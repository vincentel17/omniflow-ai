from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.workflows import EvaluationContext, EventContext, WorkflowDefinitionJSON, evaluate_workflow

from ..models import Event, VerticalPack, Workflow, WorkflowActionRun, WorkflowRun, WorkflowTriggerType
from .org_settings import get_org_settings_payload
from .verticals import load_pack_file


def sanitize_error_message(value: str) -> str:
    lowered = value.lower()
    if "token" in lowered or "authorization" in lowered or "bearer" in lowered:
        return "redacted-sensitive-error"
    return value[:500]


def current_vertical_pack(db: Session, org_id: uuid.UUID) -> str:
    row = db.scalar(select(VerticalPack).where(VerticalPack.org_id == org_id, VerticalPack.deleted_at.is_(None)))
    return row.pack_slug if row is not None else "generic"


def parse_workflow_definition(raw: dict[str, Any]) -> WorkflowDefinitionJSON:
    try:
        return WorkflowDefinitionJSON.model_validate(raw)
    except Exception as exc:  # pragma: no cover - error mapping
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"invalid workflow definition: {exc}") from exc


def evaluate_definition(
    *,
    definition_json: dict[str, Any],
    event_type: str,
    channel: str,
    payload_json: dict[str, Any],
    risk_tier: int,
    org_settings: dict[str, Any],
    vertical_pack: str,
    local_hour: int,
):
    definition = parse_workflow_definition(definition_json)
    return evaluate_workflow(
        definition=definition,
        event=EventContext(type=event_type, channel=channel, payload_json=payload_json),
        context=EvaluationContext(
            risk_tier=risk_tier,
            org_settings=org_settings,
            vertical_pack=vertical_pack,
            local_hour=local_hour,
        ),
    )


def action_idempotency_key(org_id: uuid.UUID, action_run: WorkflowActionRun) -> str:
    return f"{org_id}:{action_run.workflow_run_id}:{action_run.action_type}:{action_run.id}"


def event_depth(payload_json: dict[str, Any]) -> int:
    origin = payload_json.get("workflow_origin")
    if not isinstance(origin, dict):
        return 0
    depth = origin.get("depth")
    if isinstance(depth, int) and depth >= 0:
        return depth
    return 0


def set_workflow_origin(payload_json: dict[str, Any], run_id: uuid.UUID, depth: int) -> dict[str, Any]:
    cloned = dict(payload_json)
    cloned["workflow_origin"] = {"workflow_run_id": str(run_id), "depth": depth}
    return cloned


def org_automation_limits(settings_payload: dict[str, Any]) -> dict[str, int]:
    return {
        "max_actions_per_event": int(settings_payload.get("max_actions_per_event", 10)),
        "max_workflow_runs_per_hour": int(settings_payload.get("max_workflow_runs_per_hour", 30)),
        "max_depth": int(settings_payload.get("max_depth", 3)),
        "default_autonomy_max_tier": int(settings_payload.get("default_autonomy_max_tier", 1)),
        "business_hours_start_hour": int(settings_payload.get("business_hours_start_hour", 9)),
        "business_hours_end_hour": int(settings_payload.get("business_hours_end_hour", 17)),
    }


def _runtime_workflows_from_pack(pack_slug: str) -> list[dict[str, Any]]:
    try:
        payload = load_pack_file(pack_slug, "workflows.runtime.json")
        rows = payload.get("workflows") if isinstance(payload, dict) else None
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    except FileNotFoundError:
        pass

    payload = load_pack_file(pack_slug, "workflows.json")
    rows = payload.get("workflows") if isinstance(payload, dict) else None
    out: list[dict[str, Any]] = []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("definition_json"), dict):
                out.append(row)
    return out


def seed_pack_workflows(db: Session, org_id: uuid.UUID, pack_slug: str) -> int:
    inserted = 0
    for row in _runtime_workflows_from_pack(pack_slug):
        definition_json = row.get("definition_json")
        if not isinstance(definition_json, dict):
            continue
        definition = parse_workflow_definition(definition_json)
        key = str(row.get("key") or definition.id)
        existing = db.scalar(
            select(Workflow).where(
                Workflow.org_id == org_id,
                Workflow.key == key,
                Workflow.deleted_at.is_(None),
            )
        )
        if existing is not None:
            if existing.managed_by_pack:
                existing.name = str(row.get("name") or definition.name)
                existing.enabled = bool(row.get("enabled", existing.enabled))
                existing.definition_json = definition_json
            continue

        workflow = Workflow(
            org_id=org_id,
            key=key,
            name=str(row.get("name") or definition.name),
            enabled=bool(row.get("enabled", True)),
            trigger_type=WorkflowTriggerType(str(definition.trigger.type.value).lower()),
            definition_json=definition_json,
            managed_by_pack=bool(row.get("managed_by_pack", True)),
        )
        db.add(workflow)
        inserted += 1
    db.flush()
    return inserted


def load_event(db: Session, event_id: uuid.UUID, org_id: uuid.UUID | None = None) -> Event | None:
    stmt = select(Event).where(Event.id == event_id, Event.deleted_at.is_(None))
    if org_id is not None:
        stmt = stmt.where(Event.org_id == org_id)
    return db.scalar(stmt)


def _within_window(hour: int, start_hour: int, end_hour: int) -> bool:
    if start_hour <= end_hour:
        return start_hour <= hour <= end_hour
    return hour >= start_hour or hour <= end_hour


def local_hour_for_org(settings_payload: dict[str, Any], now: datetime | None = None) -> int:
    now_dt = now or datetime.utcnow()
    hour = now_dt.hour
    start_hour = int(settings_payload.get("business_hours_start_hour", 9))
    end_hour = int(settings_payload.get("business_hours_end_hour", 17))
    if _within_window(hour, start_hour, end_hour):
        return hour
    return hour


def settings_for_org(db: Session, org_id: uuid.UUID) -> dict[str, Any]:
    return get_org_settings_payload(db=db, org_id=org_id)


def serialize_workflow(workflow: Workflow) -> dict[str, Any]:
    return {
        "id": workflow.id,
        "org_id": workflow.org_id,
        "key": workflow.key,
        "name": workflow.name,
        "enabled": workflow.enabled,
        "trigger_type": workflow.trigger_type.value if hasattr(workflow.trigger_type, "value") else str(workflow.trigger_type),
        "managed_by_pack": workflow.managed_by_pack,
        "definition_json": workflow.definition_json,
        "created_at": workflow.created_at,
        "updated_at": workflow.updated_at,
    }


def serialize_workflow_run(run: WorkflowRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "org_id": run.org_id,
        "workflow_id": run.workflow_id,
        "trigger_event_id": run.trigger_event_id,
        "status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "summary_json": run.summary_json,
        "error_json": run.error_json,
        "loop_guard_hits": run.loop_guard_hits,
        "created_at": run.created_at,
    }


def serialize_action_run(action_run: WorkflowActionRun) -> dict[str, Any]:
    return {
        "id": action_run.id,
        "org_id": action_run.org_id,
        "workflow_run_id": action_run.workflow_run_id,
        "action_type": action_run.action_type,
        "status": action_run.status.value if hasattr(action_run.status, "value") else str(action_run.status),
        "idempotency_key": action_run.idempotency_key,
        "input_json": action_run.input_json,
        "output_json": action_run.output_json,
        "error_json": action_run.error_json,
        "created_at": action_run.created_at,
    }

