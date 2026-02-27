"""phase12 soft-delete column backfill for legacy tables

Revision ID: 0013_phase12_softdelete_backfill
Revises: 0012_phase12_compliance_gov
Create Date: 2026-02-28 00:20:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_phase12_softdelete_backfill"
down_revision: str | None = "0012_phase12_compliance_gov"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in inspector.get_table_names():
        has_deleted_at = _has_column(inspector, table_name, "deleted_at")
        has_deletion_reason = _has_column(inspector, table_name, "deletion_reason")

        if has_deleted_at and not has_deletion_reason:
            op.add_column(table_name, sa.Column("deletion_reason", sa.String(length=255), nullable=True))

        if has_deletion_reason and not has_deleted_at:
            op.add_column(table_name, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in inspector.get_table_names():
        has_deleted_at = _has_column(inspector, table_name, "deleted_at")
        has_deletion_reason = _has_column(inspector, table_name, "deletion_reason")

        if has_deleted_at and has_deletion_reason:
            op.drop_column(table_name, "deletion_reason")
