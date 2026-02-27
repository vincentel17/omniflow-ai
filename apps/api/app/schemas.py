from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .models import (
    ApprovalStatus,
    AdAccountStatus,
    AdCampaignObjective,
    AdCampaignStatus,
    AdCreativeFormat,
    AdCreativeStatus,
    AdExperimentStatus,
    AdProvider,
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
    REChecklistItemStatus,
    RECommunicationChannel,
    RECommunicationDirection,
    RECMAComparableStatus,
    REDealStatus,
    REDealType,
    REDocumentRequestStatus,
    REListingPackageStatus,
    ReputationAudience,
    ReputationChannel,
    ReputationRequestCampaignStatus,
    ReputationSource,
    RiskTier,
    Role,
    SEOWorkItemStatus,
    SEOWorkItemType,
    OnboardingSessionStatus,
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
    source: str | None = Field(default=None, max_length=100)
    medium: str | None = Field(default=None, max_length=100)
    campaign: str | None = Field(default=None, max_length=255)
    content_id: str | None = Field(default=None, max_length=255)
    campaign_plan_id: str | None = Field(default=None, max_length=255)
    channel: str | None = Field(default=None, max_length=100)
    utm_json: dict[str, object] = Field(default_factory=dict)


class LinkResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    short_code: str
    destination_url: str
    utm_json: dict[str, object]
    created_at: datetime
    short_url_path: str


class LinkAttachLeadRequest(BaseModel):
    lead_id: uuid.UUID


class AnalyticsOverviewResponse(BaseModel):
    totals: dict[str, int]
    avg_response_time_minutes: float | None
    presence_overall_score_latest: int | None
    staff_reduction_index: dict[str, object]
    top_channels: list[dict[str, object]]


class AnalyticsContentResponse(BaseModel):
    group_by: str
    content_items_by_status: dict[str, int]
    publish_success_rate: float
    clicks_by_content: list[dict[str, object]]
    leads_by_content: list[dict[str, object]]


class AnalyticsFunnelResponse(BaseModel):
    stages: dict[str, int]
    conversion_rates: dict[str, float]


class AnalyticsSLAResponse(BaseModel):
    avg_first_response_time_minutes: float | None
    within_sla_percent: float
    escalations_triggered: int
    overdue_threads_count: int


class AnalyticsPresenceResponse(BaseModel):
    group_by: str
    audit_runs_count: int
    score_trend: list[dict[str, object]]
    open_findings_count: int


class AnalyticsWorkloadResponse(BaseModel):
    estimated_minutes_saved_total: int
    breakdown_by_action_type: dict[str, int]
    automation_coverage_rate: float


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
    last_http_status: int | None = None
    last_provider_error_code: str | None = None
    last_rate_limit_reset_at: datetime | None = None


class ConnectorDiagnosticsResponse(BaseModel):
    id: uuid.UUID
    provider: str
    account_ref: str
    account_status: str
    scopes: list[str]
    expires_at: datetime | None
    health_status: str
    breaker_state: str
    last_error_msg: str | None
    last_http_status: int | None
    last_provider_error_code: str | None
    last_rate_limit_reset_at: datetime | None
    reauth_required: bool
    mode_effective: str


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
    model_config = ConfigDict(protected_namespaces=())
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


class OpsSettingsResponse(BaseModel):
    enable_auto_posting: bool = False
    enable_auto_reply: bool = False
    enable_auto_lead_routing: bool = True
    enable_auto_nurture_apply: bool = False
    enable_scheduled_audits: bool = True
    enable_seo_generation: bool = True
    enable_review_response_drafts: bool = True
    connector_mode: str = Field(default="mock", pattern="^(mock|live)$")
    providers_enabled_json: dict[str, bool] = Field(default_factory=dict)
    ai_mode: str = Field(default="mock", pattern="^(mock|live)$")
    max_auto_approve_tier: int = Field(default=1, ge=0, le=4)
    max_actions_per_event: int = Field(default=10, ge=1, le=200)
    max_workflow_runs_per_hour: int = Field(default=30, ge=1, le=500)
    max_depth: int = Field(default=3, ge=1, le=10)
    default_autonomy_max_tier: int = Field(default=1, ge=0, le=4)
    business_hours_start_hour: int = Field(default=9, ge=0, le=23)
    business_hours_end_hour: int = Field(default=17, ge=0, le=23)
    automation_weights: dict[str, int] = Field(default_factory=dict)
    enable_ads_automation: bool = False
    enable_ads_live: bool = False
    ads_provider_enabled_json: dict[str, bool] = Field(default_factory=dict)
    ads_budget_caps_json: dict[str, float] = Field(default_factory=dict)
    ads_canary_mode: bool = True
    require_approval_for_ads: bool = True
    compliance_mode: str = Field(default="none", pattern="^(none|real_estate|home_care)$")

class OpsSettingsPatchRequest(BaseModel):
    enable_auto_posting: bool | None = None
    enable_auto_reply: bool | None = None
    enable_auto_lead_routing: bool | None = None
    enable_auto_nurture_apply: bool | None = None
    enable_scheduled_audits: bool | None = None
    enable_seo_generation: bool | None = None
    enable_review_response_drafts: bool | None = None
    connector_mode: str | None = Field(default=None, pattern="^(mock|live)$")
    providers_enabled_json: dict[str, bool] | None = None
    ai_mode: str | None = Field(default=None, pattern="^(mock|live)$")
    max_auto_approve_tier: int | None = Field(default=None, ge=0, le=4)
    max_actions_per_event: int | None = Field(default=None, ge=1, le=200)
    max_workflow_runs_per_hour: int | None = Field(default=None, ge=1, le=500)
    max_depth: int | None = Field(default=None, ge=1, le=10)
    default_autonomy_max_tier: int | None = Field(default=None, ge=0, le=4)
    business_hours_start_hour: int | None = Field(default=None, ge=0, le=23)
    business_hours_end_hour: int | None = Field(default=None, ge=0, le=23)
    automation_weights: dict[str, int] | None = None
    enable_ads_automation: bool | None = None
    enable_ads_live: bool | None = None
    ads_provider_enabled_json: dict[str, bool] | None = None
    ads_budget_caps_json: dict[str, float] | None = None
    ads_canary_mode: bool | None = None
    require_approval_for_ads: bool | None = None
    compliance_mode: str | None = Field(default=None, pattern="^(none|real_estate|home_care)$")
class OnboardingSessionResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    status: OnboardingSessionStatus
    steps_json: dict[str, object]
    created_at: datetime
    completed_at: datetime | None


class OnboardingStepCompleteRequest(BaseModel):
    completed: bool = True


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


class REDealCreateRequest(BaseModel):
    deal_type: REDealType
    pipeline_stage: str = Field(default="lead", min_length=1, max_length=100)
    lead_id: uuid.UUID | None = None
    primary_contact_name: str | None = Field(default=None, max_length=255)
    primary_contact_email: str | None = Field(default=None, max_length=320)
    primary_contact_phone: str | None = Field(default=None, max_length=64)
    property_address_json: dict[str, object] = Field(default_factory=dict)
    important_dates_json: dict[str, object] = Field(default_factory=dict)


class REDealUpdateRequest(BaseModel):
    status: REDealStatus | None = None
    pipeline_stage: str | None = Field(default=None, min_length=1, max_length=100)
    property_address_json: dict[str, object] | None = None
    important_dates_json: dict[str, object] | None = None


class REDealResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    deal_type: REDealType
    status: REDealStatus
    pipeline_stage: str
    lead_id: uuid.UUID | None
    primary_contact_name: str | None
    primary_contact_email: str | None
    primary_contact_phone: str | None
    property_address_json: dict[str, object]
    important_dates_json: dict[str, object]
    created_at: datetime
    updated_at: datetime


class REChecklistApplyTemplateRequest(BaseModel):
    template_name: str = Field(min_length=1, max_length=255)
    state_code: str | None = Field(default=None, max_length=10)


class REChecklistItemResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    deal_id: uuid.UUID
    title: str
    description: str | None
    due_at: datetime | None
    status: REChecklistItemStatus
    assigned_to_user_id: uuid.UUID | None
    source_template_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class REDocumentRequestCreateRequest(BaseModel):
    doc_type: str = Field(min_length=1, max_length=100)
    requested_from: str = Field(min_length=1, max_length=100)


class REDocumentRequestResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    deal_id: uuid.UUID
    doc_type: str
    requested_from: str
    status: REDocumentRequestStatus
    file_ref: str | None
    created_at: datetime


class RECommunicationLogCreateRequest(BaseModel):
    channel: RECommunicationChannel
    direction: RECommunicationDirection
    subject: str | None = Field(default=None, max_length=255)
    body_text: str = Field(min_length=1, max_length=8000)
    thread_id: uuid.UUID | None = None


class RECommunicationLogResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    deal_id: uuid.UUID
    thread_id: uuid.UUID | None
    channel: RECommunicationChannel
    direction: RECommunicationDirection
    subject: str | None
    body_text: str
    created_by_user_id: uuid.UUID | None
    created_at: datetime


class RECMAReportCreateRequest(BaseModel):
    lead_id: uuid.UUID | None = None
    deal_id: uuid.UUID | None = None
    subject_property_json: dict[str, object] = Field(default_factory=dict)


class RECMAComparableInput(BaseModel):
    address: str = Field(min_length=1, max_length=500)
    status: RECMAComparableStatus
    sold_price: int | None = Field(default=None, ge=0)
    list_price: int | None = Field(default=None, ge=0)
    beds: float | None = Field(default=None, ge=0)
    baths: float | None = Field(default=None, ge=0)
    sqft: int | None = Field(default=None, ge=0)
    year_built: int | None = Field(default=None, ge=0)
    days_on_market: int | None = Field(default=None, ge=0)
    distance_miles: float | None = Field(default=None, ge=0)
    adjustments_json: dict[str, object] = Field(default_factory=dict)


class RECMACompsImportRequest(BaseModel):
    comparables: list[RECMAComparableInput] = Field(default_factory=list, max_length=200)


class RECMAComparableResponse(RECMAComparableInput):
    id: uuid.UUID
    org_id: uuid.UUID
    cma_report_id: uuid.UUID
    created_at: datetime


class RECMAReportResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    lead_id: uuid.UUID | None
    deal_id: uuid.UUID | None
    subject_property_json: dict[str, object]
    pricing_json: dict[str, object]
    narrative_text: str | None
    risk_tier: RiskTier
    policy_warnings_json: list[str]
    created_at: datetime


class REListingPackageCreateRequest(BaseModel):
    deal_id: uuid.UUID | None = None
    property_address_json: dict[str, object] = Field(default_factory=dict)
    key_features_json: list[str] = Field(default_factory=list)


class REListingPackageResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    deal_id: uuid.UUID | None
    property_address_json: dict[str, object]
    status: REListingPackageStatus
    description_variants_json: dict[str, object]
    key_features_json: list[str]
    open_house_plan_json: dict[str, object]
    social_campaign_pack_json: dict[str, object]
    risk_tier: RiskTier
    policy_warnings_json: list[str]
    created_at: datetime



class WorkflowCreateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=255)
    enabled: bool = True
    definition_json: dict[str, object]
    managed_by_pack: bool = False


class WorkflowUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool | None = None
    definition_json: dict[str, object] | None = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    key: str
    name: str
    enabled: bool
    trigger_type: str
    managed_by_pack: bool
    definition_json: dict[str, object]
    created_at: datetime
    updated_at: datetime


class WorkflowTestRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    channel: str = Field(min_length=1, max_length=100)
    payload_json: dict[str, object] = Field(default_factory=dict)
    risk_tier: int = Field(default=0, ge=0, le=4)


class WorkflowActionPreview(BaseModel):
    action_type: str
    params_json: dict[str, object]
    risk_tier: int
    requires_approval: bool


class WorkflowTestResponse(BaseModel):
    matched: bool
    skipped_reason: str | None = None
    overall_risk_tier: int = 0
    actions: list[WorkflowActionPreview] = Field(default_factory=list)


class WorkflowRunResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    workflow_id: uuid.UUID
    trigger_event_id: uuid.UUID | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    summary_json: dict[str, object]
    error_json: dict[str, object]
    loop_guard_hits: int
    created_at: datetime


class WorkflowActionRunResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    workflow_run_id: uuid.UUID
    action_type: str
    status: str
    idempotency_key: str
    input_json: dict[str, object]
    output_json: dict[str, object]
    error_json: dict[str, object]
    created_at: datetime


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    status: ApprovalStatus
    requested_by: uuid.UUID
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    notes: str | None
    created_at: datetime


class AdsSettingsResponse(BaseModel):
    enable_ads_automation: bool = False
    enable_ads_live: bool = False
    ads_provider_enabled_json: dict[str, bool] = Field(default_factory=dict)
    ads_budget_caps_json: dict[str, float] = Field(default_factory=dict)
    ads_canary_mode: bool = True
    require_approval_for_ads: bool = True
    compliance_mode: str = Field(default="none", pattern="^(none|real_estate|home_care)$")

class AdsSettingsPatchRequest(BaseModel):
    enable_ads_automation: bool | None = None
    enable_ads_live: bool | None = None
    ads_provider_enabled_json: dict[str, bool] | None = None
    ads_budget_caps_json: dict[str, float] | None = None
    ads_canary_mode: bool | None = None
    require_approval_for_ads: bool | None = None
    compliance_mode: str | None = Field(default=None, pattern="^(none|real_estate|home_care)$")

class AdAccountCreateRequest(BaseModel):
    provider: AdProvider
    account_ref: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)
    linked_connector_account_id: uuid.UUID | None = None


class AdAccountResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    provider: AdProvider
    account_ref: str
    display_name: str
    status: AdAccountStatus
    linked_connector_account_id: uuid.UUID | None = None
    created_at: datetime

class AdCampaignCreateRequest(BaseModel):
    provider: AdProvider
    ad_account_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    objective: AdCampaignObjective
    daily_budget_usd: float = Field(gt=0)
    lifetime_budget_usd: float | None = Field(default=None, gt=0)
    start_at: datetime | None = None
    end_at: datetime | None = None
    targeting_json: dict[str, object] = Field(default_factory=dict)
    utm_json: dict[str, object] = Field(default_factory=dict)


class AdCampaignPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    daily_budget_usd: float | None = Field(default=None, gt=0)
    lifetime_budget_usd: float | None = Field(default=None, gt=0)
    start_at: datetime | None = None
    end_at: datetime | None = None
    targeting_json: dict[str, object] | None = None
    utm_json: dict[str, object] | None = None


class AdCampaignResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    provider: AdProvider
    ad_account_id: uuid.UUID
    name: str
    objective: AdCampaignObjective
    status: AdCampaignStatus
    daily_budget_usd: float
    lifetime_budget_usd: float | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    targeting_json: dict[str, object]
    utm_json: dict[str, object]
    created_by: uuid.UUID
    external_id: str | None = None
    last_synced_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class AdCreativeCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    format: AdCreativeFormat = AdCreativeFormat.TEXT
    primary_text: str = Field(min_length=1, max_length=4000)
    headline: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=1000)
    media_ref: str | None = Field(default=None, max_length=2048)
    destination_tracked_link_id: uuid.UUID


class AdCreativeResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    campaign_id: uuid.UUID
    name: str
    format: AdCreativeFormat
    primary_text: str
    headline: str | None = None
    description: str | None = None
    media_ref: str | None = None
    destination_tracked_link_id: uuid.UUID
    status: AdCreativeStatus
    external_id: str | None = None
    created_at: datetime


class AdExperimentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    hypothesis: str = Field(min_length=1, max_length=1000)
    variants_json: list[dict[str, object]] = Field(default_factory=list, min_length=1, max_length=10)
    start_at: datetime | None = None
    end_at: datetime | None = None
    success_metric: str = Field(default="clicks", min_length=1, max_length=100)


class AdExperimentResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    campaign_id: uuid.UUID
    name: str
    hypothesis: str
    status: AdExperimentStatus
    variants_json: list[dict[str, object]]
    start_at: datetime | None = None
    end_at: datetime | None = None
    success_metric: str
    created_at: datetime


class AdSpendLedgerResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    provider: AdProvider
    campaign_id: uuid.UUID
    day: date
    spend_usd: float
    impressions: int | None = None
    clicks: int | None = None
    source: str
    created_at: datetime


class DataRetentionPolicyResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    entity_type: str
    retention_days: int
    hard_delete_after_days: int
    created_at: datetime


class DataRetentionPolicyPatchItem(BaseModel):
    entity_type: str = Field(min_length=1, max_length=80)
    retention_days: int = Field(ge=1, le=3650)
    hard_delete_after_days: int = Field(ge=1, le=7300)


class DataRetentionPolicyPatchRequest(BaseModel):
    policies: list[DataRetentionPolicyPatchItem] = Field(default_factory=list, min_length=1, max_length=50)


class DSARRequestCreateRequest(BaseModel):
    request_type: str = Field(pattern="^(access|delete|export)$")
    subject_identifier: str = Field(min_length=3, max_length=255)


class DSARRequestProcessResponse(BaseModel):
    id: uuid.UUID
    status: str
    export_ref: str | None = None
    completed_at: datetime | None = None


class DSARRequestResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    request_type: str
    subject_identifier: str
    status: str
    requested_at: datetime
    completed_at: datetime | None = None
    export_ref: str | None = None
    created_at: datetime


class RBACMatrixResponse(BaseModel):
    roles: dict[str, list[str]]


class PermissionAuditReportResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    findings_json: list[dict[str, object]]
    recommendations_json: list[str]
    created_at: datetime


class EvidenceBundleResponse(BaseModel):
    from_date: date
    to_date: date
    include_pii: bool = False
    bundle_json: dict[str, object]

