from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy import JSON as JsonType
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid


class Base(DeclarativeBase):
    pass


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [str(member.value) for member in enum_cls]


class Role(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    AGENT = "agent"


class RiskTier(str, enum.Enum):
    TIER_0 = "TIER_0"
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"
    TIER_4 = "TIER_4"


class CampaignPlanStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    ARCHIVED = "archived"


class ContentItemStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class ApprovalEntityType(str, enum.Enum):
    CAMPAIGN_PLAN = "campaign_plan"
    CONTENT_ITEM = "content_item"
    PUBLISH_JOB = "publish_job"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PublishJobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class InboxThreadType(str, enum.Enum):
    COMMENT = "comment"
    DM = "dm"
    FORM = "form"
    EMAIL = "email"
    SMS = "sms"
    OTHER = "other"


class InboxThreadStatus(str, enum.Enum):
    OPEN = "open"
    PENDING = "pending"
    CLOSED = "closed"


class InboxMessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class LeadStatus(str, enum.Enum):
    NEW = "new"
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    ARCHIVED = "archived"


class NurtureTaskType(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    CALL = "call"
    TASK = "task"


class NurtureTaskStatus(str, enum.Enum):
    OPEN = "open"
    DONE = "done"
    CANCELED = "canceled"


class PresenceAuditRunStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PresenceFindingSeverity(str, enum.Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PresenceFindingStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    IGNORED = "ignored"


class PresenceTaskType(str, enum.Enum):
    FIX_PROFILE = "fix_profile"
    POST_GBP = "post_gbp"
    UPDATE_HOURS = "update_hours"
    ADD_PHOTOS = "add_photos"
    CREATE_PAGE = "create_page"
    WRITE_BLOG = "write_blog"
    RESPOND_REVIEW = "respond_review"


class PresenceTaskStatus(str, enum.Enum):
    OPEN = "open"
    DONE = "done"
    CANCELED = "canceled"


class SEOWorkItemType(str, enum.Enum):
    SERVICE_PAGE = "service_page"
    BLOG_POST = "blog_post"
    BLOG_CLUSTER = "blog_cluster"
    FAQ = "faq"
    SCHEMA = "schema"


class SEOWorkItemStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ReputationSource(str, enum.Enum):
    GBP = "gbp"
    MANUAL_IMPORT = "manual_import"


class ReputationRequestCampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class ReputationAudience(str, enum.Enum):
    RECENT_CUSTOMERS = "recent_customers"
    CLOSED_DEALS = "closed_deals"
    CUSTOM = "custom"


class ReputationChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"


class REDealType(str, enum.Enum):
    BUYER = "buyer"
    SELLER = "seller"
    LISTING = "listing"
    LEASE = "lease"


class REDealStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class REChecklistItemStatus(str, enum.Enum):
    OPEN = "open"
    DONE = "done"
    CANCELED = "canceled"


class REDocumentRequestStatus(str, enum.Enum):
    REQUESTED = "requested"
    RECEIVED = "received"
    VERIFIED = "verified"


class RECommunicationChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    CALL = "call"
    NOTE = "note"


class RECommunicationDirection(str, enum.Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class RECMAComparableStatus(str, enum.Enum):
    SOLD = "sold"
    ACTIVE = "active"
    PENDING = "pending"


class REListingPackageStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    PUBLISHED = "published"


class OnboardingSessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Org(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "orgs"
    __table_args__ = (UniqueConstraint("name", name="uq_orgs_name"), Index("ix_orgs_created_at", "created_at"))

    name: Mapped[str] = mapped_column(String(255), nullable=False)


class User(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("external_auth_id", name="uq_users_external_auth_id"),
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_created_at", "created_at"),
    )

    external_auth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Membership(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_memberships_org_user"),
        Index("ix_memberships_org_id", "org_id"),
        Index("ix_memberships_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="role_enum"), nullable=False)


class Integration(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "provider", "external_account_id", name="uq_integrations_org_provider_external"
        ),
        Index("ix_integrations_org_id", "org_id"),
        Index("ix_integrations_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="registered")
    config_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class VerticalPack(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "vertical_packs"
    __table_args__ = (
        UniqueConstraint("org_id", name="uq_vertical_packs_org_id"),
        Index("ix_vertical_packs_org_id", "org_id"),
        Index("ix_vertical_packs_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    pack_slug: Mapped[str] = mapped_column(String(100), nullable=False)


class Event(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_org_id", "org_id"),
        Index("ix_events_created_at", "created_at"),
        Index("ix_events_org_type_created_at", "org_id", "type", "created_at"),
        Index("ix_events_org_created_at", "org_id", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lead_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class AuditLog(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_org_id", "org_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    risk_tier: Mapped[RiskTier] = mapped_column(
        Enum(RiskTier, name="risk_tier_enum", values_callable=_enum_values),
        nullable=False,
        default=RiskTier.TIER_1,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class ConnectorAccount(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "connector_accounts"
    __table_args__ = (
        UniqueConstraint("org_id", "provider", "account_ref", name="uq_connector_accounts_org_provider_ref"),
        Index("ix_connector_accounts_org_id", "org_id"),
        Index("ix_connector_accounts_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    account_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="linked")


class OAuthToken(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "oauth_tokens"
    __table_args__ = (
        UniqueConstraint("org_id", "provider", "account_ref", name="uq_oauth_tokens_org_provider_ref"),
        Index("ix_oauth_tokens_org_id", "org_id"),
        Index("ix_oauth_tokens_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    account_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token_enc: Mapped[str] = mapped_column(String(2048), nullable=False)
    refresh_token_enc: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConnectorHealth(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "connector_health"
    __table_args__ = (
        UniqueConstraint("org_id", "provider", "account_ref", name="uq_connector_health_org_provider_ref"),
        Index("ix_connector_health_org_id", "org_id"),
        Index("ix_connector_health_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    account_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_msg: Mapped[str | None] = mapped_column(String(500), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(nullable=False, default=0)


class ConnectorWorkflowRun(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "connector_workflow_runs"
    __table_args__ = (
        UniqueConstraint("org_id", "idempotency_key", name="uq_connector_workflow_runs_org_idempotency"),
        Index("ix_connector_workflow_runs_org_id", "org_id"),
        Index("ix_connector_workflow_runs_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    account_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    result_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConnectorDeadLetter(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "connector_dead_letters"
    __table_args__ = (
        Index("ix_connector_dead_letters_org_id", "org_id"),
        Index("ix_connector_dead_letters_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    account_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class CampaignPlan(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "campaign_plans"
    __table_args__ = (
        UniqueConstraint("org_id", "week_start_date", name="uq_campaign_plans_org_week"),
        Index("ix_campaign_plans_org_id", "org_id"),
        Index("ix_campaign_plans_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    vertical_pack_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    week_start_date: Mapped[date] = mapped_column(nullable=False)
    status: Mapped[CampaignPlanStatus] = mapped_column(
        Enum(CampaignPlanStatus, name="campaign_plan_status_enum", values_callable=_enum_values),
        nullable=False,
        default=CampaignPlanStatus.DRAFT,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class ContentItem(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "content_items"
    __table_args__ = (
        Index("ix_content_items_org_id", "org_id"),
        Index("ix_content_items_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    campaign_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaign_plans.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    account_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ContentItemStatus] = mapped_column(
        Enum(ContentItemStatus, name="content_item_status_enum", values_callable=_enum_values),
        nullable=False,
        default=ContentItemStatus.DRAFT,
    )
    content_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    text_rendered: Mapped[str] = mapped_column(String(4000), nullable=False)
    media_refs_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)
    link_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    tags_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)
    risk_tier: Mapped[RiskTier] = mapped_column(Enum(RiskTier, name="risk_tier_enum"), nullable=False)
    policy_warnings_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)


class Approval(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "approvals"
    __table_args__ = (
        Index("ix_approvals_org_id", "org_id"),
        Index("ix_approvals_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    entity_type: Mapped[ApprovalEntityType] = mapped_column(
        Enum(ApprovalEntityType, name="approval_entity_type_enum", values_callable=_enum_values),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="approval_status_enum", values_callable=_enum_values),
        nullable=False,
        default=ApprovalStatus.PENDING,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class PublishJob(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "publish_jobs"
    __table_args__ = (
        UniqueConstraint("org_id", "idempotency_key", name="uq_publish_jobs_org_idempotency"),
        UniqueConstraint("org_id", "content_item_id", name="uq_publish_jobs_org_content_item"),
        Index("ix_publish_jobs_org_id", "org_id"),
        Index("ix_publish_jobs_created_at", "created_at"),
        Index("ix_publish_jobs_org_status_schedule_at", "org_id", "status", "schedule_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    content_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_items.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    account_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    schedule_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[PublishJobStatus] = mapped_column(
        Enum(PublishJobStatus, name="publish_job_status_enum", values_callable=_enum_values),
        nullable=False,
        default=PublishJobStatus.QUEUED,
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BrandProfile(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "brand_profiles"
    __table_args__ = (
        UniqueConstraint("org_id", name="uq_brand_profiles_org_id"),
        Index("ix_brand_profiles_org_id", "org_id"),
        Index("ix_brand_profiles_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    brand_voice_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    brand_assets_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    locations_json: Mapped[list[dict[str, object]]] = mapped_column(JsonType, nullable=False, default=list)
    auto_approve_tiers_max: Mapped[int] = mapped_column(nullable=False, default=1)
    require_approval_for_publish: Mapped[bool] = mapped_column(nullable=False, default=True)


class OrgSettings(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "org_settings"
    __table_args__ = (
        UniqueConstraint("org_id", name="uq_org_settings_org_id"),
        Index("ix_org_settings_org_id", "org_id"),
        Index("ix_org_settings_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    settings_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class LinkTracking(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "link_tracking"
    __table_args__ = (
        UniqueConstraint("org_id", "short_code", name="uq_link_tracking_org_short_code"),
        UniqueConstraint("short_code", name="uq_link_tracking_short_code"),
        Index("ix_link_tracking_org_id", "org_id"),
        Index("ix_link_tracking_created_at", "created_at"),
        Index("ix_link_tracking_org_created_at", "org_id", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    short_code: Mapped[str] = mapped_column(String(32), nullable=False)
    destination_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    utm_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class LinkClick(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "link_clicks"
    __table_args__ = (
        Index("ix_link_clicks_org_id", "org_id"),
        Index("ix_link_clicks_created_at", "created_at"),
        Index("ix_link_clicks_org_clicked_at", "org_id", "clicked_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    tracked_link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("link_tracking.id"), nullable=False)
    short_code: Mapped[str] = mapped_column(String(32), nullable=False)
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    referrer: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id"), nullable=True)


class Pipeline(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "pipelines"
    __table_args__ = (
        UniqueConstraint("org_id", "slug", name="uq_pipelines_org_slug"),
        Index("ix_pipelines_org_id", "org_id"),
        Index("ix_pipelines_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(nullable=False, default=False)
    config_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class Stage(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "stages"
    __table_args__ = (
        UniqueConstraint("org_id", "pipeline_id", "slug", name="uq_stages_org_pipeline_slug"),
        Index("ix_stages_org_id", "org_id"),
        Index("ix_stages_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pipelines.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[int] = mapped_column(nullable=False, default=0)
    exit_on_win: Mapped[bool] = mapped_column(nullable=False, default=False)


class Lead(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_org_id", "org_id"),
        Index("ix_leads_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status_enum", values_callable=_enum_values),
        nullable=False,
        default=LeadStatus.NEW,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    tags_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)


class InboxThread(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "inbox_threads"
    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "provider",
            "account_ref",
            "external_thread_id",
            name="uq_inbox_threads_org_provider_account_external",
        ),
        Index("ix_inbox_threads_org_id", "org_id"),
        Index("ix_inbox_threads_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    account_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    external_thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    thread_type: Mapped[InboxThreadType] = mapped_column(
        Enum(InboxThreadType, name="inbox_thread_type_enum", values_callable=_enum_values),
        nullable=False,
    )
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    participants_json: Mapped[list[dict[str, object]]] = mapped_column(JsonType, nullable=False, default=list)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[InboxThreadStatus] = mapped_column(
        Enum(InboxThreadStatus, name="inbox_thread_status_enum", values_callable=_enum_values),
        nullable=False,
        default=InboxThreadStatus.OPEN,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id"), nullable=True)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class InboxMessage(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "inbox_messages"
    __table_args__ = (
        UniqueConstraint("org_id", "thread_id", "external_message_id", name="uq_inbox_messages_org_thread_external"),
        Index("ix_inbox_messages_org_id", "org_id"),
        Index("ix_inbox_messages_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inbox_threads.id"), nullable=False)
    external_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    direction: Mapped[InboxMessageDirection] = mapped_column(
        Enum(InboxMessageDirection, name="inbox_message_direction_enum", values_callable=_enum_values),
        nullable=False,
    )
    sender_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_display: Mapped[str] = mapped_column(String(255), nullable=False)
    body_text: Mapped[str] = mapped_column(String(8000), nullable=False)
    body_raw_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    flags_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class LeadScore(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "lead_scores"
    __table_args__ = (
        UniqueConstraint("org_id", "lead_id", name="uq_lead_scores_org_lead"),
        Index("ix_lead_scores_org_id", "org_id"),
        Index("ix_lead_scores_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"), nullable=False)
    score_total: Mapped[int] = mapped_column(nullable=False, default=0)
    score_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")


class LeadAssignment(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "lead_assignments"
    __table_args__ = (
        UniqueConstraint("org_id", "lead_id", name="uq_lead_assignments_org_lead"),
        Index("ix_lead_assignments_org_id", "org_id"),
        Index("ix_lead_assignments_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"), nullable=False)
    assigned_to_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    rule_applied: Mapped[str] = mapped_column(String(100), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class NurtureTask(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "nurture_tasks"
    __table_args__ = (
        Index("ix_nurture_tasks_org_id", "org_id"),
        Index("ix_nurture_tasks_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"), nullable=False)
    type: Mapped[NurtureTaskType] = mapped_column(
        Enum(NurtureTaskType, name="nurture_task_type_enum", values_callable=_enum_values),
        nullable=False,
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[NurtureTaskStatus] = mapped_column(
        Enum(NurtureTaskStatus, name="nurture_task_status_enum", values_callable=_enum_values),
        nullable=False,
        default=NurtureTaskStatus.OPEN,
    )
    template_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class SLAConfig(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sla_configs"
    __table_args__ = (
        UniqueConstraint("org_id", name="uq_sla_configs_org_id"),
        Index("ix_sla_configs_org_id", "org_id"),
        Index("ix_sla_configs_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    response_time_minutes: Mapped[int] = mapped_column(nullable=False, default=30)
    escalation_minutes: Mapped[int] = mapped_column(nullable=False, default=60)
    notify_channels_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)


class PresenceAuditRun(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "presence_audit_runs"
    __table_args__ = (
        Index("ix_presence_audit_runs_org_id", "org_id"),
        Index("ix_presence_audit_runs_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[PresenceAuditRunStatus] = mapped_column(
        Enum(PresenceAuditRunStatus, name="presence_audit_run_status_enum", values_callable=_enum_values),
        nullable=False,
        default=PresenceAuditRunStatus.RUNNING,
    )
    inputs_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    summary_scores_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    notes_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    error_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class PresenceFinding(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "presence_findings"
    __table_args__ = (
        Index("ix_presence_findings_org_id", "org_id"),
        Index("ix_presence_findings_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("presence_audit_runs.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[PresenceFindingSeverity] = mapped_column(
        Enum(PresenceFindingSeverity, name="presence_finding_severity_enum", values_callable=_enum_values),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    recommendation_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    status: Mapped[PresenceFindingStatus] = mapped_column(
        Enum(PresenceFindingStatus, name="presence_finding_status_enum", values_callable=_enum_values),
        nullable=False,
        default=PresenceFindingStatus.OPEN,
    )


class PresenceTask(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "presence_tasks"
    __table_args__ = (
        Index("ix_presence_tasks_org_id", "org_id"),
        Index("ix_presence_tasks_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    finding_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("presence_findings.id"), nullable=True)
    type: Mapped[PresenceTaskType] = mapped_column(
        Enum(PresenceTaskType, name="presence_task_type_enum", values_callable=_enum_values),
        nullable=False,
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[PresenceTaskStatus] = mapped_column(
        Enum(PresenceTaskStatus, name="presence_task_status_enum", values_callable=_enum_values),
        nullable=False,
        default=PresenceTaskStatus.OPEN,
    )
    payload_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class SEOWorkItem(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "seo_work_items"
    __table_args__ = (
        Index("ix_seo_work_items_org_id", "org_id"),
        Index("ix_seo_work_items_created_at", "created_at"),
        UniqueConstraint("org_id", "type", "url_slug", name="uq_seo_work_items_org_type_slug"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    type: Mapped[SEOWorkItemType] = mapped_column(
        Enum(SEOWorkItemType, name="seo_work_item_type_enum", values_callable=_enum_values),
        nullable=False,
    )
    status: Mapped[SEOWorkItemStatus] = mapped_column(
        Enum(SEOWorkItemStatus, name="seo_work_item_status_enum", values_callable=_enum_values),
        nullable=False,
        default=SEOWorkItemStatus.DRAFT,
    )
    target_keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    target_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    content_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    rendered_markdown: Mapped[str | None] = mapped_column(String(32000), nullable=True)
    risk_tier: Mapped[RiskTier] = mapped_column(
        Enum(RiskTier, name="risk_tier_enum", values_callable=_enum_values),
        nullable=False,
        default=RiskTier.TIER_1,
    )
    policy_warnings_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)


class ReputationReview(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "reputation_reviews"
    __table_args__ = (
        Index("ix_reputation_reviews_org_id", "org_id"),
        Index("ix_reputation_reviews_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    source: Mapped[ReputationSource] = mapped_column(
        Enum(ReputationSource, name="reputation_source_enum", values_callable=_enum_values),
        nullable=False,
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewer_name_masked: Mapped[str] = mapped_column(String(255), nullable=False)
    rating: Mapped[int] = mapped_column(nullable=False)
    review_text: Mapped[str] = mapped_column(String(8000), nullable=False)
    review_text_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    sentiment_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReputationRequestCampaign(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "reputation_request_campaigns"
    __table_args__ = (
        Index("ix_reputation_request_campaigns_org_id", "org_id"),
        Index("ix_reputation_request_campaigns_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ReputationRequestCampaignStatus] = mapped_column(
        Enum(
            ReputationRequestCampaignStatus,
            name="reputation_request_campaign_status_enum",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=ReputationRequestCampaignStatus.DRAFT,
    )
    audience: Mapped[ReputationAudience] = mapped_column(
        Enum(ReputationAudience, name="reputation_audience_enum", values_callable=_enum_values),
        nullable=False,
    )
    template_key: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[ReputationChannel] = mapped_column(
        Enum(ReputationChannel, name="reputation_channel_enum", values_callable=_enum_values),
        nullable=False,
    )


class REDeal(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "re_deals"
    __table_args__ = (
        Index("ix_re_deals_org_id", "org_id"),
        Index("ix_re_deals_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    deal_type: Mapped[REDealType] = mapped_column(
        Enum(REDealType, name="re_deal_type_enum", values_callable=_enum_values),
        nullable=False,
    )
    status: Mapped[REDealStatus] = mapped_column(
        Enum(REDealStatus, name="re_deal_status_enum", values_callable=_enum_values),
        nullable=False,
        default=REDealStatus.ACTIVE,
    )
    pipeline_stage: Mapped[str] = mapped_column(String(100), nullable=False, default="lead")
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id"), nullable=True)
    primary_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    primary_contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    property_address_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    important_dates_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class REChecklistTemplate(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "re_checklist_templates"
    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "name",
            "deal_type",
            "state_code",
            name="uq_re_checklist_templates_org_name_type_state",
        ),
        Index("ix_re_checklist_templates_org_id", "org_id"),
        Index("ix_re_checklist_templates_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    deal_type: Mapped[REDealType] = mapped_column(
        Enum(REDealType, name="re_checklist_template_deal_type_enum", values_callable=_enum_values),
        nullable=False,
    )
    state_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    items_json: Mapped[list[dict[str, object]]] = mapped_column(JsonType, nullable=False, default=list)


class REChecklistItem(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "re_checklist_items"
    __table_args__ = (
        Index("ix_re_checklist_items_org_id", "org_id"),
        Index("ix_re_checklist_items_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    deal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("re_deals.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[REChecklistItemStatus] = mapped_column(
        Enum(REChecklistItemStatus, name="re_checklist_item_status_enum", values_callable=_enum_values),
        nullable=False,
        default=REChecklistItemStatus.OPEN,
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source_template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("re_checklist_templates.id"), nullable=True)


class REDocumentRequest(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "re_document_requests"
    __table_args__ = (
        Index("ix_re_document_requests_org_id", "org_id"),
        Index("ix_re_document_requests_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    deal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("re_deals.id"), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_from: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[REDocumentRequestStatus] = mapped_column(
        Enum(REDocumentRequestStatus, name="re_document_request_status_enum", values_callable=_enum_values),
        nullable=False,
        default=REDocumentRequestStatus.REQUESTED,
    )
    file_ref: Mapped[str | None] = mapped_column(String(2048), nullable=True)


class RECommunicationLog(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "re_communication_logs"
    __table_args__ = (
        Index("ix_re_communication_logs_org_id", "org_id"),
        Index("ix_re_communication_logs_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    deal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("re_deals.id"), nullable=False)
    thread_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("inbox_threads.id"), nullable=True)
    channel: Mapped[RECommunicationChannel] = mapped_column(
        Enum(RECommunicationChannel, name="re_communication_channel_enum", values_callable=_enum_values),
        nullable=False,
    )
    direction: Mapped[RECommunicationDirection] = mapped_column(
        Enum(RECommunicationDirection, name="re_communication_direction_enum", values_callable=_enum_values),
        nullable=False,
    )
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_text: Mapped[str] = mapped_column(String(8000), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class RECMAReport(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "re_cma_reports"
    __table_args__ = (
        Index("ix_re_cma_reports_org_id", "org_id"),
        Index("ix_re_cma_reports_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id"), nullable=True)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("re_deals.id"), nullable=True)
    subject_property_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    pricing_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    narrative_text: Mapped[str | None] = mapped_column(String(32000), nullable=True)
    risk_tier: Mapped[RiskTier] = mapped_column(
        Enum(RiskTier, name="risk_tier_enum", values_callable=_enum_values),
        nullable=False,
        default=RiskTier.TIER_1,
    )
    policy_warnings_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)


class RECMAComparable(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "re_cma_comparables"
    __table_args__ = (
        Index("ix_re_cma_comparables_org_id", "org_id"),
        Index("ix_re_cma_comparables_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    cma_report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("re_cma_reports.id"), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[RECMAComparableStatus] = mapped_column(
        Enum(RECMAComparableStatus, name="re_cma_comparable_status_enum", values_callable=_enum_values),
        nullable=False,
    )
    sold_price: Mapped[int | None] = mapped_column(nullable=True)
    list_price: Mapped[int | None] = mapped_column(nullable=True)
    beds: Mapped[float | None] = mapped_column(nullable=True)
    baths: Mapped[float | None] = mapped_column(nullable=True)
    sqft: Mapped[int | None] = mapped_column(nullable=True)
    year_built: Mapped[int | None] = mapped_column(nullable=True)
    days_on_market: Mapped[int | None] = mapped_column(nullable=True)
    distance_miles: Mapped[float | None] = mapped_column(nullable=True)
    adjustments_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class REListingPackage(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "re_listing_packages"
    __table_args__ = (
        Index("ix_re_listing_packages_org_id", "org_id"),
        Index("ix_re_listing_packages_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("re_deals.id"), nullable=True)
    property_address_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    status: Mapped[REListingPackageStatus] = mapped_column(
        Enum(REListingPackageStatus, name="re_listing_package_status_enum", values_callable=_enum_values),
        nullable=False,
        default=REListingPackageStatus.DRAFT,
    )
    description_variants_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    key_features_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)
    open_house_plan_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    social_campaign_pack_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    risk_tier: Mapped[RiskTier] = mapped_column(
        Enum(RiskTier, name="risk_tier_enum", values_callable=_enum_values),
        nullable=False,
        default=RiskTier.TIER_1,
    )
    policy_warnings_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)


class OnboardingSession(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "onboarding_sessions"
    __table_args__ = (
        Index("ix_onboarding_sessions_org_id", "org_id"),
        Index("ix_onboarding_sessions_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    status: Mapped[OnboardingSessionStatus] = mapped_column(
        Enum(OnboardingSessionStatus, name="onboarding_session_status_enum", values_callable=_enum_values),
        nullable=False,
        default=OnboardingSessionStatus.IN_PROGRESS,
    )
    steps_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
