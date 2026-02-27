from __future__ import annotations

from typing import Any

from .schema import (
    ActionRequest,
    ActionType,
    ConditionType,
    EvaluationContext,
    EvaluationResult,
    EventContext,
    WorkflowCondition,
    WorkflowDefinitionJSON,
)

ACTION_RISK_REGISTRY: dict[ActionType, int] = {
    ActionType.CREATE_TASK: 0,
    ActionType.ROUTE_LEAD: 1,
    ActionType.APPLY_NURTURE_PLAN: 1,
    ActionType.CREATE_CONTENT_DRAFT: 1,
    ActionType.SCHEDULE_PUBLISH: 2,
    ActionType.RUN_PRESENCE_AUDIT: 0,
    ActionType.DRAFT_REPLY: 1,
    ActionType.TAG_LEAD: 0,
    ActionType.WEBHOOK: 3,
}


def action_risk_tier(action_type: ActionType) -> int:
    return ACTION_RISK_REGISTRY.get(action_type, 2)


def _payload_lookup(payload: dict[str, Any], key: str | None) -> Any:
    if not key:
        return None
    current: Any = payload
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _evaluate_condition(condition: WorkflowCondition, event: EventContext, context: EvaluationContext) -> bool:
    if condition.type == ConditionType.EVENT_TYPE_EQUALS:
        return event.type == str(condition.value)
    if condition.type == ConditionType.EVENT_CHANNEL_EQUALS:
        return event.channel == str(condition.value)
    if condition.type == ConditionType.EVENT_PAYLOAD_MATCH:
        actual = _payload_lookup(event.payload_json, condition.key)
        return actual == condition.value
    if condition.type == ConditionType.RISK_TIER_LTE:
        max_tier = condition.max_tier if condition.max_tier is not None else 0
        return context.risk_tier <= max_tier
    if condition.type == ConditionType.ORG_FLAG_ENABLED:
        flag_key = condition.flag_key or ""
        return context.org_settings.get(flag_key) is True
    if condition.type == ConditionType.BUSINESS_HOURS:
        start_hour = condition.start_hour if condition.start_hour is not None else 9
        end_hour = condition.end_hour if condition.end_hour is not None else 17
        if start_hour <= end_hour:
            return start_hour <= context.local_hour <= end_hour
        return context.local_hour >= start_hour or context.local_hour <= end_hour
    if condition.type == ConditionType.VERTICAL_PACK_EQUALS:
        return context.vertical_pack == (condition.pack_slug or str(condition.value or ""))
    return False


def evaluate_workflow(
    definition: WorkflowDefinitionJSON,
    event: EventContext,
    context: EvaluationContext,
) -> EvaluationResult:
    if not definition.enabled:
        return EvaluationResult(matched=False, skipped_reason="workflow_disabled")
    if definition.trigger.type.value == "EVENT" and definition.trigger.event_type != event.type:
        return EvaluationResult(matched=False, skipped_reason="trigger_mismatch")

    for condition in definition.conditions:
        if not _evaluate_condition(condition, event, context):
            return EvaluationResult(matched=False, skipped_reason=f"condition_failed:{condition.type.value}")

    action_requests: list[ActionRequest] = []
    for action in definition.actions:
        risk_tier = action_risk_tier(action.type)
        force_approval = action.type in definition.autonomy.require_approval_for_actions
        requires_approval = force_approval or risk_tier > definition.autonomy.max_auto_tier
        action_requests.append(
            ActionRequest(
                action_type=action.type,
                params_json=action.params_json,
                risk_tier=risk_tier,
                requires_approval=requires_approval,
            )
        )

    overall_risk_tier = max((row.risk_tier for row in action_requests), default=0)
    return EvaluationResult(matched=True, overall_risk_tier=overall_risk_tier, actions=action_requests)