from __future__ import annotations

import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ConnectorAccount, ConnectorHealth, OAuthToken, Role
from ..redis_client import get_redis_client
from ..schemas import (
    ConnectorAccountResponse,
    ConnectorCallbackRequest,
    ConnectorHealthResponse,
    ConnectorProviderResponse,
    ConnectorStartRequest,
    ConnectorStartResponse,
)
from ..services.audit import write_audit_log
from ..services.connector_manager import verify_connector_health
from ..services.events import write_event
from ..services.oauth_state import consume_oauth_state, create_oauth_state
from ..services.org_settings import connector_mode_for_org
from ..services.token_vault import store_tokens
from ..settings import settings
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/connectors", tags=["connectors"])

SUPPORTED_PROVIDERS = ("google-business-profile", "meta", "linkedin")


def _provider_is_configured(provider: str) -> bool:
    if provider == "meta":
        return bool(settings.meta_app_id and settings.meta_app_secret)
    if provider == "linkedin":
        return bool(settings.linkedin_client_id and settings.linkedin_client_secret)
    if provider == "google-business-profile":
        return bool(settings.google_client_id and settings.google_client_secret)
    return False


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
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unsupported provider")

    state = create_oauth_state(get_redis_client(), context.current_org_id, provider)
    if connector_mode_for_org(db, context.current_org_id) == "mock":
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
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unsupported provider")

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

    access_token = f"mock-access-{provider}-{payload.account_ref}"
    refresh_token = f"mock-refresh-{provider}-{payload.account_ref}"
    if connector_mode_for_org(db, context.current_org_id) != "mock":
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="live oauth exchange not implemented")

    store_tokens(
        db=db,
        org_id=context.current_org_id,
        provider=provider,
        account_ref=payload.account_ref,
        access_token=access_token,
        refresh_token=refresh_token,
        scopes=["basic"],
        expires_at=None,
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
        payload_json={"provider": provider, "account_ref": payload.account_ref},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(account)
    return ConnectorAccountResponse(
        id=account.id,
        org_id=account.org_id,
        provider=account.provider,
        account_ref=account.account_ref,
        display_name=account.display_name,
        status=account.status,
        created_at=account.created_at,
    )


@router.get("/accounts", response_model=list[ConnectorAccountResponse])
def list_accounts(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[ConnectorAccountResponse]:
    rows = db.scalars(
        org_scoped(
            select(ConnectorAccount)
            .where(ConnectorAccount.deleted_at.is_(None))
            .order_by(ConnectorAccount.created_at.desc()),
            context.current_org_id,
            ConnectorAccount,
        )
    ).all()
    return [
        ConnectorAccountResponse(
            id=row.id,
            org_id=row.org_id,
            provider=row.provider,
            account_ref=row.account_ref,
            display_name=row.display_name,
            status=row.status,
            created_at=row.created_at,
        )
        for row in rows
    ]


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
    token = db.scalar(
        select(OAuthToken).where(
            OAuthToken.org_id == context.current_org_id,
            OAuthToken.provider == row.provider,
            OAuthToken.account_ref == row.account_ref,
            OAuthToken.deleted_at.is_(None),
        )
    )
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
    return ConnectorAccountResponse(
        id=row.id,
        org_id=row.org_id,
        provider=row.provider,
        account_ref=row.account_ref,
        display_name=row.display_name,
        status=row.status,
        created_at=row.created_at,
    )


@router.post("/{provider}/{account_ref}/reenable", response_model=ConnectorHealthResponse)
def reenable_connector(
    provider: str,
    account_ref: str,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ConnectorHealthResponse:
    require_role(context, Role.ADMIN)
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unsupported provider")

    health = db.scalar(
        org_scoped(
            select(ConnectorHealth).where(
                ConnectorHealth.provider == provider,
                ConnectorHealth.account_ref == account_ref,
                ConnectorHealth.deleted_at.is_(None),
            ),
            context.current_org_id,
            ConnectorHealth,
        )
    )
    if health is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="connector health not found")

    health.consecutive_failures = 0
    health.last_error_at = None
    health.last_error_msg = None

    account = db.scalar(
        org_scoped(
            select(ConnectorAccount).where(
                ConnectorAccount.provider == provider,
                ConnectorAccount.account_ref == account_ref,
                ConnectorAccount.deleted_at.is_(None),
            ),
            context.current_org_id,
            ConnectorAccount,
        )
    )
    if account is not None and account.status != "linked":
        account.status = "linked"

    write_audit_log(
        db=db,
        context=context,
        action="connector.reenabled",
        target_type="connector_health",
        target_id=str(health.id),
        metadata_json={"provider": provider, "account_ref": account_ref},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="connectors",
        channel=provider,
        event_type="CONNECTOR_REENABLED",
        payload_json={"provider": provider, "account_ref": account_ref},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(health)
    return ConnectorHealthResponse(
        id=health.id,
        org_id=health.org_id,
        provider=health.provider,
        account_ref=health.account_ref,
        last_ok_at=health.last_ok_at,
        last_error_at=health.last_error_at,
        last_error_msg=health.last_error_msg,
        consecutive_failures=health.consecutive_failures,
    )


@router.post("/{provider}/{account_ref}/healthcheck", response_model=ConnectorHealthResponse)
def run_healthcheck(
    provider: str,
    account_ref: str,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ConnectorHealthResponse:
    require_role(context, Role.MEMBER)
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unsupported provider")
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
    return ConnectorHealthResponse(
        id=health.id,
        org_id=health.org_id,
        provider=health.provider,
        account_ref=health.account_ref,
        last_ok_at=health.last_ok_at,
        last_error_at=health.last_error_at,
        last_error_msg=health.last_error_msg,
        consecutive_failures=health.consecutive_failures,
    )


@router.get("/health", response_model=list[ConnectorHealthResponse])
def list_health(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[ConnectorHealthResponse]:
    rows = db.scalars(
        org_scoped(
            select(ConnectorHealth)
            .where(ConnectorHealth.deleted_at.is_(None))
            .order_by(ConnectorHealth.created_at.desc()),
            context.current_org_id,
            ConnectorHealth,
        )
    ).all()
    return [
        ConnectorHealthResponse(
            id=row.id,
            org_id=row.org_id,
            provider=row.provider,
            account_ref=row.account_ref,
            last_ok_at=row.last_ok_at,
            last_error_at=row.last_error_at,
            last_error_msg=row.last_error_msg,
            consecutive_failures=row.consecutive_failures,
        )
        for row in rows
    ]
