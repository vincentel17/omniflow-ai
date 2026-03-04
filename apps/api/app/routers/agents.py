from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AgentRun, AgentRunStatus, Approval, ApprovalEntityType, ApprovalStatus, Role
from ..schemas import AgentContextResponse, AgentRunCreateRequest, AgentRunListItem, AgentRunResponse
from ..services.agents import (
    approval_block_reason,
    assert_agent_controls,
    build_context_snapshot,
    create_agent_run_row,
    enforce_plan_safety,
    enforce_rate_limits,
    list_agent_definitions,
    plans_for_org,
    requires_approval,
    serialize_agent_run,
    set_agent_definition_enabled,
)
from ..services.audit import write_audit_log
from ..services.billing import ensure_org_active
from ..services.events import write_event
from ..services.org_settings import get_org_settings_payload
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentDefinitionResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    enabled: bool
    supported_packs_json: list[str]
    config_json: dict[str, object]
    created_at: str


class AgentDefinitionPatchRequest(BaseModel):
    enabled: bool


def _serialize_run_response(row: AgentRun) -> AgentRunResponse:
    return AgentRunResponse.model_validate(serialize_agent_run(row))


@router.get("/context", response_model=AgentContextResponse)
def get_context(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AgentContextResponse:
    require_role(context, Role.ADMIN)
    snapshot = build_context_snapshot(db=db, org_id=context.current_org_id)
    return AgentContextResponse(snapshot=snapshot.model_dump())


@router.get("/definitions", response_model=list[AgentDefinitionResponse])
def get_definitions(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[AgentDefinitionResponse]:
    require_role(context, Role.ADMIN)
    rows = list_agent_definitions(db)
    return [
        AgentDefinitionResponse(
            id=row.id,
            name=row.name,
            version=row.version,
            enabled=row.enabled,
            supported_packs_json=list(row.supported_packs_json or []),
            config_json=dict(row.config_json or {}),
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.patch("/definitions/{agent_name}", response_model=AgentDefinitionResponse)
def patch_definition(
    agent_name: str,
    payload: AgentDefinitionPatchRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AgentDefinitionResponse:
    require_role(context, Role.ADMIN)
    row = set_agent_definition_enabled(db=db, name=agent_name, enabled=payload.enabled)
    write_audit_log(
        db=db,
        context=context,
        action="agent.definition.updated",
        target_type="agent_definition",
        target_id=str(row.id),
        metadata_json={"name": row.name, "enabled": row.enabled},
    )
    db.commit()
    return AgentDefinitionResponse(
        id=row.id,
        name=row.name,
        version=row.version,
        enabled=row.enabled,
        supported_packs_json=list(row.supported_packs_json or []),
        config_json=dict(row.config_json or {}),
        created_at=row.created_at.isoformat(),
    )


@router.post("/run", response_model=AgentRunResponse, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: AgentRunCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AgentRunResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    settings_payload = get_org_settings_payload(db=db, org_id=context.current_org_id)
    assert_agent_controls(settings_payload)
    enforce_rate_limits(db=db, org_id=context.current_org_id, settings_payload=settings_payload)

    plans = plans_for_org(db=db, org_id=context.current_org_id)
    if not plans:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="no agent plans available")

    first_row: AgentRun | None = None
    for plan in plans:
        safe_plan = enforce_plan_safety(plan=plan, settings_payload=settings_payload)
        snapshot = build_context_snapshot(db=db, org_id=context.current_org_id)
        row = create_agent_run_row(
            db=db,
            org_id=context.current_org_id,
            agent_name=safe_plan.agent_name,
            agent_version=safe_plan.agent_version,
            trigger_type=payload.trigger_type,
            context_snapshot_json=snapshot.model_dump(),
            perception_json={
                "observations": [],
                "opportunities": [
                    {
                        "type": "objective",
                        "objective": safe_plan.objective,
                        "estimated_impact": 0.5,
                        "effort": "medium",
                    }
                ],
                "risks": [
                    {
                        "type": "plan",
                        "risk_tier": safe_plan.overall_risk_tier,
                        "note": safe_plan.rationale,
                    }
                ],
            },
            plan_json=safe_plan.model_dump(),
            status_value=AgentRunStatus.PROPOSED,
        )

        write_event(
            db=db,
            org_id=context.current_org_id,
            source="agent",
            channel="automations",
            event_type="AGENT_RUN_CREATED",
            payload_json={"agent_run_id": str(row.id), "agent_name": row.agent_name, "trigger_type": payload.trigger_type},
            actor_id=str(context.current_user_id),
        )
        write_event(
            db=db,
            org_id=context.current_org_id,
            source="agent",
            channel="automations",
            event_type="AGENT_PLAN_PROPOSED",
            payload_json={"agent_run_id": str(row.id), "overall_risk_tier": safe_plan.overall_risk_tier},
            actor_id=str(context.current_user_id),
        )

        if requires_approval(plan=safe_plan, settings_payload=settings_payload):
            db.add(
                Approval(
                    org_id=context.current_org_id,
                    entity_type=ApprovalEntityType.AGENT_RUN,
                    entity_id=row.id,
                    status=ApprovalStatus.PENDING,
                    requested_by=context.current_user_id,
                    notes=approval_block_reason(plan=safe_plan, settings_payload=settings_payload),
                )
            )
            row.error_json = {"approval_required": True, "reason": approval_block_reason(plan=safe_plan, settings_payload=settings_payload)}
            write_event(
                db=db,
                org_id=context.current_org_id,
                source="agent",
                channel="automations",
                event_type="AGENT_PLAN_APPROVAL_REQUESTED",
                payload_json={"agent_run_id": str(row.id), "overall_risk_tier": safe_plan.overall_risk_tier},
                actor_id=str(context.current_user_id),
            )
        else:
            row.status = AgentRunStatus.APPROVED
            try:
                from omniflow_worker.main import app as worker_app  # type: ignore

                worker_app.send_task("worker.agents.execute", args=[str(row.id)])
            except Exception:
                pass

        write_audit_log(
            db=db,
            context=context,
            action="agent.run.created",
            target_type="agent_run",
            target_id=str(row.id),
            metadata_json={
                "agent_name": row.agent_name,
                "trigger_type": payload.trigger_type,
                "overall_risk_tier": safe_plan.overall_risk_tier,
            },
        )

        if first_row is None:
            first_row = row

    db.commit()
    if first_row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="agent run creation failed")
    db.refresh(first_row)
    return _serialize_run_response(first_row)


@router.get("/runs", response_model=list[AgentRunListItem])
def list_runs(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[AgentRunListItem]:
    require_role(context, Role.ADMIN)
    stmt = org_scoped(
        select(AgentRun)
        .where(AgentRun.deleted_at.is_(None))
        .order_by(desc(AgentRun.created_at))
        .limit(limit)
        .offset(offset),
        context.current_org_id,
        AgentRun,
    )
    if status_filter:
        stmt = stmt.where(AgentRun.status == status_filter)
    rows = db.scalars(stmt).all()
    return [
        AgentRunListItem(
            id=row.id,
            org_id=row.org_id,
            agent_name=row.agent_name,
            trigger_type=row.trigger_type,
            status=row.status.value,
            started_at=row.started_at,
            finished_at=row.finished_at,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
def get_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AgentRunResponse:
    require_role(context, Role.ADMIN)
    row = db.scalar(
        org_scoped(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.deleted_at.is_(None)),
            context.current_org_id,
            AgentRun,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent run not found")
    return _serialize_run_response(row)


@router.post("/runs/{run_id}/execute", response_model=AgentRunResponse)
def execute_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AgentRunResponse:
    require_role(context, Role.ADMIN)
    row = db.scalar(
        org_scoped(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.deleted_at.is_(None)),
            context.current_org_id,
            AgentRun,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent run not found")
    if row.status == AgentRunStatus.BLOCKED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="agent run blocked")

    row.status = AgentRunStatus.APPROVED
    db.flush()
    try:
        from omniflow_worker.main import app as worker_app  # type: ignore

        worker_app.send_task("worker.agents.execute", args=[str(row.id)])
    except Exception:
        pass

    write_audit_log(
        db=db,
        context=context,
        action="agent.run.execute_requested",
        target_type="agent_run",
        target_id=str(row.id),
        metadata_json={"agent_name": row.agent_name},
    )
    db.commit()
    db.refresh(row)
    return _serialize_run_response(row)
