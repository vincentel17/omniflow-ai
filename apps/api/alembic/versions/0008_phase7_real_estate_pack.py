"""phase7 real estate productivity pack

Revision ID: 0008_phase7_real_estate_pack
Revises: 0007_phase6_attr_analytics
Create Date: 2026-02-24 19:10:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_phase7_real_estate_pack"
down_revision: str | None = "0007_phase6_attr_analytics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "re_deals",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("deal_type", sa.Enum("buyer", "seller", "listing", "lease", name="re_deal_type_enum"), nullable=False),
        sa.Column("status", sa.Enum("active", "archived", name="re_deal_status_enum"), nullable=False),
        sa.Column("pipeline_stage", sa.String(length=100), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("primary_contact_name", sa.String(length=255), nullable=True),
        sa.Column("primary_contact_email", sa.String(length=320), nullable=True),
        sa.Column("primary_contact_phone", sa.String(length=64), nullable=True),
        sa.Column("property_address_json", sa.JSON(), nullable=False),
        sa.Column("important_dates_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_re_deals_org_id", "re_deals", ["org_id"], unique=False)
    op.create_index("ix_re_deals_created_at", "re_deals", ["created_at"], unique=False)

    op.create_table(
        "re_checklist_templates",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "deal_type",
            sa.Enum("buyer", "seller", "listing", "lease", name="re_checklist_template_deal_type_enum"),
            nullable=False,
        ),
        sa.Column("state_code", sa.String(length=10), nullable=True),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "org_id",
            "name",
            "deal_type",
            "state_code",
            name="uq_re_checklist_templates_org_name_type_state",
        ),
    )
    op.create_index("ix_re_checklist_templates_org_id", "re_checklist_templates", ["org_id"], unique=False)
    op.create_index("ix_re_checklist_templates_created_at", "re_checklist_templates", ["created_at"], unique=False)

    op.create_table(
        "re_checklist_items",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Enum("open", "done", "canceled", name="re_checklist_item_status_enum"), nullable=False),
        sa.Column("assigned_to_user_id", sa.Uuid(), nullable=True),
        sa.Column("source_template_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["deal_id"], ["re_deals.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["source_template_id"], ["re_checklist_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_re_checklist_items_org_id", "re_checklist_items", ["org_id"], unique=False)
    op.create_index("ix_re_checklist_items_created_at", "re_checklist_items", ["created_at"], unique=False)

    op.create_table(
        "re_document_requests",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("doc_type", sa.String(length=100), nullable=False),
        sa.Column("requested_from", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum("requested", "received", "verified", name="re_document_request_status_enum"),
            nullable=False,
        ),
        sa.Column("file_ref", sa.String(length=2048), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["deal_id"], ["re_deals.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_re_document_requests_org_id", "re_document_requests", ["org_id"], unique=False)
    op.create_index("ix_re_document_requests_created_at", "re_document_requests", ["created_at"], unique=False)

    op.create_table(
        "re_communication_logs",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.Enum("email", "sms", "call", "note", name="re_communication_channel_enum"), nullable=False),
        sa.Column("direction", sa.Enum("outbound", "inbound", name="re_communication_direction_enum"), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("body_text", sa.String(length=8000), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["deal_id"], ["re_deals.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["thread_id"], ["inbox_threads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_re_communication_logs_org_id", "re_communication_logs", ["org_id"], unique=False)
    op.create_index("ix_re_communication_logs_created_at", "re_communication_logs", ["created_at"], unique=False)

    op.create_table(
        "re_cma_reports",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("deal_id", sa.Uuid(), nullable=True),
        sa.Column("subject_property_json", sa.JSON(), nullable=False),
        sa.Column("pricing_json", sa.JSON(), nullable=False),
        sa.Column("narrative_text", sa.String(length=32000), nullable=True),
        sa.Column("risk_tier", sa.Enum("TIER_0", "TIER_1", "TIER_2", "TIER_3", "TIER_4", name="risk_tier_enum"), nullable=False),
        sa.Column("policy_warnings_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["deal_id"], ["re_deals.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_re_cma_reports_org_id", "re_cma_reports", ["org_id"], unique=False)
    op.create_index("ix_re_cma_reports_created_at", "re_cma_reports", ["created_at"], unique=False)

    op.create_table(
        "re_cma_comparables",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("cma_report_id", sa.Uuid(), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=False),
        sa.Column("status", sa.Enum("sold", "active", "pending", name="re_cma_comparable_status_enum"), nullable=False),
        sa.Column("sold_price", sa.Integer(), nullable=True),
        sa.Column("list_price", sa.Integer(), nullable=True),
        sa.Column("beds", sa.Float(), nullable=True),
        sa.Column("baths", sa.Float(), nullable=True),
        sa.Column("sqft", sa.Integer(), nullable=True),
        sa.Column("year_built", sa.Integer(), nullable=True),
        sa.Column("days_on_market", sa.Integer(), nullable=True),
        sa.Column("distance_miles", sa.Float(), nullable=True),
        sa.Column("adjustments_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["cma_report_id"], ["re_cma_reports.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_re_cma_comparables_org_id", "re_cma_comparables", ["org_id"], unique=False)
    op.create_index("ix_re_cma_comparables_created_at", "re_cma_comparables", ["created_at"], unique=False)

    op.create_table(
        "re_listing_packages",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=True),
        sa.Column("property_address_json", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "approved", "published", name="re_listing_package_status_enum"),
            nullable=False,
        ),
        sa.Column("description_variants_json", sa.JSON(), nullable=False),
        sa.Column("key_features_json", sa.JSON(), nullable=False),
        sa.Column("open_house_plan_json", sa.JSON(), nullable=False),
        sa.Column("social_campaign_pack_json", sa.JSON(), nullable=False),
        sa.Column("risk_tier", sa.Enum("TIER_0", "TIER_1", "TIER_2", "TIER_3", "TIER_4", name="risk_tier_enum"), nullable=False),
        sa.Column("policy_warnings_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["deal_id"], ["re_deals.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_re_listing_packages_org_id", "re_listing_packages", ["org_id"], unique=False)
    op.create_index("ix_re_listing_packages_created_at", "re_listing_packages", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_re_listing_packages_created_at", table_name="re_listing_packages")
    op.drop_index("ix_re_listing_packages_org_id", table_name="re_listing_packages")
    op.drop_table("re_listing_packages")

    op.drop_index("ix_re_cma_comparables_created_at", table_name="re_cma_comparables")
    op.drop_index("ix_re_cma_comparables_org_id", table_name="re_cma_comparables")
    op.drop_table("re_cma_comparables")

    op.drop_index("ix_re_cma_reports_created_at", table_name="re_cma_reports")
    op.drop_index("ix_re_cma_reports_org_id", table_name="re_cma_reports")
    op.drop_table("re_cma_reports")

    op.drop_index("ix_re_communication_logs_created_at", table_name="re_communication_logs")
    op.drop_index("ix_re_communication_logs_org_id", table_name="re_communication_logs")
    op.drop_table("re_communication_logs")

    op.drop_index("ix_re_document_requests_created_at", table_name="re_document_requests")
    op.drop_index("ix_re_document_requests_org_id", table_name="re_document_requests")
    op.drop_table("re_document_requests")

    op.drop_index("ix_re_checklist_items_created_at", table_name="re_checklist_items")
    op.drop_index("ix_re_checklist_items_org_id", table_name="re_checklist_items")
    op.drop_table("re_checklist_items")

    op.drop_index("ix_re_checklist_templates_created_at", table_name="re_checklist_templates")
    op.drop_index("ix_re_checklist_templates_org_id", table_name="re_checklist_templates")
    op.drop_table("re_checklist_templates")

    op.drop_index("ix_re_deals_created_at", table_name="re_deals")
    op.drop_index("ix_re_deals_org_id", table_name="re_deals")
    op.drop_table("re_deals")

    op.execute("DROP TYPE IF EXISTS re_listing_package_status_enum")
    op.execute("DROP TYPE IF EXISTS re_cma_comparable_status_enum")
    op.execute("DROP TYPE IF EXISTS re_communication_direction_enum")
    op.execute("DROP TYPE IF EXISTS re_communication_channel_enum")
    op.execute("DROP TYPE IF EXISTS re_document_request_status_enum")
    op.execute("DROP TYPE IF EXISTS re_checklist_item_status_enum")
    op.execute("DROP TYPE IF EXISTS re_checklist_template_deal_type_enum")
    op.execute("DROP TYPE IF EXISTS re_deal_status_enum")
    op.execute("DROP TYPE IF EXISTS re_deal_type_enum")
