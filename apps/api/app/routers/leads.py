from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    InboxMessage,
    InboxThread,
    Lead,
    LeadAssignment,
    LeadScore,
    LeadStatus,
    NurtureTask,
    NurtureTaskStatus,
    NurtureTaskType,
    RiskTier,
    SLAConfig,
    VerticalPack,
)
from ..schemas import (
    LeadAssignmentResponse,
    LeadPatchRequest,
    LeadResponse,
    LeadScoreResponse,
    NurtureApplyRequest,
    NurtureTaskResponse,
    NurtureTaskUpdateRequest,
    SLAConfigPayload,
    SLAConfigResponse,
)
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..services.org_settings import assert_feature_enabled
from ..services.phase4 import (
    build_nurture_plan,
    choose_round_robin_assignee,
    due_at_from_minutes,
    ensure_sla_config,
    ensure_pipeline_templates,
    extract_lead_capture,
    score_lead_from_context,
    upsert_lead_score,
)
from ..tenancy import RequestContext, get_request_context, org_scoped

router = APIRouter(prefix="/leads", tags=["leads"])
sla_router = APIRouter(prefix="/sla", tags=["sla"])


def _serialize_lead(row: Lead) -> LeadResponse:
    return LeadResponse(
        id=row.id,
        org_id=row.org_id,
        source=row.source,
        status=row.status,
        name=row.name,
        email=row.email,
        phone=row.phone,
        location_json=row.location_json,
        tags_json=row.tags_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _serialize_assignment(row: LeadAssignment) -> LeadAssignmentResponse:
    return LeadAssignmentResponse(
        id=row.id,
        org_id=row.org_id,
        lead_id=row.lead_id,
        assigned_to_user_id=row.assigned_to_user_id,
        rule_applied=row.rule_applied,
        assigned_at=row.assigned_at,
        created_at=row.created_at,
    )


def _serialize_score(row: LeadScore) -> LeadScoreResponse:
    return LeadScoreResponse(
        id=row.id,
        org_id=row.org_id,
        lead_id=row.lead_id,
        score_total=row.score_total,
        score_json=row.score_json,
        scored_at=row.scored_at,
        model_version=row.model_version,
    )


def _serialize_task(row: NurtureTask) -> NurtureTaskResponse:
    return NurtureTaskResponse(
        id=row.id,
        org_id=row.org_id,
        lead_id=row.lead_id,
        type=row.type,
        due_at=row.due_at,
        status=row.status,
        template_key=row.template_key,
        payload_json=row.payload_json,
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _lead_with_scope(db: Session, context: RequestContext, lead_id: uuid.UUID) -> Lead:
    lead = db.scalar(
        org_scoped(select(Lead).where(Lead.id == lead_id, Lead.deleted_at.is_(None)), context.current_org_id, Lead)
    )
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lead not found")
    return lead


def _transcript_for_thread(db: Session, context: RequestContext, thread: InboxThread) -> str:
    rows = db.scalars(
        org_scoped(
            select(InboxMessage)
            .where(InboxMessage.thread_id == thread.id, InboxMessage.deleted_at.is_(None))
            .order_by(InboxMessage.created_at),
            context.current_org_id,
            InboxMessage,
        )
    ).all()
    return "\n".join(row.body_text for row in rows)


def _org_pack_slug(db: Session, context: RequestContext) -> str:
    current = db.scalar(
        org_scoped(select(VerticalPack).where(VerticalPack.deleted_at.is_(None)), context.current_org_id, VerticalPack)
    )
    return "generic" if current is None else current.pack_slug


@router.post("/from-thread/{thread_id}", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
def create_lead_from_thread(
    thread_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> LeadResponse:
    thread = db.scalar(
        org_scoped(
            select(InboxThread).where(InboxThread.id == thread_id, InboxThread.deleted_at.is_(None)),
            context.current_org_id,
            InboxThread,
        )
    )
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thread not found")
    if thread.lead_id is not None:
        existing = _lead_with_scope(db, context, thread.lead_id)
        return _serialize_lead(existing)

    pack_slug = _org_pack_slug(db, context)
    ensure_pipeline_templates(db=db, org_id=context.current_org_id, pack_slug=pack_slug)
    transcript = _transcript_for_thread(db, context, thread)
    capture = extract_lead_capture(transcript=transcript)
    lead = Lead(
        org_id=context.current_org_id,
        source=thread.provider,
        status=LeadStatus.NEW,
        name=capture.lead_fields.name,
        email=capture.lead_fields.email,
        phone=capture.lead_fields.phone,
        location_json=capture.lead_fields.location,
        tags_json=[capture.classification],
    )
    db.add(lead)
    db.flush()
    thread.lead_id = lead.id
    db.flush()
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="inbox",
        channel="lead",
        event_type="LEAD_CREATED",
        lead_id=str(lead.id),
        payload_json={"thread_id": str(thread.id), "classification": capture.classification},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="lead.created_from_thread",
        target_type="lead",
        target_id=str(lead.id),
        metadata_json={"thread_id": str(thread.id)},
        risk_tier=RiskTier.TIER_1,
    )
    db.commit()
    db.refresh(lead)
    return _serialize_lead(lead)


@router.get("", response_model=list[LeadResponse])
def list_leads(
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    assigned_to: uuid.UUID | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[LeadResponse]:
    stmt = org_scoped(
        select(Lead).where(Lead.deleted_at.is_(None)).order_by(desc(Lead.created_at)).limit(limit).offset(offset),
        context.current_org_id,
        Lead,
    )
    if status_filter is not None:
        stmt = stmt.where(Lead.status == status_filter)
    if source is not None:
        stmt = stmt.where(Lead.source == source)
    if assigned_to is not None:
        stmt = stmt.join(LeadAssignment, LeadAssignment.lead_id == Lead.id).where(
            LeadAssignment.assigned_to_user_id == assigned_to,
            LeadAssignment.deleted_at.is_(None),
        )
    rows = db.scalars(stmt).all()
    return [_serialize_lead(row) for row in rows]


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> LeadResponse:
    return _serialize_lead(_lead_with_scope(db=db, context=context, lead_id=lead_id))


@router.patch("/{lead_id}", response_model=LeadResponse)
def patch_lead(
    lead_id: uuid.UUID,
    payload: LeadPatchRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> LeadResponse:
    lead = _lead_with_scope(db=db, context=context, lead_id=lead_id)
    previous_status = lead.status
    updates = payload.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(lead, key, value)
    db.flush()
    if "status" in updates and lead.status != previous_status:
        write_event(
            db=db,
            org_id=context.current_org_id,
            source="lead",
            channel="lead",
            event_type="LEAD_STATUS_CHANGED",
            lead_id=str(lead.id),
            payload_json={"from_status": previous_status.value, "to_status": lead.status.value},
            actor_id=str(context.current_user_id),
        )
    write_audit_log(
        db=db,
        context=context,
        action="lead.updated",
        target_type="lead",
        target_id=str(lead.id),
        metadata_json={"fields": list(updates.keys())},
    )
    db.commit()
    db.refresh(lead)
    return _serialize_lead(lead)


@router.post("/{lead_id}/score", response_model=LeadScoreResponse)
def score_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> LeadScoreResponse:
    lead = _lead_with_scope(db=db, context=context, lead_id=lead_id)
    thread = db.scalar(
        org_scoped(
            select(InboxThread).where(InboxThread.lead_id == lead.id, InboxThread.deleted_at.is_(None)),
            context.current_org_id,
            InboxThread,
        )
    )
    transcript = "" if thread is None else _transcript_for_thread(db=db, context=context, thread=thread)
    score_payload = score_lead_from_context(lead=lead, transcript=transcript, pack_slug=_org_pack_slug(db, context))
    score = upsert_lead_score(db=db, org_id=context.current_org_id, lead=lead, score_payload=score_payload)
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="lead",
        channel="lead",
        event_type="LEAD_SCORED",
        lead_id=str(lead.id),
        payload_json={"total": score.score_total},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="lead.scored",
        target_type="lead",
        target_id=str(lead.id),
        metadata_json={"total": score.score_total},
    )
    db.commit()
    db.refresh(score)
    return _serialize_score(score)


@router.post("/{lead_id}/route", response_model=LeadAssignmentResponse)
def route_lead(
    lead_id: uuid.UUID,
    rule: str = Query(default="round_robin", pattern="^(round_robin|tag|territory)$"),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> LeadAssignmentResponse:
    lead = _lead_with_scope(db=db, context=context, lead_id=lead_id)
    assert_feature_enabled(
        db=db,
        org_id=context.current_org_id,
        feature_key="enable_auto_lead_routing",
        detail="auto lead routing is disabled by org ops settings",
    )

    if rule == "round_robin":
        assigned_to, rationale = choose_round_robin_assignee(db=db, org_id=context.current_org_id)
    else:
        assigned_to, rationale = choose_round_robin_assignee(db=db, org_id=context.current_org_id)
        rationale = f"{rule}:fallback_to_round_robin"

    existing = db.scalar(
        org_scoped(
            select(LeadAssignment).where(LeadAssignment.lead_id == lead.id, LeadAssignment.deleted_at.is_(None)),
            context.current_org_id,
            LeadAssignment,
        )
    )
    if existing is None:
        assignment = LeadAssignment(
            org_id=context.current_org_id,
            lead_id=lead.id,
            assigned_to_user_id=assigned_to,
            rule_applied=rationale,
        )
        db.add(assignment)
        db.flush()
    else:
        existing.assigned_to_user_id = assigned_to
        existing.rule_applied = rationale
        assignment = existing
        db.flush()

    thread = db.scalar(
        org_scoped(
            select(InboxThread).where(InboxThread.lead_id == lead.id, InboxThread.deleted_at.is_(None)),
            context.current_org_id,
            InboxThread,
        )
    )
    if thread is not None:
        thread.assigned_to_user_id = assigned_to

    sla = ensure_sla_config(db=db, org_id=context.current_org_id)
    first_response = NurtureTask(
        org_id=context.current_org_id,
        lead_id=lead.id,
        type=NurtureTaskType.TASK,
        due_at=due_at_from_minutes(sla.response_time_minutes),
        status=NurtureTaskStatus.OPEN,
        template_key="first_response",
        payload_json={"title": "First Response", "assigned_to_user_id": str(assigned_to)},
        created_by=context.current_user_id,
    )
    db.add(first_response)
    db.flush()

    write_event(
        db=db,
        org_id=context.current_org_id,
        source="lead",
        channel="lead",
        event_type="LEAD_ASSIGNED",
        lead_id=str(lead.id),
        payload_json={"assigned_to_user_id": str(assigned_to), "rule_applied": rationale},
        actor_id=str(context.current_user_id),
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="lead",
        channel="lead",
        event_type="NURTURE_TASK_CREATED",
        lead_id=str(lead.id),
        payload_json={"task_id": str(first_response.id), "type": first_response.type.value},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="lead.routed",
        target_type="lead",
        target_id=str(lead.id),
        metadata_json={"assigned_to_user_id": str(assigned_to), "rule": rationale},
    )
    db.commit()
    db.refresh(assignment)
    return _serialize_assignment(assignment)


@router.post("/{lead_id}/nurture/suggest")
def suggest_nurture(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    lead = _lead_with_scope(db=db, context=context, lead_id=lead_id)
    plan = build_nurture_plan(lead)
    return plan.model_dump(mode="json")


@router.post("/{lead_id}/nurture/apply", response_model=list[NurtureTaskResponse], status_code=status.HTTP_201_CREATED)
def apply_nurture(
    lead_id: uuid.UUID,
    payload: NurtureApplyRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[NurtureTaskResponse]:
    lead = _lead_with_scope(db=db, context=context, lead_id=lead_id)
    assert_feature_enabled(
        db=db,
        org_id=context.current_org_id,
        feature_key="enable_auto_nurture_apply",
        detail="auto nurture apply is disabled by org ops settings",
    )
    created: list[NurtureTask] = []
    for task in payload.tasks:
        row = NurtureTask(
            org_id=context.current_org_id,
            lead_id=lead.id,
            type=task.type,
            due_at=due_at_from_minutes(task.due_in_minutes),
            status=NurtureTaskStatus.OPEN,
            template_key=task.message_template_key,
            payload_json={"message_body": task.message_body},
            created_by=context.current_user_id,
        )
        db.add(row)
        db.flush()
        created.append(row)
        write_event(
            db=db,
            org_id=context.current_org_id,
            source="lead",
            channel="lead",
            event_type="NURTURE_TASK_CREATED",
            lead_id=str(lead.id),
            payload_json={"task_id": str(row.id), "type": row.type.value},
            actor_id=str(context.current_user_id),
        )
    write_audit_log(
        db=db,
        context=context,
        action="lead.nurture_applied",
        target_type="lead",
        target_id=str(lead.id),
        metadata_json={"task_count": len(created)},
    )
    db.commit()
    for row in created:
        db.refresh(row)
    return [_serialize_task(row) for row in created]


@router.get("/{lead_id}/nurture/tasks", response_model=list[NurtureTaskResponse])
def list_nurture_tasks(
    lead_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[NurtureTaskResponse]:
    _lead_with_scope(db=db, context=context, lead_id=lead_id)
    rows = db.scalars(
        org_scoped(
            select(NurtureTask)
            .where(NurtureTask.lead_id == lead_id, NurtureTask.deleted_at.is_(None))
            .order_by(desc(NurtureTask.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            NurtureTask,
        )
    ).all()
    return [_serialize_task(row) for row in rows]


@router.patch("/{lead_id}/nurture/tasks/{task_id}", response_model=NurtureTaskResponse)
def update_nurture_task(
    lead_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: NurtureTaskUpdateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> NurtureTaskResponse:
    _lead_with_scope(db=db, context=context, lead_id=lead_id)
    task = db.scalar(
        org_scoped(
            select(NurtureTask).where(
                NurtureTask.id == task_id,
                NurtureTask.lead_id == lead_id,
                NurtureTask.deleted_at.is_(None),
            ),
            context.current_org_id,
            NurtureTask,
        )
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="nurture task not found")
    task.status = payload.status
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="lead.nurture_task_updated",
        target_type="nurture_task",
        target_id=str(task.id),
        metadata_json={"status": task.status.value},
    )
    db.commit()
    db.refresh(task)
    return _serialize_task(task)


@sla_router.get("/config", response_model=SLAConfigResponse)
def get_sla_config(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> SLAConfigResponse:
    config = ensure_sla_config(db=db, org_id=context.current_org_id)
    db.commit()
    db.refresh(config)
    return SLAConfigResponse(
        id=config.id,
        org_id=config.org_id,
        response_time_minutes=config.response_time_minutes,
        escalation_minutes=config.escalation_minutes,
        notify_channels_json=config.notify_channels_json,
        created_at=config.created_at,
    )


@sla_router.post("/config", response_model=SLAConfigResponse)
def upsert_sla_config(
    payload: SLAConfigPayload,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> SLAConfigResponse:
    config = db.scalar(
        org_scoped(select(SLAConfig).where(SLAConfig.deleted_at.is_(None)), context.current_org_id, SLAConfig)
    )
    if config is None:
        config = SLAConfig(org_id=context.current_org_id)
        db.add(config)
    config.response_time_minutes = payload.response_time_minutes
    config.escalation_minutes = payload.escalation_minutes
    config.notify_channels_json = payload.notify_channels_json
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="sla.config_updated",
        target_type="sla_config",
        target_id=str(config.id),
        metadata_json={"response_time_minutes": config.response_time_minutes},
    )
    db.commit()
    db.refresh(config)
    return SLAConfigResponse(
        id=config.id,
        org_id=config.org_id,
        response_time_minutes=config.response_time_minutes,
        escalation_minutes=config.escalation_minutes,
        notify_channels_json=config.notify_channels_json,
        created_at=config.created_at,
    )
