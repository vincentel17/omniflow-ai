"""phase4 unified inbox and lead engine tables

Revision ID: 0005_phase4_inbox_lead_engine
Revises: 0004_phase2_connector_framework
Create Date: 2026-02-24 10:40:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_phase4_inbox_lead_engine"
down_revision: str | None = "0004_phase2_connector_framework"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inbox_thread_type_enum = sa.Enum(
        "comment",
        "dm",
        "form",
        "email",
        "sms",
        "other",
        name="inbox_thread_type_enum",
    )
    inbox_thread_status_enum = sa.Enum("open", "pending", "closed", name="inbox_thread_status_enum")
    inbox_message_direction_enum = sa.Enum("inbound", "outbound", name="inbox_message_direction_enum")
    lead_status_enum = sa.Enum("new", "qualified", "unqualified", "archived", name="lead_status_enum")
    nurture_task_type_enum = sa.Enum("email", "sms", "call", "task", name="nurture_task_type_enum")
    nurture_task_status_enum = sa.Enum("open", "done", "canceled", name="nurture_task_status_enum")

    op.create_table(
        "pipelines",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "slug", name="uq_pipelines_org_slug"),
    )
    op.create_index("ix_pipelines_org_id", "pipelines", ["org_id"], unique=False)
    op.create_index("ix_pipelines_created_at", "pipelines", ["created_at"], unique=False)

    op.create_table(
        "leads",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("status", lead_status_enum, nullable=False, server_default=sa.text("'new'")),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("location_json", sa.JSON(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_org_id", "leads", ["org_id"], unique=False)
    op.create_index("ix_leads_created_at", "leads", ["created_at"], unique=False)

    op.create_table(
        "stages",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("exit_on_win", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["pipeline_id"], ["pipelines.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "pipeline_id", "slug", name="uq_stages_org_pipeline_slug"),
    )
    op.create_index("ix_stages_org_id", "stages", ["org_id"], unique=False)
    op.create_index("ix_stages_created_at", "stages", ["created_at"], unique=False)

    op.create_table(
        "inbox_threads",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("account_ref", sa.String(length=255), nullable=False),
        sa.Column("external_thread_id", sa.String(length=255), nullable=False),
        sa.Column("thread_type", inbox_thread_type_enum, nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("participants_json", sa.JSON(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", inbox_thread_status_enum, nullable=False, server_default=sa.text("'open'")),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_to_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "org_id",
            "provider",
            "account_ref",
            "external_thread_id",
            name="uq_inbox_threads_org_provider_account_external",
        ),
    )
    op.create_index("ix_inbox_threads_org_id", "inbox_threads", ["org_id"], unique=False)
    op.create_index("ix_inbox_threads_created_at", "inbox_threads", ["created_at"], unique=False)

    op.create_table(
        "inbox_messages",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("external_message_id", sa.String(length=255), nullable=False),
        sa.Column("direction", inbox_message_direction_enum, nullable=False),
        sa.Column("sender_ref", sa.String(length=255), nullable=False),
        sa.Column("sender_display", sa.String(length=255), nullable=False),
        sa.Column("body_text", sa.String(length=8000), nullable=False),
        sa.Column("body_raw_json", sa.JSON(), nullable=False),
        sa.Column("flags_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["thread_id"], ["inbox_threads.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "thread_id", "external_message_id", name="uq_inbox_messages_org_thread_external"),
    )
    op.create_index("ix_inbox_messages_org_id", "inbox_messages", ["org_id"], unique=False)
    op.create_index("ix_inbox_messages_created_at", "inbox_messages", ["created_at"], unique=False)

    op.create_table(
        "lead_scores",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("score_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("score_json", sa.JSON(), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False, server_default=sa.text("'v1'")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "lead_id", name="uq_lead_scores_org_lead"),
    )
    op.create_index("ix_lead_scores_org_id", "lead_scores", ["org_id"], unique=False)
    op.create_index("ix_lead_scores_created_at", "lead_scores", ["created_at"], unique=False)

    op.create_table(
        "lead_assignments",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_to_user_id", sa.Uuid(), nullable=False),
        sa.Column("rule_applied", sa.String(length=100), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "lead_id", name="uq_lead_assignments_org_lead"),
    )
    op.create_index("ix_lead_assignments_org_id", "lead_assignments", ["org_id"], unique=False)
    op.create_index("ix_lead_assignments_created_at", "lead_assignments", ["created_at"], unique=False)

    op.create_table(
        "nurture_tasks",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("type", nurture_task_type_enum, nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", nurture_task_status_enum, nullable=False, server_default=sa.text("'open'")),
        sa.Column("template_key", sa.String(length=100), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_nurture_tasks_org_id", "nurture_tasks", ["org_id"], unique=False)
    op.create_index("ix_nurture_tasks_created_at", "nurture_tasks", ["created_at"], unique=False)

    op.create_table(
        "sla_configs",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("response_time_minutes", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("escalation_minutes", sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column("notify_channels_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_sla_configs_org_id"),
    )
    op.create_index("ix_sla_configs_org_id", "sla_configs", ["org_id"], unique=False)
    op.create_index("ix_sla_configs_created_at", "sla_configs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sla_configs_created_at", table_name="sla_configs")
    op.drop_index("ix_sla_configs_org_id", table_name="sla_configs")
    op.drop_table("sla_configs")

    op.drop_index("ix_nurture_tasks_created_at", table_name="nurture_tasks")
    op.drop_index("ix_nurture_tasks_org_id", table_name="nurture_tasks")
    op.drop_table("nurture_tasks")

    op.drop_index("ix_lead_assignments_created_at", table_name="lead_assignments")
    op.drop_index("ix_lead_assignments_org_id", table_name="lead_assignments")
    op.drop_table("lead_assignments")

    op.drop_index("ix_lead_scores_created_at", table_name="lead_scores")
    op.drop_index("ix_lead_scores_org_id", table_name="lead_scores")
    op.drop_table("lead_scores")

    op.drop_index("ix_inbox_messages_created_at", table_name="inbox_messages")
    op.drop_index("ix_inbox_messages_org_id", table_name="inbox_messages")
    op.drop_table("inbox_messages")

    op.drop_index("ix_inbox_threads_created_at", table_name="inbox_threads")
    op.drop_index("ix_inbox_threads_org_id", table_name="inbox_threads")
    op.drop_table("inbox_threads")

    op.drop_index("ix_stages_created_at", table_name="stages")
    op.drop_index("ix_stages_org_id", table_name="stages")
    op.drop_table("stages")

    op.drop_index("ix_leads_created_at", table_name="leads")
    op.drop_index("ix_leads_org_id", table_name="leads")
    op.drop_table("leads")

    op.drop_index("ix_pipelines_created_at", table_name="pipelines")
    op.drop_index("ix_pipelines_org_id", table_name="pipelines")
    op.drop_table("pipelines")

    sa.Enum(name="nurture_task_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="nurture_task_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="lead_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="inbox_message_direction_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="inbox_thread_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="inbox_thread_type_enum").drop(op.get_bind(), checkfirst=True)
