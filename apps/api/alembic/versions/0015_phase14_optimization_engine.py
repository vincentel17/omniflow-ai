"""phase14 optimization engine

Revision ID: 0015_phase14_optimization_engine
Revises: 0014_phase13_billing_core
Create Date: 2026-02-28 16:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_phase14_optimization_engine"
down_revision: str | None = "0014_phase13_billing_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ad_accounts (
            org_id UUID NOT NULL REFERENCES orgs(id),
            provider VARCHAR(32) NOT NULL,
            account_ref VARCHAR(255) NOT NULL,
            display_name VARCHAR(255) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            linked_connector_account_id UUID NULL REFERENCES connector_accounts(id),
            id UUID PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ NULL,
            deletion_reason VARCHAR(255) NULL
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ad_campaigns (
            org_id UUID NOT NULL REFERENCES orgs(id),
            provider VARCHAR(32) NOT NULL,
            ad_account_id UUID NOT NULL REFERENCES ad_accounts(id),
            name VARCHAR(255) NOT NULL,
            objective VARCHAR(32) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'draft',
            daily_budget_usd FLOAT NOT NULL DEFAULT 0,
            lifetime_budget_usd FLOAT NULL,
            start_at TIMESTAMPTZ NULL,
            end_at TIMESTAMPTZ NULL,
            targeting_json JSON NOT NULL DEFAULT '{}'::json,
            utm_json JSON NOT NULL DEFAULT '{}'::json,
            created_by UUID NOT NULL REFERENCES users(id),
            external_id VARCHAR(255) NULL,
            last_synced_at TIMESTAMPTZ NULL,
            last_error VARCHAR(500) NULL,
            id UUID PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ NULL,
            deletion_reason VARCHAR(255) NULL
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ad_spend_ledger (
            org_id UUID NOT NULL REFERENCES orgs(id),
            provider VARCHAR(32) NOT NULL,
            campaign_id UUID NOT NULL REFERENCES ad_campaigns(id),
            day DATE NOT NULL,
            spend_usd FLOAT NOT NULL DEFAULT 0,
            impressions INTEGER NULL,
            clicks INTEGER NULL,
            source VARCHAR(50) NOT NULL DEFAULT 'mock',
            id UUID PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ NULL,
            deletion_reason VARCHAR(255) NULL
        );
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'model_status_enum') THEN
                CREATE TYPE model_status_enum AS ENUM ('active', 'inactive', 'experimental', 'degraded');
            END IF;
        END $$;
        """
    )

    op.create_table(
        "predictive_lead_scores",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("score_probability", sa.Float(), nullable=False),
        sa.Column("feature_importance_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("predicted_stage_probability_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "lead_id", "model_version", name="uq_predictive_lead_scores_org_lead_model"),
    )
    op.create_index("ix_predictive_lead_scores_org_id", "predictive_lead_scores", ["org_id"])
    op.create_index("ix_predictive_lead_scores_created_at", "predictive_lead_scores", ["created_at"])

    op.create_table(
        "posting_optimizations",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=80), nullable=False),
        sa.Column("best_day_of_week", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("best_hour", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("model_version", sa.String(length=64), nullable=False, server_default="post_timing_model_v1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "channel", name="uq_posting_optimizations_org_channel"),
    )
    op.create_index("ix_posting_optimizations_org_id", "posting_optimizations", ["org_id"])
    op.create_index("ix_posting_optimizations_updated_at", "posting_optimizations", ["updated_at"])

    op.create_table(
        "ad_budget_recommendations",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("recommended_daily_budget", sa.Float(), nullable=False),
        sa.Column("reasoning_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("projected_cpl", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False, server_default="ad_budget_allocator_v1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["ad_campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ad_budget_recommendations_org_id", "ad_budget_recommendations", ["org_id"])
    op.create_index("ix_ad_budget_recommendations_campaign_id", "ad_budget_recommendations", ["campaign_id"])
    op.create_index("ix_ad_budget_recommendations_created_at", "ad_budget_recommendations", ["created_at"])

    op.create_table(
        "model_metadata",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("training_window", sa.String(length=120), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "status",
            sa.dialects.postgresql.ENUM(
                "active",
                "inactive",
                "experimental",
                "degraded",
                name="model_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="inactive",
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", "version", name="uq_model_metadata_org_name_version"),
    )
    op.create_index("ix_model_metadata_org_id", "model_metadata", ["org_id"])
    op.create_index("ix_model_metadata_created_at", "model_metadata", ["created_at"])

    op.create_table(
        "org_optimization_settings",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("enable_predictive_scoring", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enable_post_timing_optimization", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enable_nurture_optimization", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enable_ad_budget_recommendations", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("auto_apply_low_risk_optimizations", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_org_optimization_settings_org_id"),
    )
    op.create_index("ix_org_optimization_settings_org_id", "org_optimization_settings", ["org_id"])
    op.create_index("ix_org_optimization_settings_created_at", "org_optimization_settings", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_org_optimization_settings_created_at", table_name="org_optimization_settings")
    op.drop_index("ix_org_optimization_settings_org_id", table_name="org_optimization_settings")
    op.drop_table("org_optimization_settings")

    op.drop_index("ix_model_metadata_created_at", table_name="model_metadata")
    op.drop_index("ix_model_metadata_org_id", table_name="model_metadata")
    op.drop_table("model_metadata")

    op.drop_index("ix_ad_budget_recommendations_created_at", table_name="ad_budget_recommendations")
    op.drop_index("ix_ad_budget_recommendations_campaign_id", table_name="ad_budget_recommendations")
    op.drop_index("ix_ad_budget_recommendations_org_id", table_name="ad_budget_recommendations")
    op.drop_table("ad_budget_recommendations")

    op.drop_index("ix_posting_optimizations_updated_at", table_name="posting_optimizations")
    op.drop_index("ix_posting_optimizations_org_id", table_name="posting_optimizations")
    op.drop_table("posting_optimizations")

    op.drop_index("ix_predictive_lead_scores_created_at", table_name="predictive_lead_scores")
    op.drop_index("ix_predictive_lead_scores_org_id", table_name="predictive_lead_scores")
    op.drop_table("predictive_lead_scores")

    # Phase-14 bootstrap tables may exist when running in branches without
    # dedicated Phase-11 migrations; remove them to avoid FK teardown failures.
    op.execute("DROP TABLE IF EXISTS ad_spend_ledger")
    op.execute("DROP TABLE IF EXISTS ad_campaigns")
    op.execute("DROP TABLE IF EXISTS ad_accounts")

    op.execute("DROP TYPE IF EXISTS model_status_enum")
