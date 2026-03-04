"""phase16 enterprise ai agents layer core tables

Revision ID: 0017_phase16_agents
Revises: 0016_phase15_vertical_packs
Create Date: 2026-03-03 10:30:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_phase16_agents"
down_revision: str | None = "0016_phase15_vertical_packs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'agent_run_status_enum') THEN
                CREATE TYPE agent_run_status_enum AS ENUM (
                    'planned',
                    'proposed',
                    'approved',
                    'executing',
                    'succeeded',
                    'failed',
                    'blocked'
                );
            END IF;
        END $$;
        """
    )

    if not _has_table(inspector, "agent_definitions"):
        op.create_table(
            "agent_definitions",
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("version", sa.String(length=40), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("supported_packs_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
            sa.Column("config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deletion_reason", sa.String(length=255), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", "version", name="uq_agent_definitions_name_version"),
        )

    if _has_table(inspector, "agent_definitions") and not _has_index(
        inspector, "agent_definitions", "ix_agent_definitions_created_at"
    ):
        op.create_index("ix_agent_definitions_created_at", "agent_definitions", ["created_at"])

    if not _has_table(inspector, "agent_runs"):
        op.create_table(
            "agent_runs",
            sa.Column("org_id", sa.Uuid(), nullable=False),
            sa.Column("agent_name", sa.String(length=120), nullable=False),
            sa.Column("agent_version", sa.String(length=40), nullable=False),
            sa.Column("trigger_type", sa.String(length=20), nullable=False, server_default="manual"),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "planned",
                    "proposed",
                    "approved",
                    "executing",
                    "succeeded",
                    "failed",
                    "blocked",
                    name="agent_run_status_enum",
                    create_type=False,
                ),
                nullable=False,
                server_default="planned",
            ),
            sa.Column("context_snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("perception_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("plan_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deletion_reason", sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if _has_table(inspector, "agent_runs") and not _has_index(inspector, "agent_runs", "ix_agent_runs_org_id"):
        op.create_index("ix_agent_runs_org_id", "agent_runs", ["org_id"])
    if _has_table(inspector, "agent_runs") and not _has_index(inspector, "agent_runs", "ix_agent_runs_created_at"):
        op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"])
    if _has_table(inspector, "agent_runs") and not _has_index(
        inspector, "agent_runs", "ix_agent_runs_org_agent_status"
    ):
        op.create_index("ix_agent_runs_org_agent_status", "agent_runs", ["org_id", "agent_name", "status"])

    if not _has_table(inspector, "agent_metrics"):
        op.create_table(
            "agent_metrics",
            sa.Column("org_id", sa.Uuid(), nullable=False),
            sa.Column("agent_name", sa.String(length=120), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("metrics_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deletion_reason", sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("org_id", "agent_name", "period_start", "period_end", name="uq_agent_metrics_period"),
        )

    if _has_table(inspector, "agent_metrics") and not _has_index(inspector, "agent_metrics", "ix_agent_metrics_org_id"):
        op.create_index("ix_agent_metrics_org_id", "agent_metrics", ["org_id"])
    if _has_table(inspector, "agent_metrics") and not _has_index(inspector, "agent_metrics", "ix_agent_metrics_created_at"):
        op.create_index("ix_agent_metrics_created_at", "agent_metrics", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "agent_metrics"):
        if _has_index(inspector, "agent_metrics", "ix_agent_metrics_created_at"):
            op.drop_index("ix_agent_metrics_created_at", table_name="agent_metrics")
        if _has_index(inspector, "agent_metrics", "ix_agent_metrics_org_id"):
            op.drop_index("ix_agent_metrics_org_id", table_name="agent_metrics")
        op.drop_table("agent_metrics")

    if _has_table(inspector, "agent_runs"):
        if _has_index(inspector, "agent_runs", "ix_agent_runs_org_agent_status"):
            op.drop_index("ix_agent_runs_org_agent_status", table_name="agent_runs")
        if _has_index(inspector, "agent_runs", "ix_agent_runs_created_at"):
            op.drop_index("ix_agent_runs_created_at", table_name="agent_runs")
        if _has_index(inspector, "agent_runs", "ix_agent_runs_org_id"):
            op.drop_index("ix_agent_runs_org_id", table_name="agent_runs")
        op.drop_table("agent_runs")

    if _has_table(inspector, "agent_definitions"):
        if _has_index(inspector, "agent_definitions", "ix_agent_definitions_created_at"):
            op.drop_index("ix_agent_definitions_created_at", table_name="agent_definitions")
        op.drop_table("agent_definitions")

    op.execute("DROP TYPE IF EXISTS agent_run_status_enum")
