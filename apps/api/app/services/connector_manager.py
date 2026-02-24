from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ConnectorAccount, ConnectorHealth
from ..services.live_publishers import ConnectorError, get_live_publisher
from ..services.org_settings import provider_enabled_for_org
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
    if failures >= threshold:
        return "open"
    return "closed"


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
        return MockPublisher()

    health = _load_health(db=db, org_id=org_id, provider=provider, account_ref=account_ref)
    if _breaker_state(health=health, threshold=settings.connector_circuit_breaker_threshold) == "open":
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
    if account.status == "circuit_open":
        raise ConnectorError("circuit_open", "connector account disabled by circuit breaker")

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
