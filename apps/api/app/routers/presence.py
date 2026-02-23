from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from packages.schemas import PresenceAuditInputJSON

from ..db import get_db
from ..models import (
    PresenceAuditRun,
    PresenceAuditRunStatus,
    PresenceFinding,
    PresenceFindingSeverity,
    PresenceFindingStatus,
    PresenceTask,
    PresenceTaskStatus,
    PresenceTaskType,
    Role,
    RiskTier,
)
from ..schemas import (
    PresenceAuditRunRequest,
    PresenceAuditRunResponse,
    PresenceFindingResponse,
    PresenceFindingStatusUpdateRequest,
    PresenceTaskCreateRequest,
    PresenceTaskResponse,
)
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..services.rate_limit import enforce_org_rate_limit
from ..services.phase5 import build_presence_report, fetch_website_snapshot, mock_profile_snapshot
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/presence", tags=["presence"])


def _serialize_run(row: PresenceAuditRun) -> PresenceAuditRunResponse:
    return PresenceAuditRunResponse(
        id=row.id,
        org_id=row.org_id,
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        inputs_json=row.inputs_json,
        summary_scores_json=row.summary_scores_json,
        notes_json=row.notes_json,
        error_json=row.error_json,
        created_at=row.created_at,
    )


def _serialize_finding(row: PresenceFinding) -> PresenceFindingResponse:
    return PresenceFindingResponse(
        id=row.id,
        org_id=row.org_id,
        audit_run_id=row.audit_run_id,
        source=row.source,
        category=row.category,
        severity=row.severity,
        title=row.title,
        description=row.description,
        evidence_json=row.evidence_json,
        recommendation_json=row.recommendation_json,
        status=row.status,
        created_at=row.created_at,
    )


def _serialize_task(row: PresenceTask) -> PresenceTaskResponse:
    return PresenceTaskResponse(
        id=row.id,
        org_id=row.org_id,
        finding_id=row.finding_id,
        type=row.type,
        assigned_to_user_id=row.assigned_to_user_id,
        due_at=row.due_at,
        status=row.status,
        payload_json=row.payload_json,
        created_at=row.created_at,
    )


def _task_type_from_action(action_type: str) -> PresenceTaskType:
    mapping: dict[str, PresenceTaskType] = {
        "fix_profile": PresenceTaskType.FIX_PROFILE,
        "post_gbp": PresenceTaskType.POST_GBP,
        "update_hours": PresenceTaskType.UPDATE_HOURS,
        "add_photos": PresenceTaskType.ADD_PHOTOS,
        "create_page": PresenceTaskType.CREATE_PAGE,
        "write_blog": PresenceTaskType.WRITE_BLOG,
        "respond_review": PresenceTaskType.RESPOND_REVIEW,
    }
    return mapping.get(action_type, PresenceTaskType.FIX_PROFILE)


@router.post("/audits/run", response_model=PresenceAuditRunResponse, status_code=status.HTTP_201_CREATED)
def run_presence_audit(
    payload: PresenceAuditRunRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> PresenceAuditRunResponse:
    require_role(context, minimum_role=Role.ADMIN)
    enforce_org_rate_limit(org_id=context.current_org_id, bucket_name="presence_audits", max_requests=10, window_seconds=60)
    validated = PresenceAuditInputJSON.model_validate(payload.model_dump(mode="json"))
    run = PresenceAuditRun(
        org_id=context.current_org_id,
        started_at=datetime.now(UTC),
        status=PresenceAuditRunStatus.RUNNING,
        inputs_json=validated.model_dump(mode="json"),
        summary_scores_json={},
        notes_json={},
        error_json={},
    )
    db.add(run)
    db.flush()

    try:
        snapshots: list[dict[str, Any]] = []
        providers = validated.providers_to_audit or ["gbp", "meta", "linkedin"]
        for provider in providers:
            if provider == "website":
                continue
            refs = validated.account_refs.get(provider, ["default"])
            for account_ref in refs:
                snapshots.append(mock_profile_snapshot(provider=provider, account_ref=account_ref))
        if validated.website_url:
            website_snapshot = fetch_website_snapshot(str(validated.website_url))
            website_snapshot["source"] = "website"
            website_snapshot["provider"] = "website"
            snapshots.append(website_snapshot)

        report = build_presence_report(audit_input=validated, snapshots=snapshots)
        run.status = PresenceAuditRunStatus.SUCCEEDED
        run.completed_at = datetime.now(UTC)
        run.summary_scores_json = {
            "overall_score": report.overall_score,
            "category_scores": report.category_scores,
        }
        run.notes_json = {"findings_count": len(report.findings)}
        db.flush()

        created_finding_ids: list[str] = []
        for finding in report.findings:
            row = PresenceFinding(
                org_id=context.current_org_id,
                audit_run_id=run.id,
                source=finding.source,
                category=finding.category,
                severity=PresenceFindingSeverity(finding.severity),
                title=finding.title,
                description=finding.description,
                evidence_json=finding.evidence_json,
                recommendation_json=finding.recommendation_json.model_dump(mode="json"),
                status=PresenceFindingStatus.OPEN,
            )
            db.add(row)
            db.flush()
            created_finding_ids.append(str(row.id))
            write_event(
                db=db,
                org_id=context.current_org_id,
                source="presence",
                channel="audit",
                event_type="PRESENCE_FINDING_CREATED",
                payload_json={"finding_id": str(row.id), "severity": row.severity.value},
                actor_id=str(context.current_user_id),
            )

        for action in report.prioritized_actions[:10]:
            db.add(
                PresenceTask(
                    org_id=context.current_org_id,
                    finding_id=None,
                    type=_task_type_from_action(action.action_type),
                    assigned_to_user_id=None,
                    due_at=None,
                    status=PresenceTaskStatus.OPEN,
                    payload_json=action.model_dump(mode="json"),
                )
            )
        db.flush()

        write_event(
            db=db,
            org_id=context.current_org_id,
            source="presence",
            channel="audit",
            event_type="PRESENCE_AUDIT_RUN",
            payload_json={
                "audit_run_id": str(run.id),
                "overall_score": report.overall_score,
                "findings_count": len(report.findings),
            },
            actor_id=str(context.current_user_id),
        )
        write_audit_log(
            db=db,
            context=context,
            action="presence.audit_executed",
            target_type="presence_audit_run",
            target_id=str(run.id),
            metadata_json={"finding_ids": created_finding_ids, "overall_score": report.overall_score},
            risk_tier=RiskTier.TIER_1,
        )
        db.commit()
        db.refresh(run)
        return _serialize_run(run)
    except Exception as exc:
        run.status = PresenceAuditRunStatus.FAILED
        run.completed_at = datetime.now(UTC)
        run.error_json = {"message": str(exc)[:500]}
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="presence audit failed") from exc


@router.get("", response_model=PresenceAuditRunResponse | None)
def latest_presence_report(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> PresenceAuditRunResponse | None:
    row = db.scalar(
        org_scoped(
            select(PresenceAuditRun)
            .where(PresenceAuditRun.deleted_at.is_(None))
            .order_by(desc(PresenceAuditRun.created_at))
            .limit(1),
            context.current_org_id,
            PresenceAuditRun,
        )
    )
    return None if row is None else _serialize_run(row)


@router.get("/audits", response_model=list[PresenceAuditRunResponse])
def list_audit_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[PresenceAuditRunResponse]:
    rows = db.scalars(
        org_scoped(
            select(PresenceAuditRun)
            .where(PresenceAuditRun.deleted_at.is_(None))
            .order_by(desc(PresenceAuditRun.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            PresenceAuditRun,
        )
    ).all()
    return [_serialize_run(row) for row in rows]


@router.get("/audits/{audit_run_id}", response_model=PresenceAuditRunResponse)
def get_audit_run(
    audit_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> PresenceAuditRunResponse:
    row = db.scalar(
        org_scoped(
            select(PresenceAuditRun).where(PresenceAuditRun.id == audit_run_id, PresenceAuditRun.deleted_at.is_(None)),
            context.current_org_id,
            PresenceAuditRun,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audit run not found")
    return _serialize_run(row)


@router.get("/findings", response_model=list[PresenceFindingResponse])
def list_findings(
    status_filter: PresenceFindingStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[PresenceFindingResponse]:
    stmt = org_scoped(
        select(PresenceFinding)
        .where(PresenceFinding.deleted_at.is_(None))
        .order_by(desc(PresenceFinding.created_at))
        .limit(limit)
        .offset(offset),
        context.current_org_id,
        PresenceFinding,
    )
    if status_filter is not None:
        stmt = stmt.where(PresenceFinding.status == status_filter)
    rows = db.scalars(stmt).all()
    return [_serialize_finding(row) for row in rows]


@router.patch("/findings/{finding_id}", response_model=PresenceFindingResponse)
def update_finding_status(
    finding_id: uuid.UUID,
    payload: PresenceFindingStatusUpdateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> PresenceFindingResponse:
    row = db.scalar(
        org_scoped(
            select(PresenceFinding).where(PresenceFinding.id == finding_id, PresenceFinding.deleted_at.is_(None)),
            context.current_org_id,
            PresenceFinding,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="finding not found")
    row.status = payload.status
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="presence.finding_status_updated",
        target_type="presence_finding",
        target_id=str(row.id),
        metadata_json={"status": row.status.value},
        risk_tier=RiskTier.TIER_1,
    )
    db.commit()
    db.refresh(row)
    return _serialize_finding(row)


@router.post("/tasks", response_model=PresenceTaskResponse, status_code=status.HTTP_201_CREATED)
def create_presence_task(
    payload: PresenceTaskCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> PresenceTaskResponse:
    row = PresenceTask(
        org_id=context.current_org_id,
        finding_id=payload.finding_id,
        type=payload.type,
        assigned_to_user_id=payload.assigned_to_user_id,
        due_at=payload.due_at,
        status=PresenceTaskStatus.OPEN,
        payload_json=payload.payload_json,
    )
    db.add(row)
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="presence.task_created",
        target_type="presence_task",
        target_id=str(row.id),
        metadata_json={"type": row.type.value},
        risk_tier=RiskTier.TIER_1,
    )
    db.commit()
    db.refresh(row)
    return _serialize_task(row)


@router.get("/tasks", response_model=list[PresenceTaskResponse])
def list_presence_tasks(
    status_filter: PresenceTaskStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[PresenceTaskResponse]:
    stmt = org_scoped(
        select(PresenceTask)
        .where(PresenceTask.deleted_at.is_(None))
        .order_by(desc(PresenceTask.created_at))
        .limit(limit)
        .offset(offset),
        context.current_org_id,
        PresenceTask,
    )
    if status_filter is not None:
        stmt = stmt.where(PresenceTask.status == status_filter)
    rows = db.scalars(stmt).all()
    return [_serialize_task(row) for row in rows]
