"""phase10 workflow engine core tables

Revision ID: 0011_phase10_workflow_engine
Revises: 0010_phase9_conn_health
Create Date: 2026-02-27 10:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_phase10_workflow_engine"
down_revision: str | None = "0010_phase9_conn_health"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE approval_entity_type_enum ADD VALUE IF NOT EXISTS 'workflow_run'")
    op.execute("ALTER TYPE approval_entity_type_enum ADD VALUE IF NOT EXISTS 'workflow_action_run'")

    op.create_table(
        "workflows",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("trigger_type", sa.Enum("event", "schedule", name="workflow_trigger_type_enum"), nullable=False),
        sa.Column("managed_by_pack", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("definition_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "key", name="uq_workflows_org_key"),
    )
    op.create_index("ix_workflows_org_id", "workflows", ["org_id"])
    op.create_index("ix_workflows_created_at", "workflows", ["created_at"])

    op.create_table(
        "workflow_runs",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_event_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "succeeded",
                "failed",
                "blocked",
                "approval_pending",
                "skipped",
                name="workflow_run_status_enum",
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("error_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("loop_guard_hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_runs_org_id", "workflow_runs", ["org_id"])
    op.create_index("ix_workflow_runs_created_at", "workflow_runs", ["created_at"])
    op.create_index("ix_workflow_runs_org_workflow_started_at", "workflow_runs", ["org_id", "workflow_id", "started_at"])

    op.create_table(
        "workflow_action_runs",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "succeeded",
                "failed",
                "blocked",
                "approval_pending",
                "skipped",
                name="workflow_action_run_status_enum",
            ),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("output_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("error_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "idempotency_key", name="uq_workflow_action_runs_org_idempotency"),
    )
    op.create_index("ix_workflow_action_runs_org_id", "workflow_action_runs", ["org_id"])
    op.create_index("ix_workflow_action_runs_created_at", "workflow_action_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_action_runs_created_at", table_name="workflow_action_runs")
    op.drop_index("ix_workflow_action_runs_org_id", table_name="workflow_action_runs")
    op.drop_table("workflow_action_runs")

    op.drop_index("ix_workflow_runs_org_workflow_started_at", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_created_at", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_org_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")

    op.drop_index("ix_workflows_created_at", table_name="workflows")
    op.drop_index("ix_workflows_org_id", table_name="workflows")
    op.drop_table("workflows")

    op.execute("DELETE FROM pg_enum WHERE enumlabel='workflow_action_run' AND enumtypid='approval_entity_type_enum'::regtype")
    op.execute("DELETE FROM pg_enum WHERE enumlabel='workflow_run' AND enumtypid='approval_entity_type_enum'::regtype")
