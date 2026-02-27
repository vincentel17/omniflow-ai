"""phase13 billing subscriptions and usage metering

Revision ID: 0014_phase13_billing_core
Revises: 0013_phase12_softdelete_backfill
Create Date: 2026-02-28 10:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_phase13_billing_core"
down_revision: str | None = "0013_phase12_softdelete_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'billing_subscription_status_enum') THEN
                CREATE TYPE billing_subscription_status_enum AS ENUM ('trialing', 'active', 'past_due', 'canceled', 'suspended');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'org_status_enum') THEN
                CREATE TYPE org_status_enum AS ENUM ('active', 'suspended', 'canceled');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'usage_metric_type_enum') THEN
                CREATE TYPE usage_metric_type_enum AS ENUM ('post_created', 'ai_generation', 'workflow_executed', 'ad_impression', 'user_created');
            END IF;
        END $$;
        """
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "orgs", "org_status"):
        op.add_column(
            "orgs",
            sa.Column(
                "org_status",
                sa.dialects.postgresql.ENUM(
                    "active",
                    "suspended",
                    "canceled",
                    name="org_status_enum",
                    create_type=False,
                ),
                nullable=False,
                server_default="active",
            ),
        )

    op.create_table(
        "subscription_plans",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("price_monthly_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("price_yearly_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("entitlements_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_subscription_plans_name"),
    )
    op.create_index("ix_subscription_plans_created_at", "subscription_plans", ["created_at"])

    op.create_table(
        "org_subscriptions",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.dialects.postgresql.ENUM(
                "trialing",
                "active",
                "past_due",
                "canceled",
                "suspended",
                name="billing_subscription_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="trialing",
        ),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_org_subscriptions_org_id"),
        sa.UniqueConstraint("stripe_customer_id", name="uq_org_subscriptions_stripe_customer"),
        sa.UniqueConstraint("stripe_subscription_id", name="uq_org_subscriptions_stripe_subscription"),
    )
    op.create_index("ix_org_subscriptions_created_at", "org_subscriptions", ["created_at"])
    op.create_index("ix_org_subscriptions_org_status", "org_subscriptions", ["org_id", "status"])

    op.create_table(
        "usage_metrics",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column(
            "metric_type",
            sa.dialects.postgresql.ENUM(
                "post_created",
                "ai_generation",
                "workflow_executed",
                "ad_impression",
                "user_created",
                name="usage_metric_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "metric_type", "period_start", "period_end", name="uq_usage_metrics_period"),
    )
    op.create_index("ix_usage_metrics_org_created_at", "usage_metrics", ["org_id", "created_at"])
    op.create_index("ix_usage_metrics_org_metric_period", "usage_metrics", ["org_id", "metric_type", "period_start"])

    op.create_table(
        "global_admins",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_global_admins_user_id"),
    )
    op.create_index("ix_global_admins_created_at", "global_admins", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_global_admins_created_at", table_name="global_admins")
    op.drop_table("global_admins")

    op.drop_index("ix_usage_metrics_org_metric_period", table_name="usage_metrics")
    op.drop_index("ix_usage_metrics_org_created_at", table_name="usage_metrics")
    op.drop_table("usage_metrics")

    op.drop_index("ix_org_subscriptions_org_status", table_name="org_subscriptions")
    op.drop_index("ix_org_subscriptions_created_at", table_name="org_subscriptions")
    op.drop_table("org_subscriptions")

    op.drop_index("ix_subscription_plans_created_at", table_name="subscription_plans")
    op.drop_table("subscription_plans")
