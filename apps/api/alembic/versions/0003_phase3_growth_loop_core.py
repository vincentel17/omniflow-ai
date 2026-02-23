"""phase3 growth loop core models

Revision ID: 0003_phase3_growth_loop_core
Revises: 0002_phase1_core_foundations
Create Date: 2026-02-23 16:30:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_phase3_growth_loop_core"
down_revision: str | None = "0002_phase1_core_foundations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


campaign_plan_status_enum = postgresql.ENUM(
    "draft",
    "approved",
    "archived",
    name="campaign_plan_status_enum",
    create_type=False,
)
content_item_status_enum = postgresql.ENUM(
    "draft",
    "pending_approval",
    "approved",
    "scheduled",
    "publishing",
    "published",
    "failed",
    name="content_item_status_enum",
    create_type=False,
)
approval_entity_type_enum = postgresql.ENUM(
    "campaign_plan",
    "content_item",
    "publish_job",
    name="approval_entity_type_enum",
    create_type=False,
)
approval_status_enum = postgresql.ENUM(
    "pending",
    "approved",
    "rejected",
    name="approval_status_enum",
    create_type=False,
)
publish_job_status_enum = postgresql.ENUM(
    "queued",
    "running",
    "succeeded",
    "failed",
    "canceled",
    name="publish_job_status_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    campaign_plan_status_enum.create(bind, checkfirst=True)
    content_item_status_enum.create(bind, checkfirst=True)
    approval_entity_type_enum.create(bind, checkfirst=True)
    approval_status_enum.create(bind, checkfirst=True)
    publish_job_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "campaign_plans",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("vertical_pack_slug", sa.String(length=100), nullable=False),
        sa.Column("week_start_date", sa.Date(), nullable=False),
        sa.Column("status", campaign_plan_status_enum, nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "week_start_date", name="uq_campaign_plans_org_week"),
    )
    op.create_index("ix_campaign_plans_org_id", "campaign_plans", ["org_id"], unique=False)
    op.create_index("ix_campaign_plans_created_at", "campaign_plans", ["created_at"], unique=False)

    op.create_table(
        "content_items",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_plan_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=100), nullable=False),
        sa.Column("account_ref", sa.String(length=255), nullable=False),
        sa.Column("status", content_item_status_enum, nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("text_rendered", sa.String(length=4000), nullable=False),
        sa.Column("media_refs_json", sa.JSON(), nullable=False),
        sa.Column("link_url", sa.String(length=2048), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column(
            "risk_tier",
            postgresql.ENUM(
                "TIER_0",
                "TIER_1",
                "TIER_2",
                "TIER_3",
                "TIER_4",
                name="risk_tier_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("policy_warnings_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_plan_id"], ["campaign_plans.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_items_org_id", "content_items", ["org_id"], unique=False)
    op.create_index("ix_content_items_created_at", "content_items", ["created_at"], unique=False)

    op.create_table(
        "approvals",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", approval_entity_type_enum, nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("status", approval_status_enum, nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approvals_org_id", "approvals", ["org_id"], unique=False)
    op.create_index("ix_approvals_created_at", "approvals", ["created_at"], unique=False)

    op.create_table(
        "publish_jobs",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("content_item_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("account_ref", sa.String(length=255), nullable=False),
        sa.Column("schedule_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", publish_job_status_enum, nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "content_item_id", name="uq_publish_jobs_org_content_item"),
        sa.UniqueConstraint("org_id", "idempotency_key", name="uq_publish_jobs_org_idempotency"),
    )
    op.create_index("ix_publish_jobs_org_id", "publish_jobs", ["org_id"], unique=False)
    op.create_index("ix_publish_jobs_created_at", "publish_jobs", ["created_at"], unique=False)

    op.create_table(
        "brand_profiles",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("brand_voice_json", sa.JSON(), nullable=False),
        sa.Column("brand_assets_json", sa.JSON(), nullable=False),
        sa.Column("locations_json", sa.JSON(), nullable=False),
        sa.Column("auto_approve_tiers_max", sa.Integer(), nullable=False),
        sa.Column("require_approval_for_publish", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_brand_profiles_org_id"),
    )
    op.create_index("ix_brand_profiles_org_id", "brand_profiles", ["org_id"], unique=False)
    op.create_index("ix_brand_profiles_created_at", "brand_profiles", ["created_at"], unique=False)

    op.create_table(
        "link_tracking",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("short_code", sa.String(length=32), nullable=False),
        sa.Column("destination_url", sa.String(length=2048), nullable=False),
        sa.Column("utm_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "short_code", name="uq_link_tracking_org_short_code"),
    )
    op.create_index("ix_link_tracking_org_id", "link_tracking", ["org_id"], unique=False)
    op.create_index("ix_link_tracking_created_at", "link_tracking", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_link_tracking_created_at", table_name="link_tracking")
    op.drop_index("ix_link_tracking_org_id", table_name="link_tracking")
    op.drop_table("link_tracking")

    op.drop_index("ix_brand_profiles_created_at", table_name="brand_profiles")
    op.drop_index("ix_brand_profiles_org_id", table_name="brand_profiles")
    op.drop_table("brand_profiles")

    op.drop_index("ix_publish_jobs_created_at", table_name="publish_jobs")
    op.drop_index("ix_publish_jobs_org_id", table_name="publish_jobs")
    op.drop_table("publish_jobs")

    op.drop_index("ix_approvals_created_at", table_name="approvals")
    op.drop_index("ix_approvals_org_id", table_name="approvals")
    op.drop_table("approvals")

    op.drop_index("ix_content_items_created_at", table_name="content_items")
    op.drop_index("ix_content_items_org_id", table_name="content_items")
    op.drop_table("content_items")

    op.drop_index("ix_campaign_plans_created_at", table_name="campaign_plans")
    op.drop_index("ix_campaign_plans_org_id", table_name="campaign_plans")
    op.drop_table("campaign_plans")

    publish_job_status_enum.drop(bind, checkfirst=True)
    approval_status_enum.drop(bind, checkfirst=True)
    approval_entity_type_enum.drop(bind, checkfirst=True)
    content_item_status_enum.drop(bind, checkfirst=True)
    campaign_plan_status_enum.drop(bind, checkfirst=True)
