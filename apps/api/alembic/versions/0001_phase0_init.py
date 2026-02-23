"""phase0 init

Revision ID: 0001_phase0_init
Revises:
Create Date: 2026-02-22 00:00:00
"""

from typing import Sequence

from alembic import op

revision: str = "0001_phase0_init"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SELECT 1")


def downgrade() -> None:
    op.execute("SELECT 1")
