from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, HttpUrl

from .models import (
    ApprovalStatus,
    BrandProfile,
    CampaignPlanStatus,
    ContentItemStatus,
    InboxMessageDirection,
    InboxThreadStatus,
    InboxThreadType,
    LeadStatus,
    NurtureTaskStatus,
    NurtureTaskType,
    PresenceAuditRunStatus,
    PresenceFindingSeverity,
    PresenceFindingStatus,
    PresenceTaskStatus,
    PresenceTaskType,
    PublishJobStatus,
    ReputationAudience,
    ReputationChannel,
    ReputationRequestCampaignStatus,
    ReputationSource,
    RiskTier,
    Role,
    SEOWorkItemStatus,
    SEOWorkItemType,
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


class ConnectorProviderResponse(BaseModel):
    provider: str
    mode: str
    configured: bool


class ConnectorStartRequest(BaseModel):
    account_ref: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)


class ConnectorStartResponse(BaseModel):
    provider: str
    state: str
    authorization_url: str


class ConnectorCallbackRequest(BaseModel):
    state: str = Field(min_length=8, max_length=255)
    code: str = Field(min_length=1, max_length=2048)
    account_ref: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)


class ConnectorAccountResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    provider: str
    account_ref: str
    display_name: str
    status: str
    created_at: datetime


class ConnectorHealthResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    provider: str
    account_ref: str
    last_ok_at: datetime | None
    last_error_at: datetime | None
    last_error_msg: str | None
    consecutive_failures: int


class InboxIngestMockRequest(BaseModel):
    thread: dict[str, object]
    messages: list[dict[str, object]] = Field(default_factory=list)


class InboxIngestMockResponse(BaseModel):
    thread_id: uuid.UUID
    inserted_messages: int


class InboxThreadResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    provider: str
    account_ref: str
    external_thread_id: str
    thread_type: InboxThreadType
    subject: str | None
    participants_json: list[dict[str, object]]
    last_message_at: datetime | None
    status: InboxThreadStatus
    lead_id: uuid.UUID | None
    assigned_to_user_id: uuid.UUID | None
    created_at: datetime


class InboxMessageResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    thread_id: uuid.UUID
    external_message_id: str
    direction: InboxMessageDirection
    sender_ref: str
    sender_display: str
    body_text: str
    body_raw_json: dict[str, object]
    flags_json: dict[str, object]
    created_at: datetime


class InboxAssignRequest(BaseModel):
    assigned_to_user_id: uuid.UUID


class ReplySuggestionResponse(BaseModel):
    intent: str
    reply_text: str
    followup_questions: list[str]
    risk_tier: RiskTier
    required_disclaimers: list[str]
    policy_warnings: list[str] = Field(default_factory=list)


class DraftReplyRequest(BaseModel):
    body_text: str = Field(min_length=1, max_length=2000)


class LeadResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    source: str
    status: LeadStatus
    name: str | None
    email: str | None
    phone: str | None
    location_json: dict[str, object]
    tags_json: list[str]
    created_at: datetime
    updated_at: datetime


class LeadPatchRequest(BaseModel):
    status: LeadStatus | None = None
    name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    location_json: dict[str, object] | None = None
    tags_json: list[str] | None = None


class LeadScoreResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    lead_id: uuid.UUID
    score_total: int
    score_json: dict[str, object]
    scored_at: datetime
    model_version: str


class LeadAssignmentResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    lead_id: uuid.UUID
    assigned_to_user_id: uuid.UUID
    rule_applied: str
    assigned_at: datetime
    created_at: datetime


class NurtureTaskResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    lead_id: uuid.UUID
    type: NurtureTaskType
    due_at: datetime
    status: NurtureTaskStatus
    template_key: str | None
    payload_json: dict[str, object]
    created_by: uuid.UUID | None
    created_at: datetime


class NurtureTaskPayload(BaseModel):
    type: NurtureTaskType
    due_in_minutes: int = Field(ge=1, le=10080)
    message_template_key: str = Field(min_length=1, max_length=100)
    message_body: str = Field(min_length=1, max_length=2000)


class NurtureApplyRequest(BaseModel):
    tasks: list[NurtureTaskPayload] = Field(default_factory=list, max_length=20)


class NurtureTaskUpdateRequest(BaseModel):
    status: NurtureTaskStatus


class SLAConfigPayload(BaseModel):
    response_time_minutes: int = Field(default=30, ge=1, le=10080)
    escalation_minutes: int = Field(default=60, ge=1, le=10080)
    notify_channels_json: list[str] = Field(default_factory=list)


class SLAConfigResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    response_time_minutes: int
    escalation_minutes: int
    notify_channels_json: list[str]
    created_at: datetime


class PresenceAuditRunRequest(BaseModel):
    website_url: HttpUrl | None = None
    providers_to_audit: list[str] = Field(default_factory=list, max_length=8)
    account_refs: dict[str, list[str]] = Field(default_factory=dict)
    run_mode: str = Field(default="manual", pattern="^(manual|scheduled)$")


class PresenceAuditRunResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None
    status: PresenceAuditRunStatus
    inputs_json: dict[str, object]
    summary_scores_json: dict[str, object]
    notes_json: dict[str, object]
    error_json: dict[str, object]
    created_at: datetime


class PresenceFindingResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    audit_run_id: uuid.UUID
    source: str
    category: str
    severity: PresenceFindingSeverity
    title: str
    description: str
    evidence_json: dict[str, object]
    recommendation_json: dict[str, object]
    status: PresenceFindingStatus
    created_at: datetime


class PresenceFindingStatusUpdateRequest(BaseModel):
    status: PresenceFindingStatus


class PresenceTaskCreateRequest(BaseModel):
    finding_id: uuid.UUID | None = None
    type: PresenceTaskType
    assigned_to_user_id: uuid.UUID | None = None
    due_at: datetime | None = None
    payload_json: dict[str, object] = Field(default_factory=dict)


class PresenceTaskResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    finding_id: uuid.UUID | None
    type: PresenceTaskType
    assigned_to_user_id: uuid.UUID | None
    due_at: datetime | None
    status: PresenceTaskStatus
    payload_json: dict[str, object]
    created_at: datetime


class SEOPlanRequest(BaseModel):
    audit_run_id: uuid.UUID | None = None
    target_locations: list[str] = Field(default_factory=list, max_length=20)


class SEOPlanResponse(BaseModel):
    service_pages: list[dict[str, object]] = Field(default_factory=list)
    blog_clusters: list[dict[str, object]] = Field(default_factory=list)
    internal_linking_suggestions: list[str] = Field(default_factory=list)
    schema_suggestions: list[str] = Field(default_factory=list)


class SEOWorkItemCreateRequest(BaseModel):
    type: SEOWorkItemType
    target_keyword: str = Field(min_length=1, max_length=255)
    target_location: str | None = Field(default=None, max_length=255)
    url_slug: str = Field(min_length=1, max_length=255)
    content_json: dict[str, object] = Field(default_factory=dict)


class SEOWorkItemResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    type: SEOWorkItemType
    status: SEOWorkItemStatus
    target_keyword: str
    target_location: str | None
    url_slug: str
    content_json: dict[str, object]
    rendered_markdown: str | None
    risk_tier: RiskTier
    policy_warnings_json: list[str]
    created_at: datetime


class SEOWorkItemApproveRequest(BaseModel):
    status: SEOWorkItemStatus = Field(default=SEOWorkItemStatus.APPROVED)


class ReputationReviewImportItem(BaseModel):
    source: ReputationSource = ReputationSource.MANUAL_IMPORT
    external_id: str | None = Field(default=None, max_length=255)
    reviewer_name: str | None = Field(default=None, max_length=255)
    rating: int = Field(ge=1, le=5)
    review_text: str = Field(min_length=1, max_length=8000)


class ReputationReviewImportRequest(BaseModel):
    reviews: list[ReputationReviewImportItem] = Field(default_factory=list, max_length=200)


class ReputationReviewResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    source: ReputationSource
    external_id: str | None
    reviewer_name_masked: str
    rating: int
    review_text: str
    review_text_hash: str
    sentiment_json: dict[str, object]
    responded_at: datetime | None
    created_at: datetime


class ReputationDraftResponse(BaseModel):
    response_text: str
    tone: str
    disclaimers: list[str]
    risk_tier: RiskTier
    policy_warnings: list[str]


class ReputationCampaignCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    audience: ReputationAudience
    template_key: str = Field(min_length=1, max_length=100)
    channel: ReputationChannel


class ReputationCampaignResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    status: ReputationRequestCampaignStatus
    audience: ReputationAudience
    template_key: str
    channel: ReputationChannel
    created_at: datetime
