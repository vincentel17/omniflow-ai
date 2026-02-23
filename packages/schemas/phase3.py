from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, HttpUrl


class CampaignPlanPost(BaseModel):
    channel: str = Field(min_length=1, max_length=100)
    account_ref: str = Field(min_length=1, max_length=255)
    hook: str = Field(min_length=1, max_length=280)
    value_points: list[str] = Field(default_factory=list, max_length=5)
    cta: str = Field(min_length=1, max_length=280)
    compliance_notes: list[str] = Field(default_factory=list)


class CampaignPlanJSON(BaseModel):
    week_start: date
    objectives: list[str] = Field(default_factory=list, max_length=5)
    themes: list[str] = Field(default_factory=list, max_length=5)
    channels: list[str] = Field(default_factory=list, max_length=8)
    posts: list[CampaignPlanPost] = Field(default_factory=list, max_length=30)


class ContentItemJSON(BaseModel):
    channel: str = Field(min_length=1, max_length=100)
    caption: str = Field(min_length=1, max_length=2200)
    hashtags: list[str] = Field(default_factory=list, max_length=15)
    cta: str = Field(min_length=1, max_length=280)
    link_url: HttpUrl | None = None
    media_prompt: str | None = Field(default=None, max_length=1000)
    disclaimers: list[str] = Field(default_factory=list, max_length=8)


class ApprovalDecision(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    notes: str | None = Field(default=None, max_length=1000)
