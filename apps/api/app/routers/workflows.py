from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Role, Workflow, WorkflowActionRun, WorkflowRun, WorkflowTriggerType
from ..schemas import (
    WorkflowActionPreview,
    WorkflowActionRunResponse,
    WorkflowCreateRequest,
    WorkflowResponse,
    WorkflowRunResponse,
    WorkflowTestRequest,
    WorkflowTestResponse,
    WorkflowUpdateRequest,
)
from ..services.audit import write_audit_log
from ..services.billing import ensure_org_active
from ..services.events import write_event
from ..services.workflows import (
    current_vertical_pack,
    evaluate_definition,
    local_hour_for_org,
    serialize_action_run,
    serialize_workflow,
    serialize_workflow_run,
    settings_for_org,
)
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _get_workflow_or_404(db: Session, org_id: uuid.UUID, workflow_id: uuid.UUID) -> Workflow:
    row = db.scalar(
        org_scoped(
            select(Workflow).where(Workflow.id == workflow_id, Workflow.deleted_at.is_(None)),
            org_id,
            Workflow,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workflow not found")
    return row


def _trigger_type_from_definition(definition_json: dict[str, object]) -> WorkflowTriggerType:
    trigger_raw = definition_json.get("trigger")
    if isinstance(trigger_raw, dict):
        trigger_type = str(trigger_raw.get("type", "EVENT")).upper()
        if trigger_type == "SCHEDULE":
            return WorkflowTriggerType.SCHEDULE
    return WorkflowTriggerType.EVENT


@router.get("", response_model=list[WorkflowResponse])
def list_workflows(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[WorkflowResponse]:
    require_role(context, Role.ADMIN)
    rows = db.scalars(
        org_scoped(
            select(Workflow)
            .where(Workflow.deleted_at.is_(None))
            .order_by(desc(Workflow.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            Workflow,
        )
    ).all()
    return [WorkflowResponse.model_validate(serialize_workflow(row)) for row in rows]


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    payload: WorkflowCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> WorkflowResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    exists = db.scalar(
        org_scoped(
            select(Workflow).where(Workflow.key == payload.key, Workflow.deleted_at.is_(None)),
            context.current_org_id,
            Workflow,
        )
    )
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="workflow key already exists")

    evaluate_definition(
        definition_json=payload.definition_json,
        event_type="WORKFLOW_DRY_RUN",
        channel="workflow",
        payload_json={},
        risk_tier=0,
        org_settings=settings_for_org(db, context.current_org_id),
        vertical_pack=current_vertical_pack(db, context.current_org_id),
        local_hour=12,
    )

    workflow = Workflow(
        org_id=context.current_org_id,
        key=payload.key,
        name=payload.name,
        enabled=payload.enabled,
        trigger_type=_trigger_type_from_definition(payload.definition_json),
        definition_json=payload.definition_json,
        managed_by_pack=payload.managed_by_pack,
    )
    db.add(workflow)
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="workflow.created",
        target_type="workflow",
        target_id=str(workflow.id),
        metadata_json={"key": workflow.key},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="workflow",
        channel="automations",
        event_type="WORKFLOW_CREATED",
        payload_json={"workflow_id": str(workflow.id), "key": workflow.key},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(workflow)
    return WorkflowResponse.model_validate(serialize_workflow(workflow))


@router.get("/runs", response_model=list[WorkflowRunResponse])
def list_workflow_runs(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[WorkflowRunResponse]:
    require_role(context, Role.ADMIN)
    stmt = org_scoped(
        select(WorkflowRun)
        .where(WorkflowRun.deleted_at.is_(None))
        .order_by(desc(WorkflowRun.created_at))
        .limit(limit)
        .offset(offset),
        context.current_org_id,
        WorkflowRun,
    )
    if status_filter:
        stmt = stmt.where(WorkflowRun.status == status_filter)
    rows = db.scalars(stmt).all()
    return [WorkflowRunResponse.model_validate(serialize_workflow_run(row)) for row in rows]


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
def get_workflow_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> WorkflowRunResponse:
    require_role(context, Role.ADMIN)
    run = db.scalar(
        org_scoped(
            select(WorkflowRun).where(WorkflowRun.id == run_id, WorkflowRun.deleted_at.is_(None)),
            context.current_org_id,
            WorkflowRun,
        )
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workflow run not found")
    return WorkflowRunResponse.model_validate(serialize_workflow_run(run))


@router.get("/actions", response_model=list[WorkflowActionRunResponse])
def list_workflow_action_runs(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[WorkflowActionRunResponse]:
    require_role(context, Role.ADMIN)
    stmt = org_scoped(
        select(WorkflowActionRun)
        .where(WorkflowActionRun.deleted_at.is_(None))
        .order_by(desc(WorkflowActionRun.created_at))
        .limit(limit)
        .offset(offset),
        context.current_org_id,
        WorkflowActionRun,
    )
    if status_filter:
        stmt = stmt.where(WorkflowActionRun.status == status_filter)
    rows = db.scalars(stmt).all()
    return [WorkflowActionRunResponse.model_validate(serialize_action_run(row)) for row in rows]


@router.get("/actions/{action_run_id}", response_model=WorkflowActionRunResponse)
def get_workflow_action_run(
    action_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> WorkflowActionRunResponse:
    require_role(context, Role.ADMIN)
    row = db.scalar(
        org_scoped(
            select(WorkflowActionRun).where(WorkflowActionRun.id == action_run_id, WorkflowActionRun.deleted_at.is_(None)),
            context.current_org_id,
            WorkflowActionRun,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workflow action run not found")
    return WorkflowActionRunResponse.model_validate(serialize_action_run(row))


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> WorkflowResponse:
    require_role(context, Role.ADMIN)
    row = _get_workflow_or_404(db=db, org_id=context.current_org_id, workflow_id=workflow_id)
    return WorkflowResponse.model_validate(serialize_workflow(row))


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: uuid.UUID,
    payload: WorkflowUpdateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> WorkflowResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    workflow = _get_workflow_or_404(db=db, org_id=context.current_org_id, workflow_id=workflow_id)

    if payload.name is not None:
        workflow.name = payload.name
    if payload.enabled is not None:
        workflow.enabled = payload.enabled
    if payload.definition_json is not None:
        evaluate_definition(
            definition_json=payload.definition_json,
            event_type="WORKFLOW_DRY_RUN",
            channel="workflow",
            payload_json={},
            risk_tier=0,
            org_settings=settings_for_org(db, context.current_org_id),
            vertical_pack=current_vertical_pack(db, context.current_org_id),
            local_hour=12,
        )
        workflow.definition_json = payload.definition_json
        workflow.trigger_type = _trigger_type_from_definition(payload.definition_json)

    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="workflow.updated",
        target_type="workflow",
        target_id=str(workflow.id),
        metadata_json={"updated": sorted(payload.model_dump(exclude_none=True).keys())},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="workflow",
        channel="automations",
        event_type="WORKFLOW_UPDATED",
        payload_json={"workflow_id": str(workflow.id)},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(workflow)
    return WorkflowResponse.model_validate(serialize_workflow(workflow))


@router.post("/{workflow_id}/test", response_model=WorkflowTestResponse)
def dry_run_workflow(
    workflow_id: uuid.UUID,
    payload: WorkflowTestRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> WorkflowTestResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    workflow = _get_workflow_or_404(db=db, org_id=context.current_org_id, workflow_id=workflow_id)
    org_settings = settings_for_org(db, context.current_org_id)
    evaluated = evaluate_definition(
        definition_json=workflow.definition_json,
        event_type=payload.event_type,
        channel=payload.channel,
        payload_json=payload.payload_json,
        risk_tier=payload.risk_tier,
        org_settings=org_settings,
        vertical_pack=current_vertical_pack(db, context.current_org_id),
        local_hour=local_hour_for_org(org_settings),
    )
    return WorkflowTestResponse(
        matched=evaluated.matched,
        skipped_reason=evaluated.skipped_reason,
        overall_risk_tier=evaluated.overall_risk_tier,
        actions=[
            WorkflowActionPreview(
                action_type=action.action_type.value,
                params_json=action.params_json,
                risk_tier=action.risk_tier,
                requires_approval=action.requires_approval,
            )
            for action in evaluated.actions
        ],
    )


