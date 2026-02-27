from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class TriggerType(StrEnum):
    EVENT = "EVENT"
    SCHEDULE = "SCHEDULE"


class ConditionType(StrEnum):
    EVENT_TYPE_EQUALS = "event.type_equals"
    EVENT_CHANNEL_EQUALS = "event.channel_equals"
    EVENT_PAYLOAD_MATCH = "event.payload_match"
    RISK_TIER_LTE = "risk_tier_lte"
    ORG_FLAG_ENABLED = "org_flag_enabled"
    BUSINESS_HOURS = "business_hours"
    VERTICAL_PACK_EQUALS = "vertical_pack_equals"


class ActionType(StrEnum):
    CREATE_TASK = "CREATE_TASK"
    ROUTE_LEAD = "ROUTE_LEAD"
    APPLY_NURTURE_PLAN = "APPLY_NURTURE_PLAN"
    CREATE_CONTENT_DRAFT = "CREATE_CONTENT_DRAFT"
    SCHEDULE_PUBLISH = "SCHEDULE_PUBLISH"
    RUN_PRESENCE_AUDIT = "RUN_PRESENCE_AUDIT"
    DRAFT_REPLY = "DRAFT_REPLY"
    TAG_LEAD = "TAG_LEAD"
    WEBHOOK = "WEBHOOK"


class WorkflowTrigger(BaseModel):
    type: TriggerType
    event_type: str | None = None
    cron: str | None = None

    @model_validator(mode="after")
    def validate_by_type(self) -> "WorkflowTrigger":
        if self.type == TriggerType.EVENT and not self.event_type:
            raise ValueError("event_type is required for EVENT trigger")
        if self.type == TriggerType.SCHEDULE and not self.cron:
            raise ValueError("cron is required for SCHEDULE trigger")
        return self


class WorkflowCondition(BaseModel):
    type: ConditionType
    key: str | None = None
    value: Any | None = None
    max_tier: int | None = Field(default=None, ge=0, le=4)
    flag_key: str | None = None
    start_hour: int | None = Field(default=None, ge=0, le=23)
    end_hour: int | None = Field(default=None, ge=0, le=23)
    pack_slug: str | None = None


class WorkflowAction(BaseModel):
    type: ActionType
    params_json: dict[str, Any] = Field(default_factory=dict)


class WorkflowAutonomy(BaseModel):
    max_auto_tier: int = Field(default=1, ge=0, le=4)
    require_approval_for_actions: list[ActionType] = Field(default_factory=list)


class WorkflowDefinitionJSON(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=255)
    enabled: bool = True
    trigger: WorkflowTrigger
    conditions: list[WorkflowCondition] = Field(default_factory=list)
    actions: list[WorkflowAction] = Field(default_factory=list, min_length=1, max_length=20)
    max_runs_per_day: int = Field(default=100, ge=1, le=1000)
    cooldown_minutes: int = Field(default=0, ge=0, le=1440)
    autonomy: WorkflowAutonomy = Field(default_factory=WorkflowAutonomy)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def managed_vertical_pack(self) -> str | None:
        value = self.metadata.get("vertical_pack")
        return value if isinstance(value, str) and value else None


class EventContext(BaseModel):
    type: str
    channel: str
    payload_json: dict[str, Any] = Field(default_factory=dict)


class EvaluationContext(BaseModel):
    risk_tier: int = Field(default=0, ge=0, le=4)
    org_settings: dict[str, Any] = Field(default_factory=dict)
    vertical_pack: str = "generic"
    local_hour: int = Field(default=12, ge=0, le=23)


class ActionRequest(BaseModel):
    action_type: ActionType
    params_json: dict[str, Any] = Field(default_factory=dict)
    risk_tier: int = Field(default=0, ge=0, le=4)
    requires_approval: bool = False


class EvaluationResult(BaseModel):
    matched: bool
    skipped_reason: str | None = None
    overall_risk_tier: int = Field(default=0, ge=0, le=4)
    actions: list[ActionRequest] = Field(default_factory=list)


ConditionOperator = Literal["eq", "contains"]