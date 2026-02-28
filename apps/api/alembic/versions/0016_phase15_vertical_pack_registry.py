"""phase15 vertical pack registry and plan vertical entitlements

Revision ID: 0016_phase15_vertical_packs
Revises: 0015_phase14_optimization_engine
Create Date: 2026-02-28 21:30:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_phase15_vertical_packs"
down_revision: str | None = "0015_phase14_optimization_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "subscription_plans"):
        if not _has_column(inspector, "subscription_plans", "allowed_verticals_json"):
            op.add_column(
                "subscription_plans",
                sa.Column(
                    "allowed_verticals_json",
                    sa.JSON(),
                    nullable=False,
                    server_default=sa.text("'[]'::json"),
                ),
            )
        if not _has_column(inspector, "subscription_plans", "custom_pack_pricing_json"):
            op.add_column(
                "subscription_plans",
                sa.Column(
                    "custom_pack_pricing_json",
                    sa.JSON(),
                    nullable=False,
                    server_default=sa.text("'{}'::json"),
                ),
            )

    if not _has_table(inspector, "vertical_pack_registry"):
        op.create_table(
            "vertical_pack_registry",
            sa.Column("slug", sa.String(length=100), nullable=False),
            sa.Column("version", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("checksum", sa.String(length=128), nullable=False),
            sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deletion_reason", sa.String(length=255), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug", "version", name="uq_vertical_pack_registry_slug_version"),
        )
        op.create_index("ix_vertical_pack_registry_installed_at", "vertical_pack_registry", ["installed_at"])
        op.create_index("ix_vertical_pack_registry_created_at", "vertical_pack_registry", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "vertical_pack_registry"):
        op.drop_index("ix_vertical_pack_registry_created_at", table_name="vertical_pack_registry")
        op.drop_index("ix_vertical_pack_registry_installed_at", table_name="vertical_pack_registry")
        op.drop_table("vertical_pack_registry")

    if _has_table(inspector, "subscription_plans"):
        if _has_column(inspector, "subscription_plans", "custom_pack_pricing_json"):
            op.drop_column("subscription_plans", "custom_pack_pricing_json")
        if _has_column(inspector, "subscription_plans", "allowed_verticals_json"):
            op.drop_column("subscription_plans", "allowed_verticals_json")
