"""phase12 compliance governance core tables

Revision ID: 0012_phase12_compliance_gov
Revises: 0011_phase10_workflow_engine
Create Date: 2026-02-27 20:30:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_phase12_compliance_gov"
down_revision: str | None = "0011_phase10_workflow_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dsar_request_type_enum') THEN
                CREATE TYPE dsar_request_type_enum AS ENUM ('access', 'delete', 'export');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dsar_request_status_enum') THEN
                CREATE TYPE dsar_request_status_enum AS ENUM ('requested', 'in_progress', 'completed', 'rejected');
            END IF;
        END $$;
        """
    )

    op.create_table(
        "data_retention_policies",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("hard_delete_after_days", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "entity_type", name="uq_data_retention_policy_org_entity"),
    )
    op.create_index("ix_data_retention_policies_org_id", "data_retention_policies", ["org_id"])
    op.create_index("ix_data_retention_policies_created_at", "data_retention_policies", ["created_at"])

    op.create_table(
        "dsar_requests",
        sa.Column(
            "request_type",
            sa.dialects.postgresql.ENUM(
                "access",
                "delete",
                "export",
                name="dsar_request_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.dialects.postgresql.ENUM(
                "requested",
                "in_progress",
                "completed",
                "rejected",
                name="dsar_request_status_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("subject_identifier", sa.String(length=255), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("export_ref", sa.String(length=1024), nullable=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dsar_requests_org_id", "dsar_requests", ["org_id"])
    op.create_index("ix_dsar_requests_created_at", "dsar_requests", ["created_at"])
    op.create_index("ix_dsar_requests_org_status", "dsar_requests", ["org_id", "status"])

    op.create_table(
        "permission_audit_reports",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("findings_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("recommendations_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_permission_audit_reports_org_id", "permission_audit_reports", ["org_id"])
    op.create_index("ix_permission_audit_reports_created_at", "permission_audit_reports", ["created_at"])

    op.add_column("leads", sa.Column("pii_flags_json", sa.JSON(), nullable=True))
    op.add_column("leads", sa.Column("sensitive_level", sa.String(length=16), nullable=False, server_default="medium"))

    op.add_column("inbox_messages", sa.Column("pii_flags_json", sa.JSON(), nullable=True))
    op.add_column(
        "inbox_messages",
        sa.Column("sensitive_level", sa.String(length=16), nullable=False, server_default="medium"),
    )

    op.add_column("re_deals", sa.Column("pii_flags_json", sa.JSON(), nullable=True))
    op.add_column("re_deals", sa.Column("sensitive_level", sa.String(length=16), nullable=False, server_default="high"))

    op.add_column("re_cma_reports", sa.Column("pii_flags_json", sa.JSON(), nullable=True))
    op.add_column(
        "re_cma_reports",
        sa.Column("sensitive_level", sa.String(length=16), nullable=False, server_default="high"),
    )

    op.add_column("reputation_reviews", sa.Column("pii_flags_json", sa.JSON(), nullable=True))
    op.add_column(
        "reputation_reviews",
        sa.Column("sensitive_level", sa.String(length=16), nullable=False, server_default="medium"),
    )


def downgrade() -> None:
    op.drop_column("reputation_reviews", "sensitive_level")
    op.drop_column("reputation_reviews", "pii_flags_json")

    op.drop_column("re_cma_reports", "sensitive_level")
    op.drop_column("re_cma_reports", "pii_flags_json")

    op.drop_column("re_deals", "sensitive_level")
    op.drop_column("re_deals", "pii_flags_json")

    op.drop_column("inbox_messages", "sensitive_level")
    op.drop_column("inbox_messages", "pii_flags_json")

    op.drop_column("leads", "sensitive_level")
    op.drop_column("leads", "pii_flags_json")

    op.drop_index("ix_permission_audit_reports_created_at", table_name="permission_audit_reports")
    op.drop_index("ix_permission_audit_reports_org_id", table_name="permission_audit_reports")
    op.drop_table("permission_audit_reports")

    op.drop_index("ix_dsar_requests_org_status", table_name="dsar_requests")
    op.drop_index("ix_dsar_requests_created_at", table_name="dsar_requests")
    op.drop_index("ix_dsar_requests_org_id", table_name="dsar_requests")
    op.drop_table("dsar_requests")

    op.drop_index("ix_data_retention_policies_created_at", table_name="data_retention_policies")
    op.drop_index("ix_data_retention_policies_org_id", table_name="data_retention_policies")
    op.drop_table("data_retention_policies")
