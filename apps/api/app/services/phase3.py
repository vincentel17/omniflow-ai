from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import BrandProfile, RiskTier, VerticalPack


def get_vertical_pack_slug(db: Session, org_id: uuid.UUID, preferred_slug: str | None = None) -> str:
    if preferred_slug:
        return preferred_slug
    current = db.scalar(
        select(VerticalPack).where(VerticalPack.org_id == org_id, VerticalPack.deleted_at.is_(None))
    )
    if current is None:
        return "generic"
    return current.pack_slug


def get_brand_profile(db: Session, org_id: uuid.UUID) -> BrandProfile | None:
    return db.scalar(select(BrandProfile).where(BrandProfile.org_id == org_id, BrandProfile.deleted_at.is_(None)))


def tier_to_number(tier: RiskTier) -> int:
    return int(str(tier.value).split("_")[1])


def should_auto_approve(risk_tier: RiskTier, auto_approve_tiers_max: int) -> bool:
    return tier_to_number(risk_tier) <= auto_approve_tiers_max


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)
