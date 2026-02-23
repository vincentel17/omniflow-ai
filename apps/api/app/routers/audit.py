from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog
from ..schemas import AuditLogResponse
from ..tenancy import RequestContext, get_request_context, org_scoped

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[AuditLogResponse]:
    stmt = org_scoped(
        select(AuditLog)
        .where(AuditLog.deleted_at.is_(None))
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .offset(offset),
        context.current_org_id,
        AuditLog,
    )
    rows = db.scalars(stmt).all()
    return [
        AuditLogResponse(
            id=row.id,
            org_id=row.org_id,
            actor_user_id=row.actor_user_id,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            risk_tier=row.risk_tier,
            metadata_json=row.metadata_json,
            created_at=row.created_at,
        )
        for row in rows
    ]
