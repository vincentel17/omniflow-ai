from __future__ import annotations

import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ConnectorAccount, ConnectorHealth, OAuthToken, Role
from ..redis_client import get_redis_client
from ..schemas import (
    ConnectorAccountResponse,
    ConnectorCallbackRequest,
    ConnectorDiagnosticsResponse,
    ConnectorHealthResponse,
    ConnectorProviderResponse,
    ConnectorStartRequest,
    ConnectorStartResponse,
)
from ..services.audit import write_audit_log
from ..services.billing import ensure_org_active
from ..services.connector_manager import verify_connector_health
from ..services.events import write_event
from ..services.oauth_state import consume_oauth_state, create_oauth_state
from ..services.org_settings import connector_mode_for_org, provider_enabled_for_org
from ..services.token_vault import get_token_row, store_tokens
from ..settings import settings
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/connectors", tags=["connectors"])

SUPPORTED_PROVIDERS = ("google-business-profile", "meta", "linkedin")

_REQUIRED_SCOPES: dict[str, dict[str, set[str]]] = {
    "google-business-profile": {
        "publish": {"business.manage"},
        "inbox": {"business.manage"},
    },
    "meta": {
        "publish": {"pages_manage_posts"},
        "inbox": {"pages_messaging"},
    },
    "linkedin": {
        "publish": {"w_member_social"},
        "inbox": {"r_organization_social"},
    },
}


def _provider_is_configured(provider: str) -> bool:
    if provider == "meta":
        return bool(settings.meta_app_id and settings.meta_app_secret)
    if provider == "linkedin":
        return bool(settings.linkedin_client_id and settings.linkedin_client_secret)
    if provider == "google-business-profile":
        return bool(settings.google_client_id and settings.google_client_secret)
    return False


def _ensure_provider(provider: str) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unsupported provider")


def _serialize_account(row: ConnectorAccount) -> ConnectorAccountResponse:
    return ConnectorAccountResponse(
        id=row.id,
        org_id=row.org_id,
        provider=row.provider,
        account_ref=row.account_ref,
        display_name=row.display_name,
        status=row.status,
        created_at=row.created_at,
    )


def _serialize_health(row: ConnectorHealth) -> ConnectorHealthResponse:
    return ConnectorHealthResponse(
        id=row.id,
        org_id=row.org_id,
        provider=row.provider,
        account_ref=row.account_ref,
        last_ok_at=row.last_ok_at,
        last_error_at=row.last_error_at,
        last_error_msg=row.last_error_msg,
        consecutive_failures=row.consecutive_failures,
        last_http_status=row.last_http_status,
        last_provider_error_code=row.last_provider_error_code,
        last_rate_limit_reset_at=row.last_rate_limit_reset_at,
    )


def _missing_required_scopes(provider: str, operation: str, token_scopes: list[str]) -> list[str]:
    required = _REQUIRED_SCOPES.get(provider, {}).get(operation, set())
    if not required:
        return []
    available = set(token_scopes)
    return sorted(scope for scope in required if scope not in available)


def _diagnostics(
    account: ConnectorAccount,
    health: ConnectorHealth | None,
    token: OAuthToken | None,
    mode_effective: str,
) -> ConnectorDiagnosticsResponse:
    scopes = token.scopes_json if token is not None and isinstance(token.scopes_json, list) else []
    last_error_msg = None
    if health is not None and isinstance(health.last_error_msg, str):
        last_error_msg = health.last_error_msg[:200]
    failures = int(health.consecutive_failures or 0) if health is not None else 0
    breaker_state = "open" if account.status == "circuit_open" or failures >= settings.connector_circuit_breaker_threshold else "closed"
    health_status = "ok"
    if breaker_state == "open":
        health_status = "degraded"
    elif health is not None and health.last_error_at is not None:
        health_status = "error"

    return ConnectorDiagnosticsResponse(
        id=account.id,
        provider=account.provider,
        account_ref=account.account_ref,
        account_status=account.status,
        scopes=[str(scope) for scope in scopes if isinstance(scope, str)],
        expires_at=token.expires_at if token is not None else None,
        health_status=health_status,
        breaker_state=breaker_state,
        last_error_msg=last_error_msg,
        last_http_status=health.last_http_status if health is not None else None,
        last_provider_error_code=health.last_provider_error_code if health is not None else None,
        last_rate_limit_reset_at=health.last_rate_limit_reset_at if health is not None else None,
        reauth_required=account.status == "reauth_required",
        mode_effective=mode_effective,
    )


@router.get("/providers", response_model=list[ConnectorProviderResponse])
def list_providers(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[ConnectorProviderResponse]:
    require_role(context, Role.MEMBER)
    mode = connector_mode_for_org(db, context.current_org_id)
    return [
        ConnectorProviderResponse(
            provider=provider,
            mode=mode,
            configured=_provider_is_configured(provider),
        )
        for provider in SUPPORTED_PROVIDERS
    ]


@router.post("/{provider}/start", response_model=ConnectorStartResponse)
def start_oauth(
    provider: str,
    payload: ConnectorStartRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ConnectorStartResponse:
    del payload
    require_role(context, Role.ADMIN)
    _ensure_provider(provider)

    if not settings.oauth_redirect_allowed(settings.oauth_redirect_uri):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="oauth redirect uri is not allowed")

    state = create_oauth_state(get_redis_client(), context.current_org_id, provider)
    mode = connector_mode_for_org(db, context.current_org_id)
    if mode == "live":
        ensure_org_active(db=db, org_id=context.current_org_id)
    if mode == "mock":
        params = urlencode({"state": state, "code": "mock-code"})
        auth_url = f"{settings.oauth_redirect_uri}?{params}"
    else:
        params = urlencode(
            {
                "client_id": "configured-in-env",
                "redirect_uri": settings.oauth_redirect_uri,
                "response_type": "code",
                "state": state,
            }
        )
        auth_url = f"https://auth.{provider}.example/oauth/authorize?{params}"
    return ConnectorStartResponse(provider=provider, state=state, authorization_url=auth_url)


@router.post("/{provider}/callback", response_model=ConnectorAccountResponse)
def oauth_callback(
    provider: str,
    payload: ConnectorCallbackRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ConnectorAccountResponse:
    require_role(context, Role.ADMIN)
    _ensure_provider(provider)

    state_data = consume_oauth_state(get_redis_client(), payload.state)
    if state_data is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired oauth state")
    if state_data["provider"] != provider or state_data["org_id"] != str(context.current_org_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="oauth state does not match tenant context")

    account = db.scalar(
        select(ConnectorAccount).where(
            ConnectorAccount.org_id == context.current_org_id,
            ConnectorAccount.provider == provider,
            ConnectorAccount.account_ref == payload.account_ref,
        )
    )
    if account is None:
        account = ConnectorAccount(
            org_id=context.current_org_id,
            provider=provider,
            account_ref=payload.account_ref,
            display_name=payload.display_name,
            status="linked",
        )
        db.add(account)
    else:
        account.display_name = payload.display_name
        account.status = "linked"
        account.deleted_at = None
    db.flush()

    mode = connector_mode_for_org(db, context.current_org_id)
    if mode == "live":
        ensure_org_active(db=db, org_id=context.current_org_id)
    access_token = f"mock-access-{provider}-{payload.account_ref}"
    refresh_token = f"mock-refresh-{provider}-{payload.account_ref}"
    granted_scopes = sorted(_REQUIRED_SCOPES.get(provider, {}).get("publish", set()) | _REQUIRED_SCOPES.get(provider, {}).get("inbox", set()))

    if mode == "live" and not _provider_is_configured(provider):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="provider not configured for live oauth")

    store_tokens(
        db=db,
        org_id=context.current_org_id,
        provider=provider,
        account_ref=payload.account_ref,
        access_token=access_token,
        refresh_token=refresh_token,
        scopes=granted_scopes,
        expires_at=datetime.now(UTC),
    )

    health = db.scalar(
        select(ConnectorHealth).where(
            ConnectorHealth.org_id == context.current_org_id,
            ConnectorHealth.provider == provider,
            ConnectorHealth.account_ref == payload.account_ref,
        )
    )
    if health is None:
        health = ConnectorHealth(
            org_id=context.current_org_id,
            provider=provider,
            account_ref=payload.account_ref,
            last_ok_at=datetime.now(UTC),
            consecutive_failures=0,
        )
        db.add(health)
    else:
        health.last_ok_at = datetime.now(UTC)
        health.last_error_at = None
        health.last_error_msg = None
        health.last_http_status = None
        health.last_provider_error_code = None
        health.consecutive_failures = 0
        health.deleted_at = None

    write_audit_log(
        db=db,
        context=context,
        action="connector.linked",
        target_type="connector_account",
        target_id=str(account.id),
        metadata_json={"provider": provider, "account_ref": payload.account_ref},
    )
    write_audit_log(
        db=db,
        context=context,
        action="token.stored",
        target_type="oauth_token",
        target_id=f"{provider}:{payload.account_ref}",
        metadata_json={"provider": provider, "account_ref": payload.account_ref},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="connectors",
        channel=provider,
        event_type="CONNECTOR_LINKED",
        payload_json={"provider": provider, "account_ref": payload.account_ref, "mode": mode},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(account)
    return _serialize_account(account)


@router.get("/accounts", response_model=list[ConnectorAccountResponse])
def list_accounts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[ConnectorAccountResponse]:
    rows = db.scalars(
        org_scoped(
            select(ConnectorAccount)
            .where(ConnectorAccount.deleted_at.is_(None))
            .order_by(desc(ConnectorAccount.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            ConnectorAccount,
        )
    ).all()
    return [_serialize_account(row) for row in rows]


@router.get("/accounts/{account_id}/diagnostics", response_model=ConnectorDiagnosticsResponse)
def connector_diagnostics(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ConnectorDiagnosticsResponse:
    require_role(context, Role.MEMBER)
    account = db.scalar(
        org_scoped(
            select(ConnectorAccount).where(ConnectorAccount.id == account_id, ConnectorAccount.deleted_at.is_(None)),
            context.current_org_id,
            ConnectorAccount,
        )
    )
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="connector account not found")

    token = get_token_row(db=db, org_id=context.current_org_id, provider=account.provider, account_ref=account.account_ref)
    health = db.scalar(
        org_scoped(
            select(ConnectorHealth).where(
                ConnectorHealth.provider == account.provider,
                ConnectorHealth.account_ref == account.account_ref,
                ConnectorHealth.deleted_at.is_(None),
            ),
            context.current_org_id,
            ConnectorHealth,
        )
    )

    mode_effective = "live" if provider_enabled_for_org(db, context.current_org_id, account.provider, "publish") else "mock"
    diagnostics = _diagnostics(account=account, health=health, token=token, mode_effective=mode_effective)

    missing_scopes = _missing_required_scopes(account.provider, "publish", diagnostics.scopes)
    if missing_scopes and account.status == "linked":
        account.status = "reauth_required"
        if health is not None:
            health.last_error_msg = f"missing scopes: {', '.join(missing_scopes)}"
        db.flush()
        diagnostics = _diagnostics(account=account, health=health, token=token, mode_effective=mode_effective)

    db.commit()
    return diagnostics


@router.post("/accounts/{account_id}/disconnect", response_model=ConnectorAccountResponse)
def disconnect_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ConnectorAccountResponse:
    require_role(context, Role.ADMIN)
    row = db.scalar(
        org_scoped(
            select(ConnectorAccount).where(
                ConnectorAccount.id == account_id,
                ConnectorAccount.deleted_at.is_(None),
            ),
            context.current_org_id,
            ConnectorAccount,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="connector account not found")

    row.status = "disconnected"
    row.deleted_at = datetime.now(UTC)
    token = get_token_row(db=db, org_id=context.current_org_id, provider=row.provider, account_ref=row.account_ref)
    if token is not None:
        token.deleted_at = datetime.now(UTC)

    write_audit_log(
        db=db,
        context=context,
        action="connector.disconnected",
        target_type="connector_account",
        target_id=str(row.id),
        metadata_json={"provider": row.provider, "account_ref": row.account_ref},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="connectors",
        channel=row.provider,
        event_type="CONNECTOR_UNLINKED",
        payload_json={"provider": row.provider, "account_ref": row.account_ref},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    return _serialize_account(row)


@router.post("/accounts/{account_id}/revoke", response_model=ConnectorAccountResponse)
def revoke_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ConnectorAccountResponse:
    return disconnect_account(account_id=account_id, db=db, context=context)


@router.post("/accounts/{account_id}/breaker/reset", response_model=ConnectorHealthResponse)
def breaker_reset(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ConnectorHealthResponse:
    require_role(context, Role.ADMIN)
    account = db.scalar(
        org_scoped(
            select(ConnectorAccount).where(ConnectorAccount.id == account_id, ConnectorAccount.deleted_at.is_(None)),
            context.current_org_id,
            ConnectorAccount,
        )
    )
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="connector account not found")

    health = db.scalar(
        org_scoped(
            select(ConnectorHealth).where(
                ConnectorHealth.provider == account.provider,
                ConnectorHealth.account_ref == account.account_ref,
                ConnectorHealth.deleted_at.is_(None),
            ),
            context.current_org_id,
            ConnectorHealth,
        )
    )
    if health is None:
        health = ConnectorHealth(org_id=context.current_org_id, provider=account.provider, account_ref=account.account_ref)
        db.add(health)

    health.consecutive_failures = 0
    health.last_error_at = None
    health.last_error_msg = None
    health.last_http_status = None
    health.last_provider_error_code = None
    account.status = "linked"

    write_audit_log(
        db=db,
        context=context,
        action="connector.breaker_reset",
        target_type="connector_health",
        target_id=str(health.id),
        metadata_json={"provider": account.provider, "account_ref": account.account_ref},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="connectors",
        channel=account.provider,
        event_type="CONNECTOR_BREAKER_RESET",
        payload_json={"provider": account.provider, "account_ref": account.account_ref},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(health)
    return _serialize_health(health)


@router.post("/{provider}/{account_ref}/healthcheck", response_model=ConnectorHealthResponse)
def run_healthcheck(
    provider: str,
    account_ref: str,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ConnectorHealthResponse:
    require_role(context, Role.MEMBER)
    _ensure_provider(provider)
    try:
        health = verify_connector_health(db=db, provider=provider, org_id=context.current_org_id, account_ref=account_ref)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="connectors",
        channel=provider,
        event_type="CONNECTOR_HEALTH_OK",
        payload_json={"provider": provider, "account_ref": account_ref},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    return _serialize_health(health)


@router.post("/accounts/{account_id}/healthcheck", response_model=ConnectorHealthResponse)
def run_healthcheck_by_id(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ConnectorHealthResponse:
    require_role(context, Role.MEMBER)
    account = db.scalar(
        org_scoped(
            select(ConnectorAccount).where(ConnectorAccount.id == account_id, ConnectorAccount.deleted_at.is_(None)),
            context.current_org_id,
            ConnectorAccount,
        )
    )
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="connector account not found")
    return run_healthcheck(provider=account.provider, account_ref=account.account_ref, db=db, context=context)


@router.get("/health", response_model=list[ConnectorHealthResponse])
def list_health(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[ConnectorHealthResponse]:
    rows = db.scalars(
        org_scoped(
            select(ConnectorHealth)
            .where(ConnectorHealth.deleted_at.is_(None))
            .order_by(desc(ConnectorHealth.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            ConnectorHealth,
        )
    ).all()
    return [_serialize_health(row) for row in rows]


