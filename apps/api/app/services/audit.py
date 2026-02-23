from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog, RiskTier
from ..tenancy import RequestContext


def write_audit_log(
    db: Session,
    context: RequestContext,
    action: str,
    target_type: str,
    target_id: str,
    metadata_json: dict[str, Any] | None = None,
    risk_tier: RiskTier = RiskTier.TIER_1,
) -> AuditLog:
    entry = AuditLog(
        org_id=context.current_org_id,
        actor_user_id=context.current_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata_json or {},
        risk_tier=risk_tier,
    )
    db.add(entry)
    db.flush()
    return entry


def write_system_audit_log(
    db: Session,
    org_id: uuid.UUID,
    action: str,
    target_type: str,
    target_id: str,
    metadata_json: dict[str, Any] | None = None,
    risk_tier: RiskTier = RiskTier.TIER_1,
) -> AuditLog:
    entry = AuditLog(
        org_id=org_id,
        actor_user_id=None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata_json or {},
        risk_tier=risk_tier,
    )
    db.add(entry)
    db.flush()
    return entry
