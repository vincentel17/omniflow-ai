from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Approval, ApprovalStatus, Role, WorkflowActionRun, WorkflowActionRunStatus
from ..schemas import ApprovalDecisionRequest, ApprovalResponse
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_approval(row: Approval) -> ApprovalResponse:
    return ApprovalResponse(
        id=row.id,
        org_id=row.org_id,
        entity_type=row.entity_type.value,
        entity_id=row.entity_id,
        status=row.status,
        requested_by=row.requested_by,
        decided_by=row.decided_by,
        decided_at=row.decided_at,
        notes=row.notes,
        created_at=row.created_at,
    )


@router.get("", response_model=list[ApprovalResponse])
def list_approvals(
    status_filter: ApprovalStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[ApprovalResponse]:
    require_role(context, Role.ADMIN)
    stmt = org_scoped(
        select(Approval)
        .where(Approval.deleted_at.is_(None))
        .order_by(desc(Approval.created_at))
        .limit(limit)
        .offset(offset),
        context.current_org_id,
        Approval,
    )
    if status_filter is not None:
        stmt = stmt.where(Approval.status == status_filter)
    rows = db.scalars(stmt).all()
    return [_serialize_approval(row) for row in rows]


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
def approve(
    approval_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ApprovalResponse:
    require_role(context, Role.ADMIN)
    row = db.scalar(
        org_scoped(
            select(Approval).where(Approval.id == approval_id, Approval.deleted_at.is_(None)),
            context.current_org_id,
            Approval,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="approval not found")

    row.status = ApprovalStatus.APPROVED
    row.decided_by = context.current_user_id
    row.decided_at = _utcnow()
    row.notes = payload.notes
    db.flush()

    if row.entity_type.value == "workflow_action_run":
        action_run = db.scalar(
            org_scoped(
                select(WorkflowActionRun).where(WorkflowActionRun.id == row.entity_id, WorkflowActionRun.deleted_at.is_(None)),
                context.current_org_id,
                WorkflowActionRun,
            )
        )
        if action_run is not None and action_run.status == WorkflowActionRunStatus.APPROVAL_PENDING:
            action_run.status = WorkflowActionRunStatus.QUEUED
            db.flush()
            try:
                from omniflow_worker.main import app as worker_app  # type: ignore

                worker_app.send_task("worker.workflow.action.execute", args=[str(action_run.id)])
            except Exception:
                pass

    write_audit_log(
        db=db,
        context=context,
        action="approval.approved",
        target_type="approval",
        target_id=str(row.id),
        metadata_json={"entity_type": row.entity_type.value, "entity_id": str(row.entity_id)},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="approval",
        channel="automations",
        event_type="APPROVAL_APPROVED",
        payload_json={"approval_id": str(row.id), "entity_type": row.entity_type.value, "entity_id": str(row.entity_id)},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(row)
    return _serialize_approval(row)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
def reject(
    approval_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ApprovalResponse:
    require_role(context, Role.ADMIN)
    row = db.scalar(
        org_scoped(
            select(Approval).where(Approval.id == approval_id, Approval.deleted_at.is_(None)),
            context.current_org_id,
            Approval,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="approval not found")

    row.status = ApprovalStatus.REJECTED
    row.decided_by = context.current_user_id
    row.decided_at = _utcnow()
    row.notes = payload.notes
    db.flush()

    if row.entity_type.value == "workflow_action_run":
        action_run = db.scalar(
            org_scoped(
                select(WorkflowActionRun).where(WorkflowActionRun.id == row.entity_id, WorkflowActionRun.deleted_at.is_(None)),
                context.current_org_id,
                WorkflowActionRun,
            )
        )
        if action_run is not None:
            action_run.status = WorkflowActionRunStatus.BLOCKED

    write_audit_log(
        db=db,
        context=context,
        action="approval.rejected",
        target_type="approval",
        target_id=str(row.id),
        metadata_json={"entity_type": row.entity_type.value, "entity_id": str(row.entity_id)},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="approval",
        channel="automations",
        event_type="APPROVAL_REJECTED",
        payload_json={"approval_id": str(row.id), "entity_type": row.entity_type.value, "entity_id": str(row.entity_id)},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(row)
    return _serialize_approval(row)
