"""phase9 connector health diagnostics fields

Revision ID: 0010_phase9_conn_health
Revises: 0009_phase8_ops_onboarding
Create Date: 2026-02-26 12:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_phase9_conn_health"
down_revision: str | None = "0009_phase8_ops_onboarding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("connector_health", sa.Column("last_http_status", sa.Integer(), nullable=True))
    op.add_column("connector_health", sa.Column("last_provider_error_code", sa.String(length=100), nullable=True))
    op.add_column("connector_health", sa.Column("last_rate_limit_reset_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("connector_health", "last_rate_limit_reset_at")
    op.drop_column("connector_health", "last_provider_error_code")
    op.drop_column("connector_health", "last_http_status")

