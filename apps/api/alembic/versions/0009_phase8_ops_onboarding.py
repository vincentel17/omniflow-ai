"""phase8 ops settings and onboarding session

Revision ID: 0009_phase8_ops_onboarding
Revises: 0008_phase7_real_estate_pack
Create Date: 2026-02-26 10:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_phase8_ops_onboarding"
down_revision: str | None = "0008_phase7_real_estate_pack"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "onboarding_sessions",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("in_progress", "completed", name="onboarding_session_status_enum"),
            nullable=False,
        ),
        sa.Column("steps_json", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_onboarding_sessions_org_id", "onboarding_sessions", ["org_id"], unique=False)
    op.create_index("ix_onboarding_sessions_created_at", "onboarding_sessions", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_onboarding_sessions_created_at", table_name="onboarding_sessions")
    op.drop_index("ix_onboarding_sessions_org_id", table_name="onboarding_sessions")
    op.drop_table("onboarding_sessions")
    op.execute("DROP TYPE IF EXISTS onboarding_session_status_enum")
