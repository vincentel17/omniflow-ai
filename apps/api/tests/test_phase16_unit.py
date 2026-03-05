from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.services.agents import enforce_plan_safety
from packages.agents.supervisor import SupervisorAgent
from packages.schemas.phase16 import AgentContextSnapshotJSON, AgentPlanJSON


def _build_context(**overrides: object) -> AgentContextSnapshotJSON:
    base = AgentContextSnapshotJSON(
        org_id=str(uuid.uuid4()),
        active_pack_slug="generic",
        modes={"ai_mode": "mock", "connector_mode": "mock"},
        entitlements_summary={},
        compliance_mode="none",
        risk_limits={"max_auto_tier": 1, "max_steps_per_plan": 10},
        recent_events_summary={},
        inbox_summary={"open_threads": 0, "sla_breaches": 0},
        leads_summary={"new": 0, "qualified": 0, "stale": 0},
        optimization_signals={},
        presence_summary={"latest_score": 100},
        seo_summary={"drafts_pending": 1},
        reputation_summary={"unresponded_negative_reviews": 0},
        re_ops_summary={"overdue_checklists": 0},
    )
    return base.model_copy(update=overrides)


def test_phase16_schema_rejects_invalid_action_type() -> None:
    with pytest.raises(ValidationError):
        AgentPlanJSON.model_validate(
            {
                "plan_id": str(uuid.uuid4()),
                "agent_name": "InboxAgent",
                "agent_version": "1.0.0",
                "objective": "invalid action test",
                "steps": [
                    {
                        "step_id": "bad-step",
                        "action_type": "DELETE_EVERYTHING",
                        "target_ref": "lead:any",
                        "inputs_json": {},
                        "expected_outcome": "should fail",
                        "risk_tier": 1,
                        "requires_approval": False,
                    }
                ],
                "rationale": "schema enforcement",
                "rollback_strategy": "none",
                "limits": {"max_exec_time_seconds": 30, "max_steps": 1},
            }
        )


def test_phase16_supervisor_selects_inbox_for_sla_breach() -> None:
    supervisor = SupervisorAgent()
    context = _build_context(inbox_summary={"open_threads": 2, "sla_breaches": 3})
    selected = supervisor.select_agents(context)
    names = {agent.identity.name for agent in selected}
    assert "InboxAgent" in names


def test_phase16_conflict_resolution_deduplicates_publish_slots() -> None:
    supervisor = SupervisorAgent()
    plan_a = AgentPlanJSON.model_validate(
        {
            "plan_id": str(uuid.uuid4()),
            "agent_name": "GrowthAgent",
            "agent_version": "1.0.0",
            "objective": "slot-a",
            "steps": [
                {
                    "step_id": "slot-a",
                    "action_type": "SCHEDULE_PUBLISH",
                    "target_ref": "campaign:1",
                    "inputs_json": {"channel": "meta", "account_ref": "acct-1", "schedule_at": "2026-03-03T08:00:00Z"},
                    "expected_outcome": "publish",
                    "risk_tier": 1,
                    "requires_approval": False,
                }
            ],
            "rationale": "a",
            "rollback_strategy": "cancel",
            "limits": {"max_exec_time_seconds": 60, "max_steps": 1},
        }
    )
    plan_b = AgentPlanJSON.model_validate(
        {
            "plan_id": str(uuid.uuid4()),
            "agent_name": "SEOAgent",
            "agent_version": "1.0.0",
            "objective": "slot-b",
            "steps": [
                {
                    "step_id": "slot-b",
                    "action_type": "SCHEDULE_PUBLISH",
                    "target_ref": "campaign:2",
                    "inputs_json": {"channel": "meta", "account_ref": "acct-1", "schedule_at": "2026-03-03T08:00:00Z"},
                    "expected_outcome": "publish",
                    "risk_tier": 1,
                    "requires_approval": False,
                }
            ],
            "rationale": "b",
            "rollback_strategy": "cancel",
            "limits": {"max_exec_time_seconds": 60, "max_steps": 1},
        }
    )

    resolved = supervisor._resolve_conflicts([plan_a, plan_b])
    total_steps = sum(len(plan.steps) for plan in resolved)
    assert total_steps == 1


def test_phase16_safety_home_care_marks_health_targets_for_approval() -> None:
    plan = AgentPlanJSON.model_validate(
        {
            "plan_id": str(uuid.uuid4()),
            "agent_name": "InboxAgent",
            "agent_version": "1.0.0",
            "objective": "safety",
            "steps": [
                {
                    "step_id": "drop-me",
                    "action_type": "CREATE_TASK",
                    "target_ref": "lead:blocked",
                    "inputs_json": {},
                    "expected_outcome": "drop",
                    "risk_tier": 1,
                    "requires_approval": False,
                },
                {
                    "step_id": "keep-me",
                    "action_type": "DRAFT_REPLY",
                    "target_ref": "thread:patient-followup",
                    "inputs_json": {},
                    "expected_outcome": "draft",
                    "risk_tier": 1,
                    "requires_approval": False,
                },
            ],
            "rationale": "guardrails",
            "rollback_strategy": "cancel",
            "limits": {"max_exec_time_seconds": 90, "max_steps": 10},
        }
    )

    safe = enforce_plan_safety(
        plan=plan,
        settings_payload={
            "agent_max_steps_per_plan": 10,
            "agent_allowed_action_types_json": ["CREATE_TASK", "DRAFT_REPLY"],
            "agent_disallowed_targets_json": ["blocked"],
            "compliance_mode": "home_care",
        },
    )

    assert len(safe.steps) == 1
    assert safe.steps[0].step_id == "keep-me"
    assert safe.steps[0].requires_approval is True


def test_phase16_safety_blocks_ads_without_entitlement() -> None:
    plan = AgentPlanJSON.model_validate(
        {
            "plan_id": str(uuid.uuid4()),
            "agent_name": "GrowthAgent",
            "agent_version": "1.0.0",
            "objective": "ads draft",
            "steps": [
                {
                    "step_id": "ads-step",
                    "action_type": "ADS_CREATE_CAMPAIGN_DRAFT",
                    "target_ref": "campaign:new",
                    "inputs_json": {"provider": "meta", "daily_budget_usd": 5},
                    "expected_outcome": "create draft",
                    "risk_tier": 2,
                    "requires_approval": True,
                }
            ],
            "rationale": "ads",
            "rollback_strategy": "pause",
            "limits": {"max_exec_time_seconds": 60, "max_steps": 1},
        }
    )

    with pytest.raises(HTTPException):
        enforce_plan_safety(
            plan=plan,
            settings_payload={
                "agent_max_steps_per_plan": 10,
                "enable_ads_automation": False,
            },
            entitlements_summary={"ads_enabled": False},
            active_pack_slug="generic",
        )


def test_phase16_safety_blocks_real_estate_steps_when_pack_inactive() -> None:
    plan = AgentPlanJSON.model_validate(
        {
            "plan_id": str(uuid.uuid4()),
            "agent_name": "RealEstateOpsAgent",
            "agent_version": "1.0.0",
            "objective": "re ops",
            "steps": [
                {
                    "step_id": "re-step",
                    "action_type": "RE_CREATE_CHECKLIST_ITEM",
                    "target_ref": "deal:1",
                    "inputs_json": {"deal_id": str(uuid.uuid4()), "title": "Call escrow"},
                    "expected_outcome": "checklist",
                    "risk_tier": 1,
                    "requires_approval": False,
                }
            ],
            "rationale": "re",
            "rollback_strategy": "delete task",
            "limits": {"max_exec_time_seconds": 60, "max_steps": 1},
        }
    )

    with pytest.raises(HTTPException):
        enforce_plan_safety(
            plan=plan,
            settings_payload={"agent_max_steps_per_plan": 10},
            entitlements_summary={"allowed_verticals": ["generic"]},
            active_pack_slug="generic",
        )
