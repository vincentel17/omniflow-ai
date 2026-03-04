from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


ActionTypeLiteral = Literal[
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
]


class AgentContextSnapshotJSON(BaseModel):
    org_id: str
    active_pack_slug: str = "generic"
    modes: dict[str, str] = Field(default_factory=dict)
    entitlements_summary: dict[str, Any] = Field(default_factory=dict)
    compliance_mode: str = "none"
    risk_limits: dict[str, Any] = Field(default_factory=dict)
    recent_events_summary: dict[str, int] = Field(default_factory=dict)
    inbox_summary: dict[str, int] = Field(default_factory=dict)
    leads_summary: dict[str, int] = Field(default_factory=dict)
    optimization_signals: dict[str, Any] = Field(default_factory=dict)
    presence_summary: dict[str, Any] = Field(default_factory=dict)
    seo_summary: dict[str, Any] = Field(default_factory=dict)
    reputation_summary: dict[str, Any] = Field(default_factory=dict)
    re_ops_summary: dict[str, Any] | None = None


class AgentObservation(BaseModel):
    type: str
    value: dict[str, Any] = Field(default_factory=dict)


class AgentOpportunity(BaseModel):
    type: str
    estimated_impact: float = Field(default=0.0, ge=0, le=100)
    estimated_effort: float = Field(default=0.0, ge=0, le=100)
    details: dict[str, Any] = Field(default_factory=dict)


class AgentRisk(BaseModel):
    type: str
    severity: int = Field(default=0, ge=0, le=5)
    details: dict[str, Any] = Field(default_factory=dict)


class AgentPerceptionJSON(BaseModel):
    observations: list[AgentObservation] = Field(default_factory=list)
    opportunities: list[AgentOpportunity] = Field(default_factory=list)
    risks: list[AgentRisk] = Field(default_factory=list)


class AgentPlanStepJSON(BaseModel):
    step_id: str
    action_type: ActionTypeLiteral
    target_ref: str
    inputs_json: dict[str, Any] = Field(default_factory=dict)
    expected_outcome: str
    risk_tier: int = Field(default=0, ge=0, le=5)
    requires_approval: bool = False


class AgentPlanLimitsJSON(BaseModel):
    max_exec_time_seconds: int = Field(default=300, ge=1, le=7200)
    max_steps: int = Field(default=10, ge=1, le=50)


class AgentPlanJSON(BaseModel):
    plan_id: str
    agent_name: str
    agent_version: str
    objective: str
    steps: list[AgentPlanStepJSON] = Field(default_factory=list, min_length=1, max_length=50)
    overall_risk_tier: int = Field(default=0, ge=0, le=5)
    rationale: str
    rollback_strategy: str
    limits: AgentPlanLimitsJSON = Field(default_factory=AgentPlanLimitsJSON)

    @model_validator(mode="after")
    def derive_overall_risk(self) -> "AgentPlanJSON":
        if self.steps:
            self.overall_risk_tier = max(int(step.risk_tier) for step in self.steps)
        return self


class AgentDecisionRecordJSON(BaseModel):
    executed: list[dict[str, Any]] = Field(default_factory=list)
    blocked: list[dict[str, Any]] = Field(default_factory=list)
    approvals_created: list[str] = Field(default_factory=list)

