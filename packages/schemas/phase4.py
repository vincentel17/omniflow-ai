from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NormalizedMessage(BaseModel):
    external_message_id: str = Field(min_length=1, max_length=255)
    direction: str = Field(pattern="^(inbound|outbound)$")
    sender_ref: str = Field(min_length=1, max_length=255)
    sender_display: str = Field(min_length=1, max_length=255)
    body_text: str = Field(min_length=1, max_length=8000)
    body_raw_json: dict[str, object] = Field(default_factory=dict)
    created_at: datetime | None = None


class NormalizedThread(BaseModel):
    provider: str = Field(min_length=1, max_length=100)
    account_ref: str = Field(min_length=1, max_length=255)
    external_thread_id: str = Field(min_length=1, max_length=255)
    thread_type: str = Field(pattern="^(comment|dm|form|email|sms|other)$")
    subject: str | None = Field(default=None, max_length=500)
    participants_json: list[dict[str, object]] = Field(default_factory=list)
    last_message_at: datetime | None = None
    messages: list[NormalizedMessage] = Field(default_factory=list, max_length=200)


class ReplySuggestionJSON(BaseModel):
    intent: str = Field(pattern="^(answer|question|qualify|escalate)$")
    reply_text: str = Field(min_length=1, max_length=2000)
    followup_questions: list[str] = Field(default_factory=list, max_length=8)
    risk_tier: str = Field(pattern="^TIER_[0-4]$")
    required_disclaimers: list[str] = Field(default_factory=list, max_length=8)


class LeadFields(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    location: dict[str, object] = Field(default_factory=dict)


class LeadCaptureJSON(BaseModel):
    lead_fields: LeadFields = Field(default_factory=LeadFields)
    classification: str = Field(
        pattern="^(buyer|seller|renter|caregiver|client|other)$",
    )
    next_step_recommendation: str = Field(min_length=1, max_length=500)


class LeadScoreFactor(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    weight: float
    value: float
    explanation: str = Field(min_length=1, max_length=500)


class LeadScoreExplanationJSON(BaseModel):
    total: int = Field(ge=0, le=100)
    factors: list[LeadScoreFactor] = Field(default_factory=list, max_length=20)


class RoutingDecisionJSON(BaseModel):
    assigned_to_user_id: str = Field(min_length=1, max_length=36)
    rationale: str = Field(min_length=1, max_length=500)


class NurtureTaskJSON(BaseModel):
    type: str = Field(pattern="^(email|sms|call|task)$")
    due_in_minutes: int = Field(ge=1, le=10080)
    message_template_key: str = Field(min_length=1, max_length=100)
    message_body: str = Field(min_length=1, max_length=2000)


class NurturePlanJSON(BaseModel):
    tasks: list[NurtureTaskJSON] = Field(default_factory=list, max_length=20)
