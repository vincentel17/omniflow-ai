"""phase2 connector framework tables

Revision ID: 0004_phase2_connector_framework
Revises: 0003_phase3_growth_loop_core
Create Date: 2026-02-23 22:10:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_phase2_connector_framework"
down_revision: str | None = "0003_phase3_growth_loop_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_accounts",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("account_ref", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "provider", "account_ref", name="uq_connector_accounts_org_provider_ref"),
    )
    op.create_index("ix_connector_accounts_org_id", "connector_accounts", ["org_id"], unique=False)
    op.create_index("ix_connector_accounts_created_at", "connector_accounts", ["created_at"], unique=False)

    op.create_table(
        "oauth_tokens",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("account_ref", sa.String(length=255), nullable=False),
        sa.Column("access_token_enc", sa.String(length=2048), nullable=False),
        sa.Column("refresh_token_enc", sa.String(length=2048), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes_json", sa.JSON(), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "provider", "account_ref", name="uq_oauth_tokens_org_provider_ref"),
    )
    op.create_index("ix_oauth_tokens_org_id", "oauth_tokens", ["org_id"], unique=False)
    op.create_index("ix_oauth_tokens_created_at", "oauth_tokens", ["created_at"], unique=False)

    op.create_table(
        "connector_health",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("account_ref", sa.String(length=255), nullable=False),
        sa.Column("last_ok_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_msg", sa.String(length=500), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "provider", "account_ref", name="uq_connector_health_org_provider_ref"),
    )
    op.create_index("ix_connector_health_org_id", "connector_health", ["org_id"], unique=False)
    op.create_index("ix_connector_health_created_at", "connector_health", ["created_at"], unique=False)

    op.create_table(
        "connector_workflow_runs",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("account_ref", sa.String(length=255), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "idempotency_key", name="uq_connector_workflow_runs_org_idempotency"),
    )
    op.create_index("ix_connector_workflow_runs_org_id", "connector_workflow_runs", ["org_id"], unique=False)
    op.create_index("ix_connector_workflow_runs_created_at", "connector_workflow_runs", ["created_at"], unique=False)

    op.create_table(
        "connector_dead_letters",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("account_ref", sa.String(length=255), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_connector_dead_letters_org_id", "connector_dead_letters", ["org_id"], unique=False)
    op.create_index("ix_connector_dead_letters_created_at", "connector_dead_letters", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_connector_dead_letters_created_at", table_name="connector_dead_letters")
    op.drop_index("ix_connector_dead_letters_org_id", table_name="connector_dead_letters")
    op.drop_table("connector_dead_letters")

    op.drop_index("ix_connector_workflow_runs_created_at", table_name="connector_workflow_runs")
    op.drop_index("ix_connector_workflow_runs_org_id", table_name="connector_workflow_runs")
    op.drop_table("connector_workflow_runs")

    op.drop_index("ix_connector_health_created_at", table_name="connector_health")
    op.drop_index("ix_connector_health_org_id", table_name="connector_health")
    op.drop_table("connector_health")

    op.drop_index("ix_oauth_tokens_created_at", table_name="oauth_tokens")
    op.drop_index("ix_oauth_tokens_org_id", table_name="oauth_tokens")
    op.drop_table("oauth_tokens")

    op.drop_index("ix_connector_accounts_created_at", table_name="connector_accounts")
    op.drop_index("ix_connector_accounts_org_id", table_name="connector_accounts")
    op.drop_table("connector_accounts")

