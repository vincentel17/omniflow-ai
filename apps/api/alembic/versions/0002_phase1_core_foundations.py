"""phase1 core foundations

Revision ID: 0002_phase1_core_foundations
Revises: 0001_phase0_init
Create Date: 2026-02-23 00:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase1_core_foundations"
down_revision: str | None = "0001_phase0_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orgs",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_orgs_name"),
    )
    op.create_index("ix_orgs_created_at", "orgs", ["created_at"], unique=False)

    op.create_table(
        "users",
        sa.Column("external_auth_id", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("external_auth_id", name="uq_users_external_auth_id"),
    )
    op.create_index("ix_users_created_at", "users", ["created_at"], unique=False)

    op.create_table(
        "memberships",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Enum("OWNER", "ADMIN", "MEMBER", "AGENT", name="role_enum"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "user_id", name="uq_memberships_org_user"),
    )
    op.create_index("ix_memberships_org_id", "memberships", ["org_id"], unique=False)
    op.create_index("ix_memberships_created_at", "memberships", ["created_at"], unique=False)

    op.create_table(
        "integrations",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("external_account_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "org_id",
            "provider",
            "external_account_id",
            name="uq_integrations_org_provider_external",
        ),
    )
    op.create_index("ix_integrations_org_id", "integrations", ["org_id"], unique=False)
    op.create_index("ix_integrations_created_at", "integrations", ["created_at"], unique=False)

    op.create_table(
        "vertical_packs",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("pack_slug", sa.String(length=100), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_vertical_packs_org_id"),
    )
    op.create_index("ix_vertical_packs_org_id", "vertical_packs", ["org_id"], unique=False)
    op.create_index("ix_vertical_packs_created_at", "vertical_packs", ["created_at"], unique=False)

    op.create_table(
        "events",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("channel", sa.String(length=100), nullable=False),
        sa.Column("campaign_id", sa.String(length=255), nullable=True),
        sa.Column("content_id", sa.String(length=255), nullable=True),
        sa.Column("lead_id", sa.String(length=255), nullable=True),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_org_id", "events", ["org_id"], unique=False)
    op.create_index("ix_events_created_at", "events", ["created_at"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column("risk_tier", sa.Enum("TIER_0", "TIER_1", "TIER_2", "TIER_3", "TIER_4", name="risk_tier_enum"), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_org_id", "audit_logs", ["org_id"], unique=False)
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_org_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_events_created_at", table_name="events")
    op.drop_index("ix_events_org_id", table_name="events")
    op.drop_table("events")

    op.drop_index("ix_vertical_packs_created_at", table_name="vertical_packs")
    op.drop_index("ix_vertical_packs_org_id", table_name="vertical_packs")
    op.drop_table("vertical_packs")

    op.drop_index("ix_integrations_created_at", table_name="integrations")
    op.drop_index("ix_integrations_org_id", table_name="integrations")
    op.drop_table("integrations")

    op.drop_index("ix_memberships_created_at", table_name="memberships")
    op.drop_index("ix_memberships_org_id", table_name="memberships")
    op.drop_table("memberships")

    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_orgs_created_at", table_name="orgs")
    op.drop_table("orgs")

    op.execute("DROP TYPE IF EXISTS role_enum")
    op.execute("DROP TYPE IF EXISTS risk_tier_enum")
