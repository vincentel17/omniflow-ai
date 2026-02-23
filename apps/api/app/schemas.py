from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, HttpUrl

from .models import (
    ApprovalStatus,
    BrandProfile,
    CampaignPlanStatus,
    ContentItemStatus,
    PublishJobStatus,
    RiskTier,
    Role,
)


class OrgCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime


class MembershipUpsertRequest(BaseModel):
    org_id: uuid.UUID
    user_id: uuid.UUID
    role: Role


class MembershipResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    role: Role
    created_at: datetime


class VerticalPackSelectRequest(BaseModel):
    pack_slug: str = Field(min_length=1, max_length=100)


class VerticalPackResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    pack_slug: str
    created_at: datetime


class EventCreateRequest(BaseModel):
    source: str
    channel: str
    campaign_id: str | None = None
    content_id: str | None = None
    lead_id: str | None = None
    actor_id: str | None = None
    type: str
    payload_json: dict[str, object] = Field(default_factory=dict)


class EventResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    source: str
    channel: str
    campaign_id: str | None = None
    content_id: str | None = None
    lead_id: str | None = None
    actor_id: str | None = None
    type: str
    payload_json: dict[str, object]
    created_at: datetime


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    action: str
    target_type: str
    target_id: str
    risk_tier: RiskTier
    metadata_json: dict[str, object]
    created_at: datetime


class CampaignPlanCreateRequest(BaseModel):
    week_start_date: date
    channels: list[str] = Field(default_factory=list, max_length=8)
    objectives: list[str] = Field(default_factory=list, max_length=5)
    vertical_pack_slug: str | None = Field(default=None, max_length=100)
    brand_profile_id: uuid.UUID | None = None


class CampaignPlanResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    vertical_pack_slug: str
    week_start_date: date
    status: CampaignPlanStatus
    created_by: uuid.UUID
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    plan_json: dict[str, object]
    metadata_json: dict[str, object]
    created_at: datetime


class CampaignPlanGenerateContentResponse(BaseModel):
    items_created: int


class ContentListItemResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    campaign_plan_id: uuid.UUID
    channel: str
    account_ref: str
    status: ContentItemStatus
    risk_tier: RiskTier
    policy_warnings_json: list[str]
    created_at: datetime


class ContentDetailResponse(ContentListItemResponse):
    content_json: dict[str, object]
    text_rendered: str
    media_refs_json: list[str]
    link_url: str | None
    tags_json: list[str]


class ApprovalDecisionRequest(BaseModel):
    status: ApprovalStatus
    notes: str | None = Field(default=None, max_length=1000)


class ContentScheduleRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=100)
    account_ref: str = Field(min_length=1, max_length=255)
    schedule_at: datetime | None = None


class PublishJobCreateRequest(ContentScheduleRequest):
    content_item_id: uuid.UUID


class PublishJobResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    content_item_id: uuid.UUID
    provider: str
    account_ref: str
    schedule_at: datetime | None
    status: PublishJobStatus
    idempotency_key: str
    attempts: int
    last_error: str | None
    external_id: str | None
    published_at: datetime | None
    created_at: datetime


class BrandProfilePayload(BaseModel):
    brand_voice_json: dict[str, object] = Field(default_factory=dict)
    brand_assets_json: dict[str, object] = Field(default_factory=dict)
    locations_json: list[dict[str, object]] = Field(default_factory=list)
    auto_approve_tiers_max: int = Field(default=1, ge=0, le=4)
    require_approval_for_publish: bool = True


class BrandProfileResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    brand_voice_json: dict[str, object]
    brand_assets_json: dict[str, object]
    locations_json: list[dict[str, object]]
    auto_approve_tiers_max: int
    require_approval_for_publish: bool
    created_at: datetime

    @classmethod
    def from_model(cls, model: BrandProfile) -> "BrandProfileResponse":
        return cls(
            id=model.id,
            org_id=model.org_id,
            brand_voice_json=model.brand_voice_json,
            brand_assets_json=model.brand_assets_json,
            locations_json=model.locations_json,
            auto_approve_tiers_max=model.auto_approve_tiers_max,
            require_approval_for_publish=model.require_approval_for_publish,
            created_at=model.created_at,
        )


class LinkCreateRequest(BaseModel):
    destination_url: HttpUrl
    utm_json: dict[str, object] = Field(default_factory=dict)


class LinkResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    short_code: str
    destination_url: str
    utm_json: dict[str, object]
    created_at: datetime
