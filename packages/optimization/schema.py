from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ModelStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPERIMENTAL = "experimental"
    DEGRADED = "degraded"


class FeatureVector(BaseModel):
    org_id: str
    lead_id: str | None = None
    campaign_id: str | None = None
    feature_json: dict[str, float] = Field(default_factory=dict)


class ModelDescriptor(BaseModel):
    name: str
    version: str
    trained_at: datetime
    training_window: str
    metrics_json: dict[str, float] = Field(default_factory=dict)
    status: ModelStatus = ModelStatus.INACTIVE


class PredictiveLeadScoreResult(BaseModel):
    score_probability: float = Field(ge=0.0, le=1.0)
    feature_importance_json: dict[str, float] = Field(default_factory=dict)
    predicted_stage_probability_json: dict[str, float] = Field(default_factory=dict)
    explanation: str


class PostingOptimizationResult(BaseModel):
    channel: str
    best_day_of_week: int = Field(ge=0, le=6)
    best_hour: int = Field(ge=0, le=23)
    confidence_score: float = Field(ge=0.0, le=1.0)
    explanation: str


class NurtureRecommendationResult(BaseModel):
    recommended_delays_minutes: list[int] = Field(default_factory=list)
    explanation: str


class AdBudgetRecommendationResult(BaseModel):
    recommended_daily_budget: float = Field(ge=0.0)
    projected_cpl: float = Field(ge=0.0)
    reasoning_json: dict[str, float | str] = Field(default_factory=dict)
    explanation: str


class NextBestActionResult(BaseModel):
    action_type: str
    rationale: str
    expected_uplift: float = Field(ge=0.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
