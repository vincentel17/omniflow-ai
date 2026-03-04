"""phase16 add agent approval entity enum values

Revision ID: 0018_p16_approval_enum
Revises: 0017_phase16_agents
Create Date: 2026-03-03 14:45:00
"""

from typing import Sequence

from alembic import op

revision: str = "0018_p16_approval_enum"
down_revision: str | None = "0017_phase16_agents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE approval_entity_type_enum ADD VALUE IF NOT EXISTS 'agent_run'")
    op.execute("ALTER TYPE approval_entity_type_enum ADD VALUE IF NOT EXISTS 'agent_plan'")


def downgrade() -> None:
    # PostgreSQL enum value removal is unsafe for live data; keep downgrade as no-op.
    return None
