from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ConnectorAccount, ConnectorHealth
from ..settings import settings


class Publisher(Protocol):
    def publish_post(self, payload: dict[str, object]) -> dict[str, object]: ...


class MockPublisher:
    def publish_post(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "status": "published",
            "external_id": f"mock-{payload.get('channel', 'unknown')}-{int(datetime.now(UTC).timestamp())}",
            "raw_ref": "mock",
        }


def get_publisher(provider: str, org_id: uuid.UUID, account_ref: str) -> Publisher:
    if settings.connector_mode == "mock":
        return MockPublisher()
    raise NotImplementedError(f"live publisher not implemented for provider={provider}")


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

    health = db.scalar(
        select(ConnectorHealth).where(
            ConnectorHealth.org_id == org_id,
            ConnectorHealth.provider == provider,
            ConnectorHealth.account_ref == account_ref,
            ConnectorHealth.deleted_at.is_(None),
        )
    )
    if health is None:
        health = ConnectorHealth(org_id=account.org_id, provider=provider, account_ref=account_ref)
        db.add(health)
    health.last_ok_at = datetime.now(UTC)
    health.last_error_at = None
    health.last_error_msg = None
    health.consecutive_failures = 0
    db.flush()
    return health
