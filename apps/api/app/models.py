from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy import JSON as JsonType
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    AGENT = "agent"


class RiskTier(str, enum.Enum):
    TIER_0 = "TIER_0"
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"
    TIER_4 = "TIER_4"


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Org(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "orgs"
    __table_args__ = (UniqueConstraint("name", name="uq_orgs_name"), Index("ix_orgs_created_at", "created_at"))

    name: Mapped[str] = mapped_column(String(255), nullable=False)


class User(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("external_auth_id", name="uq_users_external_auth_id"),
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_created_at", "created_at"),
    )

    external_auth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Membership(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_memberships_org_user"),
        Index("ix_memberships_org_id", "org_id"),
        Index("ix_memberships_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="role_enum"), nullable=False)


class Integration(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "provider", "external_account_id", name="uq_integrations_org_provider_external"
        ),
        Index("ix_integrations_org_id", "org_id"),
        Index("ix_integrations_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="registered")
    config_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class VerticalPack(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "vertical_packs"
    __table_args__ = (
        UniqueConstraint("org_id", name="uq_vertical_packs_org_id"),
        Index("ix_vertical_packs_org_id", "org_id"),
        Index("ix_vertical_packs_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    pack_slug: Mapped[str] = mapped_column(String(100), nullable=False)


class Event(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_org_id", "org_id"),
        Index("ix_events_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lead_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)


class AuditLog(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_org_id", "org_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    risk_tier: Mapped[RiskTier] = mapped_column(
        Enum(RiskTier, name="risk_tier_enum"), nullable=False, default=RiskTier.TIER_1
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False, default=dict)
