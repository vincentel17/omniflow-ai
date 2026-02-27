from __future__ import annotations

import pytest

from app.services.workflows import event_depth
from packages.workflows import EvaluationContext, EventContext, WorkflowDefinitionJSON, evaluate_workflow


def test_phase10_schema_rejects_event_trigger_without_event_type() -> None:
    with pytest.raises(Exception):
        WorkflowDefinitionJSON.model_validate(
            {
                "id": "bad-trigger",
                "name": "Bad Trigger",
                "enabled": True,
                "trigger": {"type": "EVENT"},
                "conditions": [],
                "actions": [{"type": "RUN_PRESENCE_AUDIT", "params_json": {}}],
            }
        )


def test_phase10_condition_evaluation_business_hours_and_pack() -> None:
    definition = WorkflowDefinitionJSON.model_validate(
        {
            "id": "hours-pack",
            "name": "Hours + Pack",
            "enabled": True,
            "trigger": {"type": "EVENT", "event_type": "LEAD_CREATED"},
            "conditions": [
                {"type": "business_hours", "start_hour": 9, "end_hour": 17},
                {"type": "vertical_pack_equals", "pack_slug": "real-estate"},
                {"type": "event.payload_match", "key": "classification", "value": "buyer"},
            ],
            "actions": [{"type": "CREATE_TASK", "params_json": {"title": "Contact lead"}}],
        }
    )

    matched = evaluate_workflow(
        definition=definition,
        event=EventContext(type="LEAD_CREATED", channel="inbox", payload_json={"classification": "buyer"}),
        context=EvaluationContext(risk_tier=1, org_settings={}, vertical_pack="real-estate", local_hour=10),
    )
    assert matched.matched is True
    assert matched.overall_risk_tier == 0

    outside_hours = evaluate_workflow(
        definition=definition,
        event=EventContext(type="LEAD_CREATED", channel="inbox", payload_json={"classification": "buyer"}),
        context=EvaluationContext(risk_tier=1, org_settings={}, vertical_pack="real-estate", local_hour=22),
    )
    assert outside_hours.matched is False


def test_phase10_loop_guard_depth_parser() -> None:
    assert event_depth({}) == 0
    assert event_depth({"workflow_origin": {"depth": 2}}) == 2
    assert event_depth({"workflow_origin": {"depth": -1}}) == 0


def test_phase10_risk_gating_marks_high_tier_action_for_approval() -> None:
    definition = WorkflowDefinitionJSON.model_validate(
        {
            "id": "risk-gating",
            "name": "Risk Gating",
            "enabled": True,
            "trigger": {"type": "EVENT", "event_type": "LISTING_PACKAGE_APPROVED"},
            "conditions": [{"type": "event.type_equals", "value": "LISTING_PACKAGE_APPROVED"}],
            "actions": [{"type": "SCHEDULE_PUBLISH", "params_json": {}}],
            "autonomy": {"max_auto_tier": 1, "require_approval_for_actions": []},
        }
    )

    result = evaluate_workflow(
        definition=definition,
        event=EventContext(type="LISTING_PACKAGE_APPROVED", channel="content", payload_json={}),
        context=EvaluationContext(risk_tier=0, org_settings={}, vertical_pack="generic", local_hour=12),
    )

    assert result.matched is True
    assert len(result.actions) == 1
    assert result.actions[0].risk_tier == 2
    assert result.actions[0].requires_approval is True
