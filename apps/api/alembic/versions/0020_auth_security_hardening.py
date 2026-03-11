"""add auth security fields and audit events

Revision ID: 0020_auth_security
Revises: 0019_auth_creds_reset
Create Date: 2026-03-11 18:20:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_auth_security"
down_revision: str | None = "0019_auth_creds_reset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"))
    op.alter_column("users", "session_version", server_default=None)

    op.create_table(
        "auth_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_audit_events_user_id", "auth_audit_events", ["user_id"], unique=False)
    op.create_index("ix_auth_audit_events_org_id", "auth_audit_events", ["org_id"], unique=False)
    op.create_index("ix_auth_audit_events_event_type", "auth_audit_events", ["event_type"], unique=False)
    op.create_index("ix_auth_audit_events_created_at", "auth_audit_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auth_audit_events_created_at", table_name="auth_audit_events")
    op.drop_index("ix_auth_audit_events_event_type", table_name="auth_audit_events")
    op.drop_index("ix_auth_audit_events_org_id", table_name="auth_audit_events")
    op.drop_index("ix_auth_audit_events_user_id", table_name="auth_audit_events")
    op.drop_table("auth_audit_events")
    op.drop_column("users", "session_version")
