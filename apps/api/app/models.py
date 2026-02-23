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


class LinkTracking(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "link_tracking"
    __table_args__ = (
        UniqueConstraint("org_id", "short_code", name="uq_link_tracking_org_short_code"),
        Index("ix_link_tracking_org_id", "org_id"),
        Index("ix_link_tracking_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    short_code: Mapped[str] = mapped_column(String(32), nullable=False)
    destination_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    utm_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


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
