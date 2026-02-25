from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditLog, ConnectorAccount, ConnectorHealth, RiskTier
from ..services.live_publishers import ConnectorError, get_live_publisher, missing_required_scopes, scopes_for_provider
from ..services.org_settings import provider_enabled_for_org
from ..services.token_vault import get_token_row
from ..settings import settings


class Publisher(Protocol):
    def publish_post(self, payload: dict[str, object]) -> dict[str, object]: ...


class MockPublisher:
    def publish_post(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "status": "published",
            "external_id": f"mock-{payload.get('channel', 'unknown')}-{int(datetime.now(UTC).timestamp())}",
            "raw_ref": "mock",
            "warnings": [],
        }


def _load_health(db: Session, org_id: uuid.UUID, provider: str, account_ref: str) -> ConnectorHealth | None:
    return db.scalar(
        select(ConnectorHealth).where(
            ConnectorHealth.org_id == org_id,
            ConnectorHealth.provider == provider,
            ConnectorHealth.account_ref == account_ref,
            ConnectorHealth.deleted_at.is_(None),
        )
    )


def _breaker_state(health: ConnectorHealth | None, threshold: int) -> str:
    if health is None:
        return "closed"
    failures = int(health.consecutive_failures or 0)
    if failures < threshold:
        return "closed"

    last_error_at = health.last_error_at
    if last_error_at is not None:
        cooldown = timedelta(seconds=max(1, int(settings.connector_circuit_breaker_cooldown_seconds)))
        if datetime.now(UTC) >= last_error_at + cooldown:
            return "half_open"
    return "open"


def _audit_live_blocked(
    db: Session,
    org_id: uuid.UUID,
    provider: str,
    account_ref: str,
    reason: str,
    extra: dict[str, object] | None = None,
) -> None:
    if not hasattr(db, "add"):
        return
    metadata: dict[str, object] = {
        "provider": provider,
        "account_ref": account_ref,
        "reason": reason,
    }
    if isinstance(extra, dict):
        metadata.update(extra)

    db.add(
        AuditLog(
            org_id=org_id,
            actor_user_id=None,
            action="LIVE_BLOCKED",
            target_type="connector_account",
            target_id=account_ref,
            risk_tier=RiskTier.TIER_2,
            metadata_json=metadata,
        )
    )


def get_publisher(
    provider: str,
    org_id: uuid.UUID,
    account_ref: str,
    db: Session | None = None,
) -> Publisher:
    if db is None:
        return MockPublisher()

    live_enabled = provider_enabled_for_org(db=db, org_id=org_id, provider=provider, operation="publish")
    if not live_enabled:
        _audit_live_blocked(
            db=db,
            org_id=org_id,
            provider=provider,
            account_ref=account_ref,
            reason="CONNECTOR_MODE_OR_PROVIDER_DISABLED",
        )
        return MockPublisher()

    health = _load_health(db=db, org_id=org_id, provider=provider, account_ref=account_ref)
    breaker = _breaker_state(health=health, threshold=settings.connector_circuit_breaker_threshold)
    if breaker == "open":
        _audit_live_blocked(
            db=db,
            org_id=org_id,
            provider=provider,
            account_ref=account_ref,
            reason="BREAKER_TRIPPED",
        )
        raise ConnectorError("circuit_open", "connector circuit breaker open")

    account = db.scalar(
        select(ConnectorAccount).where(
            ConnectorAccount.org_id == org_id,
            ConnectorAccount.provider == provider,
            ConnectorAccount.account_ref == account_ref,
            ConnectorAccount.deleted_at.is_(None),
        )
    )
    if account is None:
        raise ConnectorError("validation", "connector account not found")
    if account.status == "circuit_open" and breaker != "half_open":
        raise ConnectorError("circuit_open", "connector account disabled by circuit breaker")

    token = get_token_row(db=db, org_id=org_id, provider=provider, account_ref=account_ref)
    scopes = scopes_for_provider(token)
    missing = missing_required_scopes(provider=provider, operation="publish", token_scopes=scopes)
    if missing:
        account.status = "reauth_required"
        if health is None:
            health = ConnectorHealth(org_id=org_id, provider=provider, account_ref=account_ref)
            db.add(health)
        health.last_error_at = datetime.now(UTC)
        health.last_error_msg = f"missing scopes: {', '.join(missing)}"
        health.last_http_status = 403
        _audit_live_blocked(
            db=db,
            org_id=org_id,
            provider=provider,
            account_ref=account_ref,
            reason="MISSING_SCOPES",
            extra={"missing_scopes": missing},
        )
        raise ConnectorError("reauth_required", "missing required scopes", status_code=403)

    return get_live_publisher(provider=provider, db=db, org_id=org_id, account_ref=account_ref)


def verify_connector_health(
    db: Session, provider: str, org_id: uuid.UUID, account_ref: str
) -> ConnectorHealth:
    account = db.scalar(
        select(ConnectorAccount).where(
            ConnectorAccount.org_id == org_id,
            ConnectorAccount.provider == provider,
            ConnectorAccount.account_ref == account_ref,
            ConnectorAccount.deleted_at.is_(None),
        )
    )
    if account is None:
        raise ValueError("connector account not found")

    health = _load_health(db=db, org_id=org_id, provider=provider, account_ref=account_ref)
    if health is None:
        health = ConnectorHealth(org_id=account.org_id, provider=provider, account_ref=account_ref)
        db.add(health)
    health.last_ok_at = datetime.now(UTC)
    health.last_error_at = None
    health.last_error_msg = None
    health.last_http_status = None
    health.last_provider_error_code = None
    health.last_rate_limit_reset_at = None
    health.consecutive_failures = 0
    db.flush()
    return health