"""phase5 digital presence, seo, and reputation tables

Revision ID: 0006_phase5_presence_seo_rep
Revises: 0005_phase4_inbox_lead_engine
Create Date: 2026-02-24 14:30:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_phase5_presence_seo_rep"
down_revision: str | None = "0005_phase4_inbox_lead_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    presence_audit_run_status_enum = sa.Enum(
        "running",
        "succeeded",
        "failed",
        name="presence_audit_run_status_enum",
    )
    presence_finding_severity_enum = sa.Enum(
        "info",
        "low",
        "medium",
        "high",
        name="presence_finding_severity_enum",
    )
    presence_finding_status_enum = sa.Enum(
        "open",
        "in_progress",
        "done",
        "ignored",
        name="presence_finding_status_enum",
    )
    presence_task_type_enum = sa.Enum(
        "fix_profile",
        "post_gbp",
        "update_hours",
        "add_photos",
        "create_page",
        "write_blog",
        "respond_review",
        name="presence_task_type_enum",
    )
    presence_task_status_enum = sa.Enum("open", "done", "canceled", name="presence_task_status_enum")
    seo_work_item_type_enum = sa.Enum(
        "service_page",
        "blog_post",
        "blog_cluster",
        "faq",
        "schema",
        name="seo_work_item_type_enum",
    )
    seo_work_item_status_enum = sa.Enum(
        "draft",
        "approved",
        "published",
        "archived",
        name="seo_work_item_status_enum",
    )
    reputation_source_enum = sa.Enum("gbp", "manual_import", name="reputation_source_enum")
    reputation_request_campaign_status_enum = sa.Enum(
        "draft",
        "running",
        "paused",
        "completed",
        name="reputation_request_campaign_status_enum",
    )
    reputation_audience_enum = sa.Enum(
        "recent_customers",
        "closed_deals",
        "custom",
        name="reputation_audience_enum",
    )
    reputation_channel_enum = sa.Enum("email", "sms", name="reputation_channel_enum")

    op.create_table(
        "presence_audit_runs",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", presence_audit_run_status_enum, nullable=False, server_default=sa.text("'running'")),
        sa.Column("inputs_json", sa.JSON(), nullable=False),
        sa.Column("summary_scores_json", sa.JSON(), nullable=False),
        sa.Column("notes_json", sa.JSON(), nullable=False),
        sa.Column("error_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_presence_audit_runs_org_id", "presence_audit_runs", ["org_id"], unique=False)
    op.create_index("ix_presence_audit_runs_created_at", "presence_audit_runs", ["created_at"], unique=False)

    op.create_table(
        "presence_findings",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("audit_run_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("severity", presence_finding_severity_enum, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("recommendation_json", sa.JSON(), nullable=False),
        sa.Column("status", presence_finding_status_enum, nullable=False, server_default=sa.text("'open'")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["audit_run_id"], ["presence_audit_runs.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_presence_findings_org_id", "presence_findings", ["org_id"], unique=False)
    op.create_index("ix_presence_findings_created_at", "presence_findings", ["created_at"], unique=False)

    op.create_table(
        "presence_tasks",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=True),
        sa.Column("type", presence_task_type_enum, nullable=False),
        sa.Column("assigned_to_user_id", sa.Uuid(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", presence_task_status_enum, nullable=False, server_default=sa.text("'open'")),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["finding_id"], ["presence_findings.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_presence_tasks_org_id", "presence_tasks", ["org_id"], unique=False)
    op.create_index("ix_presence_tasks_created_at", "presence_tasks", ["created_at"], unique=False)

    op.create_table(
        "seo_work_items",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("type", seo_work_item_type_enum, nullable=False),
        sa.Column("status", seo_work_item_status_enum, nullable=False, server_default=sa.text("'draft'")),
        sa.Column("target_keyword", sa.String(length=255), nullable=False),
        sa.Column("target_location", sa.String(length=255), nullable=True),
        sa.Column("url_slug", sa.String(length=255), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("rendered_markdown", sa.String(length=32000), nullable=True),
        sa.Column("risk_tier", sa.Enum("TIER_0", "TIER_1", "TIER_2", "TIER_3", "TIER_4", name="risk_tier_enum"), nullable=False),
        sa.Column("policy_warnings_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "type", "url_slug", name="uq_seo_work_items_org_type_slug"),
    )
    op.create_index("ix_seo_work_items_org_id", "seo_work_items", ["org_id"], unique=False)
    op.create_index("ix_seo_work_items_created_at", "seo_work_items", ["created_at"], unique=False)

    op.create_table(
        "reputation_reviews",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("source", reputation_source_enum, nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("reviewer_name_masked", sa.String(length=255), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("review_text", sa.String(length=8000), nullable=False),
        sa.Column("review_text_hash", sa.String(length=128), nullable=False),
        sa.Column("sentiment_json", sa.JSON(), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reputation_reviews_org_id", "reputation_reviews", ["org_id"], unique=False)
    op.create_index("ix_reputation_reviews_created_at", "reputation_reviews", ["created_at"], unique=False)

    op.create_table(
        "reputation_request_campaigns",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            reputation_request_campaign_status_enum,
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("audience", reputation_audience_enum, nullable=False),
        sa.Column("template_key", sa.String(length=100), nullable=False),
        sa.Column("channel", reputation_channel_enum, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reputation_request_campaigns_org_id",
        "reputation_request_campaigns",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "ix_reputation_request_campaigns_created_at",
        "reputation_request_campaigns",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_reputation_request_campaigns_created_at", table_name="reputation_request_campaigns")
    op.drop_index("ix_reputation_request_campaigns_org_id", table_name="reputation_request_campaigns")
    op.drop_table("reputation_request_campaigns")

    op.drop_index("ix_reputation_reviews_created_at", table_name="reputation_reviews")
    op.drop_index("ix_reputation_reviews_org_id", table_name="reputation_reviews")
    op.drop_table("reputation_reviews")

    op.drop_index("ix_seo_work_items_created_at", table_name="seo_work_items")
    op.drop_index("ix_seo_work_items_org_id", table_name="seo_work_items")
    op.drop_table("seo_work_items")

    op.drop_index("ix_presence_tasks_created_at", table_name="presence_tasks")
    op.drop_index("ix_presence_tasks_org_id", table_name="presence_tasks")
    op.drop_table("presence_tasks")

    op.drop_index("ix_presence_findings_created_at", table_name="presence_findings")
    op.drop_index("ix_presence_findings_org_id", table_name="presence_findings")
    op.drop_table("presence_findings")

    op.drop_index("ix_presence_audit_runs_created_at", table_name="presence_audit_runs")
    op.drop_index("ix_presence_audit_runs_org_id", table_name="presence_audit_runs")
    op.drop_table("presence_audit_runs")

    sa.Enum(name="reputation_channel_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="reputation_audience_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="reputation_request_campaign_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="reputation_source_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="seo_work_item_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="seo_work_item_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="presence_task_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="presence_task_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="presence_finding_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="presence_finding_severity_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="presence_audit_run_status_enum").drop(op.get_bind(), checkfirst=True)

