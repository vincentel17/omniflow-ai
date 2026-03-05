from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.agents import AgentOrchestrator
from packages.schemas.phase16 import AgentContextSnapshotJSON, AgentPlanJSON

from ..models import (
    AdBudgetRecommendation,
    AgentDefinition,
    AgentRun,
    AgentRunStatus,
    Event,
    InboxThread,
    InboxThreadStatus,
    Lead,
    LeadStatus,
    PostingOptimization,
    PredictiveLeadScore,
    PresenceAuditRun,
    REChecklistItem,
    REChecklistItemStatus,
    REDeal,
    REDealStatus,
    ReputationReview,
    SEOWorkItem,
    VerticalPack,
    WorkflowActionRun,
    WorkflowRun,
)
from .billing import get_billing_snapshot
from .org_settings import get_org_settings_payload


ALLOWED_AGENT_ACTION_TYPES: set[str] = {
    "CREATE_TASK",
    "ROUTE_LEAD",
    "APPLY_NURTURE_PLAN",
    "CREATE_CONTENT_DRAFT",
    "SCHEDULE_PUBLISH",
    "RUN_PRESENCE_AUDIT",
    "DRAFT_REPLY",
    "TAG_LEAD",
    "ADS_CREATE_CAMPAIGN_DRAFT",
    "ADS_REQUEST_ACTIVATION",
    "ADS_SYNC_METRICS",
    "ADS_PAUSE_CAMPAIGN",
    "RE_CREATE_CHECKLIST_ITEM",
    "RE_CREATE_CMA_DRAFT",
    "RE_CREATE_LISTING_PACKAGE",
    "WEBHOOK",
}

def _target_is_health_related(target_ref: str) -> bool:
    lowered = target_ref.lower()
    tokens = ("health", "patient", "diagnosis", "treatment", "hipaa", "phi")
    return any(token in lowered for token in tokens)

_DEFAULT_AGENT_DEFINITIONS: list[tuple[str, str, tuple[str, ...], dict[str, Any]]] = [
    ("SupervisorAgent", "1.0.0", ("generic", "real-estate", "home-care"), {"max_steps": 10}),
    ("InboxAgent", "1.0.0", ("generic", "real-estate", "home-care"), {"focus": "sla"}),
    ("GrowthAgent", "1.0.0", ("generic", "real-estate", "home-care"), {"focus": "pipeline"}),
    ("PresenceAgent", "1.0.0", ("generic", "real-estate", "home-care"), {"focus": "presence"}),
    ("SEOAgent", "1.0.0", ("generic", "real-estate", "home-care"), {"focus": "seo"}),
    ("ReputationAgent", "1.0.0", ("generic", "real-estate", "home-care"), {"focus": "reputation"}),
    ("RealEstateOpsAgent", "1.0.0", ("real-estate",), {"focus": "re-ops"}),
]


class AgentPlannerError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _current_pack(db: Session, org_id: uuid.UUID) -> str:
    row = db.scalar(select(VerticalPack).where(VerticalPack.org_id == org_id, VerticalPack.deleted_at.is_(None)))
    return row.pack_slug if row is not None else "generic"


def _risk_limits_from_settings(settings_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_auto_tier": int(settings_payload.get("agent_autonomy_max_tier", 1)),
        "max_plans_per_day": int(settings_payload.get("agent_max_plans_per_day", 3)),
        "max_steps_per_plan": int(settings_payload.get("agent_max_steps_per_plan", 10)),
        "cooldown_minutes": int(settings_payload.get("agent_cooldown_minutes", 60)),
        "allowed_action_types": list(settings_payload.get("agent_allowed_action_types_json", [])),
        "disallowed_targets": list(settings_payload.get("agent_disallowed_targets_json", [])),
    }


def _recent_events_summary(db: Session, org_id: uuid.UUID, hours: int = 24) -> dict[str, int]:
    since = _now() - timedelta(hours=hours)
    rows = db.execute(
        select(Event.type, func.count(Event.id))
        .where(Event.org_id == org_id, Event.deleted_at.is_(None), Event.created_at >= since)
        .group_by(Event.type)
    ).all()
    return {str(event_type): int(count) for event_type, count in rows}


def build_context_snapshot(db: Session, org_id: uuid.UUID) -> AgentContextSnapshotJSON:
    settings_payload = get_org_settings_payload(db=db, org_id=org_id)
    billing_snapshot = get_billing_snapshot(db=db, org_id=org_id)
    active_pack_slug = _current_pack(db, org_id)

    open_threads = int(
        db.scalar(
            select(func.count(InboxThread.id)).where(
                InboxThread.org_id == org_id,
                InboxThread.deleted_at.is_(None),
                InboxThread.status == InboxThreadStatus.OPEN,
            )
        )
        or 0
    )
    sla_breaches = int(_recent_events_summary(db, org_id, hours=24).get("SLA_BREACH", 0))

    new_leads = int(
        db.scalar(
            select(func.count(Lead.id)).where(
                Lead.org_id == org_id,
                Lead.deleted_at.is_(None),
                Lead.status == LeadStatus.NEW,
            )
        )
        or 0
    )
    qualified_leads = int(
        db.scalar(
            select(func.count(Lead.id)).where(
                Lead.org_id == org_id,
                Lead.deleted_at.is_(None),
                Lead.status == LeadStatus.QUALIFIED,
            )
        )
        or 0
    )
    stale_cutoff = _now() - timedelta(days=14)
    stale_leads = int(
        db.scalar(
            select(func.count(Lead.id)).where(
                Lead.org_id == org_id,
                Lead.deleted_at.is_(None),
                Lead.status == LeadStatus.NEW,
                Lead.updated_at < stale_cutoff,
            )
        )
        or 0
    )

    latest_predictive = db.scalar(
        select(PredictiveLeadScore)
        .where(PredictiveLeadScore.org_id == org_id, PredictiveLeadScore.deleted_at.is_(None))
        .order_by(PredictiveLeadScore.scored_at.desc())
        .limit(1)
    )
    latest_post_opt = db.scalar(
        select(PostingOptimization)
        .where(PostingOptimization.org_id == org_id, PostingOptimization.deleted_at.is_(None))
        .order_by(PostingOptimization.updated_at.desc())
        .limit(1)
    )

    latest_presence = db.scalar(
        select(PresenceAuditRun)
        .where(PresenceAuditRun.org_id == org_id, PresenceAuditRun.deleted_at.is_(None))
        .order_by(PresenceAuditRun.created_at.desc())
        .limit(1)
    )

    seo_drafts = int(
        db.scalar(
            select(func.count(SEOWorkItem.id)).where(
                SEOWorkItem.org_id == org_id,
                SEOWorkItem.deleted_at.is_(None),
            )
        )
        or 0
    )

    unresponded_negative_reviews = int(
        db.scalar(
            select(func.count(ReputationReview.id)).where(
                ReputationReview.org_id == org_id,
                ReputationReview.deleted_at.is_(None),
                ReputationReview.rating <= 2,
                ReputationReview.responded_at.is_(None),
            )
        )
        or 0
    )
    presence_score = 100.0
    if latest_presence is not None:
        summary_scores = latest_presence.summary_scores_json or {}
        overall_score = summary_scores.get("overall_score", 100.0)
        if isinstance(overall_score, int | float):
            presence_score = float(overall_score)
    re_ops_summary: dict[str, int] | None = None
    if active_pack_slug == "real-estate":
        open_deals = int(
            db.scalar(
                select(func.count(REDeal.id)).where(
                    REDeal.org_id == org_id,
                    REDeal.deleted_at.is_(None),
                    REDeal.status == REDealStatus.ACTIVE,
                )
            )
            or 0
        )
        overdue_checklists = int(
            db.scalar(
                select(func.count(REChecklistItem.id)).where(
                    REChecklistItem.org_id == org_id,
                    REChecklistItem.deleted_at.is_(None),
                    REChecklistItem.status == REChecklistItemStatus.OPEN,
                    REChecklistItem.due_at.is_not(None),
                    REChecklistItem.due_at < _now(),
                )
            )
            or 0
        )
        re_ops_summary = {"open_deals": open_deals, "overdue_checklists": overdue_checklists}
    return AgentContextSnapshotJSON(
        org_id=str(org_id),
        active_pack_slug=active_pack_slug,
        modes={
            "ai_mode": str(settings_payload.get("ai_mode", "mock")),
            "connector_mode": str(settings_payload.get("connector_mode", "mock")),
        },
        entitlements_summary=dict(billing_snapshot.entitlements),
        compliance_mode=str(settings_payload.get("compliance_mode", "none")),
        risk_limits=_risk_limits_from_settings(settings_payload),
        recent_events_summary=_recent_events_summary(db, org_id),
        inbox_summary={"open_threads": open_threads, "sla_breaches": sla_breaches},
        leads_summary={"new": new_leads, "qualified": qualified_leads, "stale": stale_leads},
        optimization_signals={
            "predictive_lead_lift": float(latest_predictive.score_probability) if latest_predictive is not None else 0.0,
            "best_post_hour": int(latest_post_opt.best_hour) if latest_post_opt is not None else 10,
            "best_post_day": int(latest_post_opt.best_day_of_week) if latest_post_opt is not None else 2,
            "post_confidence": float(latest_post_opt.confidence_score) if latest_post_opt is not None else 0.0,
        },
        presence_summary={
            "latest_score": presence_score,
        },
        seo_summary={"drafts_pending": seo_drafts},
        reputation_summary={"unresponded_negative_reviews": unresponded_negative_reviews},
        re_ops_summary=re_ops_summary,
    )


def assert_agent_controls(settings_payload: dict[str, Any]) -> None:
    if settings_payload.get("enable_agents") is not True:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="agents disabled for org")


def _vertical_allowed(entitlements_summary: dict[str, Any], vertical_slug: str) -> bool:
    allowed = entitlements_summary.get("allowed_verticals")
    if not isinstance(allowed, list) or not allowed:
        return vertical_slug == "generic"
    tokens = {str(item) for item in allowed}
    return "*" in tokens or vertical_slug in tokens


def enforce_plan_safety(
    plan: AgentPlanJSON,
    settings_payload: dict[str, Any],
    *,
    entitlements_summary: dict[str, Any] | None = None,
    active_pack_slug: str = "generic",
) -> AgentPlanJSON:
    max_steps = int(settings_payload.get("agent_max_steps_per_plan", 10))
    allowed = set(settings_payload.get("agent_allowed_action_types_json", []))
    disallowed_targets = [
        str(item) for item in settings_payload.get("agent_disallowed_targets_json", []) if isinstance(item, str)
    ]
    compliance_mode = str(settings_payload.get("compliance_mode", "none")).lower()
    entitlements = entitlements_summary if isinstance(entitlements_summary, dict) else {}

    filtered_steps = []
    for step in plan.steps[:max_steps]:
        if step.action_type not in ALLOWED_AGENT_ACTION_TYPES:
            continue
        if allowed and step.action_type not in allowed:
            continue
        if step.action_type.startswith("ADS_"):
            if entitlements.get("ads_enabled") is not True:
                continue
            if settings_payload.get("enable_ads_automation") is not True:
                continue
        if step.action_type.startswith("RE_"):
            if active_pack_slug != "real-estate":
                continue
            if not _vertical_allowed(entitlements, "real-estate"):
                continue
        target_lower = step.target_ref.lower()
        if any(token.lower() in target_lower for token in disallowed_targets):
            continue
        safe_step = step
        if compliance_mode == "home_care" and _target_is_health_related(step.target_ref):
            safe_step = step.model_copy(update={"requires_approval": True})
        filtered_steps.append(safe_step)

    if not filtered_steps:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent plan has no allowed steps")

    return plan.model_copy(update={"steps": filtered_steps})


def _seed_default_agent_definitions(db: Session) -> None:
    for name, version, supported_packs, config in _DEFAULT_AGENT_DEFINITIONS:
        row = db.scalar(
            select(AgentDefinition).where(
                AgentDefinition.name == name,
                AgentDefinition.version == version,
                AgentDefinition.deleted_at.is_(None),
            )
        )
        if row is None:
            db.add(
                AgentDefinition(
                    name=name,
                    version=version,
                    enabled=True,
                    supported_packs_json=list(supported_packs),
                    config_json=config,
                )
            )
    db.flush()


def list_agent_definitions(db: Session) -> list[AgentDefinition]:
    _seed_default_agent_definitions(db)
    rows = db.scalars(
        select(AgentDefinition)
        .where(AgentDefinition.deleted_at.is_(None))
        .order_by(AgentDefinition.name.asc(), AgentDefinition.version.desc())
    ).all()
    return list(rows)


def set_agent_definition_enabled(db: Session, *, name: str, enabled: bool) -> AgentDefinition:
    _seed_default_agent_definitions(db)
    row = db.scalar(
        select(AgentDefinition)
        .where(AgentDefinition.name == name, AgentDefinition.deleted_at.is_(None))
        .order_by(AgentDefinition.version.desc())
        .limit(1)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent definition not found")
    row.enabled = enabled
    db.flush()
    return row


def _enabled_agent_names(db: Session, active_pack_slug: str) -> set[str]:
    definitions = list_agent_definitions(db)
    enabled_names: set[str] = set()
    for row in definitions:
        if not row.enabled:
            continue
        supported = set(row.supported_packs_json or [])
        if active_pack_slug not in supported and "generic" not in supported:
            continue
        enabled_names.add(row.name)
    return enabled_names


def _mock_plans(snapshot: AgentContextSnapshotJSON) -> list[AgentPlanJSON]:
    orchestrator = AgentOrchestrator.build_default()
    plans = orchestrator.propose(snapshot)
    return [AgentPlanJSON.model_validate(plan.model_dump()) for plan in plans]


def _live_plans(snapshot: AgentContextSnapshotJSON) -> list[AgentPlanJSON]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise AgentPlannerError("OPENAI_API_KEY not set for AI live mode")

    model = os.getenv("OPENAI_AGENT_MODEL", "gpt-5-mini")
    prompt = (
        "Produce JSON only: an array of AgentPlanJSON objects. "
        "Use only allowed workflow action types, max 10 steps per plan, and include concise rationale/rollback strategy."
    )

    response = httpx.post(
        "https://api.openai.com/v1/responses",
        timeout=20,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(snapshot.model_dump(), separators=(",", ":")),
                        }
                    ],
                },
            ],
            "text": {"format": {"type": "json_object"}},
        },
    )
    response.raise_for_status()

    payload = response.json()
    output_text = ""
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text_value = content.get("text")
            if isinstance(text_value, str) and text_value.strip():
                output_text = text_value
                break
        if output_text:
            break
    if not output_text and isinstance(payload.get("output_text"), str):
        output_text = payload["output_text"]
    if not output_text:
        raise AgentPlannerError("live planner returned no output")

    decoded = json.loads(output_text)
    plan_items = decoded.get("plans") if isinstance(decoded, dict) else decoded
    if not isinstance(plan_items, list):
        raise AgentPlannerError("live planner returned invalid structure")
    return [AgentPlanJSON.model_validate(item) for item in plan_items]


def plans_for_org(db: Session, org_id: uuid.UUID) -> list[AgentPlanJSON]:
    snapshot = build_context_snapshot(db=db, org_id=org_id)
    settings_payload = get_org_settings_payload(db=db, org_id=org_id)
    ai_mode = str(settings_payload.get("ai_mode", "mock")).lower()

    if ai_mode == "live":
        try:
            candidate_plans = _live_plans(snapshot)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"agent live planning unavailable: {exc}") from exc
    else:
        candidate_plans = _mock_plans(snapshot)

    enabled_names = _enabled_agent_names(db=db, active_pack_slug=snapshot.active_pack_slug)
    return [plan for plan in candidate_plans if plan.agent_name in enabled_names]


def serialize_agent_run(row: AgentRun) -> dict[str, object]:
    return {
        "id": row.id,
        "org_id": row.org_id,
        "agent_name": row.agent_name,
        "agent_version": row.agent_version,
        "trigger_type": row.trigger_type,
        "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        "context_snapshot_json": row.context_snapshot_json,
        "perception_json": row.perception_json,
        "plan_json": row.plan_json,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "error_json": row.error_json,
        "created_at": row.created_at,
    }


def create_agent_run_row(
    db: Session,
    *,
    org_id: uuid.UUID,
    agent_name: str,
    agent_version: str,
    trigger_type: str,
    context_snapshot_json: dict[str, Any],
    perception_json: dict[str, Any],
    plan_json: dict[str, Any],
    status_value: AgentRunStatus,
) -> AgentRun:
    row = AgentRun(
        org_id=org_id,
        agent_name=agent_name,
        agent_version=agent_version,
        trigger_type=trigger_type,
        status=status_value,
        context_snapshot_json=context_snapshot_json,
        perception_json=perception_json,
        plan_json=plan_json,
        started_at=_now(),
        error_json={},
    )
    db.add(row)
    db.flush()
    return row


def enforce_rate_limits(db: Session, org_id: uuid.UUID, settings_payload: dict[str, Any]) -> None:
    now = _now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    plans_today = int(
        db.scalar(
            select(func.count(AgentRun.id)).where(
                AgentRun.org_id == org_id,
                AgentRun.deleted_at.is_(None),
                AgentRun.created_at >= day_start,
            )
        )
        or 0
    )
    max_plans_per_day = int(settings_payload.get("agent_max_plans_per_day", 3))
    if plans_today >= max_plans_per_day:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="agent max plans per day reached")

    cooldown_minutes = int(settings_payload.get("agent_cooldown_minutes", 60))
    if cooldown_minutes <= 0:
        return
    latest_run = db.scalar(
        select(AgentRun)
        .where(AgentRun.org_id == org_id, AgentRun.deleted_at.is_(None))
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    if latest_run is None:
        return
    if latest_run.created_at >= now - timedelta(minutes=cooldown_minutes):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="agent cooldown active")


def requires_approval(plan: AgentPlanJSON, settings_payload: dict[str, Any]) -> bool:
    max_tier = int(settings_payload.get("agent_autonomy_max_tier", 1))
    if plan.overall_risk_tier > max_tier:
        return True
    return any(bool(step.requires_approval) for step in plan.steps)


def approval_block_reason(plan: AgentPlanJSON, settings_payload: dict[str, Any]) -> str:
    max_tier = int(settings_payload.get("agent_autonomy_max_tier", 1))
    if plan.overall_risk_tier > max_tier:
        return f"overall risk tier {plan.overall_risk_tier} exceeds max {max_tier}"
    if any(bool(step.requires_approval) for step in plan.steps):
        return "plan contains approval-gated step"
    return "approval required"


def summarize_agent_metrics(db: Session, org_id: uuid.UUID, *, days: int = 7) -> dict[str, int]:
    since = _now() - timedelta(days=days)
    total_runs = int(
        db.scalar(
            select(func.count(AgentRun.id)).where(
                AgentRun.org_id == org_id,
                AgentRun.deleted_at.is_(None),
                AgentRun.created_at >= since,
            )
        )
        or 0
    )
    workflow_runs = int(
        db.scalar(
            select(func.count(WorkflowRun.id)).where(
                WorkflowRun.org_id == org_id,
                WorkflowRun.deleted_at.is_(None),
                WorkflowRun.created_at >= since,
            )
        )
        or 0
    )
    workflow_actions = int(
        db.scalar(
            select(func.count(WorkflowActionRun.id)).where(
                WorkflowActionRun.org_id == org_id,
                WorkflowActionRun.deleted_at.is_(None),
                WorkflowActionRun.created_at >= since,
            )
        )
        or 0
    )
    budget_recs = int(
        db.scalar(
            select(func.count(AdBudgetRecommendation.id)).where(
                AdBudgetRecommendation.org_id == org_id,
                AdBudgetRecommendation.deleted_at.is_(None),
                AdBudgetRecommendation.created_at >= since,
            )
        )
        or 0
    )
    return {
        "agent_runs": total_runs,
        "workflow_runs": workflow_runs,
        "workflow_actions": workflow_actions,
        "ad_budget_recommendations": budget_recs,
    }



