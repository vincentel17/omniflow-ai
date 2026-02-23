"""phase6 attribution, analytics, and link click tracking

Revision ID: 0007_phase6_attr_analytics
Revises: 0006_phase5_presence_seo_rep
Create Date: 2026-02-24 16:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_phase6_attr_analytics"
down_revision: str | None = "0006_phase5_presence_seo_rep"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "org_settings",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_org_settings_org_id"),
    )
    op.create_index("ix_org_settings_org_id", "org_settings", ["org_id"], unique=False)
    op.create_index("ix_org_settings_created_at", "org_settings", ["created_at"], unique=False)

    op.create_table(
        "link_clicks",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("tracked_link_id", sa.Uuid(), nullable=False),
        sa.Column("short_code", sa.String(length=32), nullable=False),
        sa.Column("clicked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("referrer", sa.String(length=2048), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=128), nullable=True),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["tracked_link_id"], ["link_tracking.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_link_clicks_org_id", "link_clicks", ["org_id"], unique=False)
    op.create_index("ix_link_clicks_created_at", "link_clicks", ["created_at"], unique=False)
    op.create_index("ix_link_clicks_org_clicked_at", "link_clicks", ["org_id", "clicked_at"], unique=False)

    op.create_unique_constraint("uq_link_tracking_short_code", "link_tracking", ["short_code"])
    op.create_index("ix_link_tracking_org_created_at", "link_tracking", ["org_id", "created_at"], unique=False)

    op.create_index("ix_events_org_type_created_at", "events", ["org_id", "type", "created_at"], unique=False)
    op.create_index("ix_events_org_created_at", "events", ["org_id", "created_at"], unique=False)
    op.create_index(
        "ix_publish_jobs_org_status_schedule_at",
        "publish_jobs",
        ["org_id", "status", "schedule_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_org_settings_created_at", table_name="org_settings")
    op.drop_index("ix_org_settings_org_id", table_name="org_settings")
    op.drop_table("org_settings")

    op.drop_index("ix_publish_jobs_org_status_schedule_at", table_name="publish_jobs")
    op.drop_index("ix_events_org_created_at", table_name="events")
    op.drop_index("ix_events_org_type_created_at", table_name="events")

    op.drop_index("ix_link_tracking_org_created_at", table_name="link_tracking")
    op.drop_constraint("uq_link_tracking_short_code", "link_tracking", type_="unique")

    op.drop_index("ix_link_clicks_org_clicked_at", table_name="link_clicks")
    op.drop_index("ix_link_clicks_created_at", table_name="link_clicks")
    op.drop_index("ix_link_clicks_org_id", table_name="link_clicks")
    op.drop_table("link_clicks")
