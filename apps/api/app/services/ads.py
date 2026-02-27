from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AdCampaign, AdCampaignStatus, AdSpendLedger, Approval, ApprovalEntityType, ApprovalStatus
from .org_settings import ads_budget_caps_for_org, get_org_settings_payload, update_org_settings_payload


def ads_settings_for_org(db: Session, org_id: uuid.UUID) -> dict[str, object]:
    payload = get_org_settings_payload(db=db, org_id=org_id)
    return {
        "enable_ads_automation": payload.get("enable_ads_automation") is True,
        "enable_ads_live": payload.get("enable_ads_live") is True,
        "ads_provider_enabled_json": payload.get("ads_provider_enabled_json") if isinstance(payload.get("ads_provider_enabled_json"), dict) else {},
        "ads_budget_caps_json": payload.get("ads_budget_caps_json") if isinstance(payload.get("ads_budget_caps_json"), dict) else {},
        "ads_canary_mode": payload.get("ads_canary_mode") is True,
        "require_approval_for_ads": payload.get("require_approval_for_ads") is True,
    }


def patch_ads_settings_for_org(db: Session, org_id: uuid.UUID, patch: dict[str, object]) -> dict[str, object]:
    return update_org_settings_payload(db=db, org_id=org_id, patch=patch)


def assert_budget_within_caps(db: Session, org_id: uuid.UUID, daily_budget_usd: float) -> None:
    caps = ads_budget_caps_for_org(db=db, org_id=org_id)
    if daily_budget_usd > float(caps.get("per_campaign_cap_usd", 50.0)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="BUDGET_CAP_EXCEEDED:per_campaign_cap_usd")

    today = date.today()
    month_start = today.replace(day=1)
    day_spend = float(
        db.scalar(
            select(func.coalesce(func.sum(AdSpendLedger.spend_usd), 0.0)).where(
                AdSpendLedger.org_id == org_id,
                AdSpendLedger.day == today,
                AdSpendLedger.deleted_at.is_(None),
            )
        )
        or 0.0
    )
    month_spend = float(
        db.scalar(
            select(func.coalesce(func.sum(AdSpendLedger.spend_usd), 0.0)).where(
                AdSpendLedger.org_id == org_id,
                AdSpendLedger.day >= month_start,
                AdSpendLedger.deleted_at.is_(None),
            )
        )
        or 0.0
    )
    if day_spend + daily_budget_usd > float(caps.get("org_daily_cap_usd", 10.0)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="BUDGET_CAP_EXCEEDED:org_daily_cap_usd")
    if month_spend + daily_budget_usd > float(caps.get("org_monthly_cap_usd", 200.0)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="BUDGET_CAP_EXCEEDED:org_monthly_cap_usd")


def ensure_ads_live_gate(db: Session, org_id: uuid.UUID, provider: str) -> None:
    payload = get_org_settings_payload(db=db, org_id=org_id)
    if payload.get("enable_ads_automation") is not True or payload.get("enable_ads_live") is not True:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ADS_LIVE_BLOCKED")
    enabled = payload.get("ads_provider_enabled_json")
    if not isinstance(enabled, dict) or enabled.get(f"{provider}_ads_enabled") is not True:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ADS_LIVE_BLOCKED")


def create_ads_approval(
    db: Session,
    *,
    org_id: uuid.UUID,
    requested_by: uuid.UUID,
    entity_type: ApprovalEntityType,
    entity_id: uuid.UUID,
    notes: str,
) -> Approval:
    approval = Approval(
        org_id=org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        status=ApprovalStatus.PENDING,
        requested_by=requested_by,
        notes=notes,
    )
    db.add(approval)
    db.flush()
    return approval


def can_activate_campaign(db: Session, org_id: uuid.UUID, campaign_id: uuid.UUID) -> bool:
    pending = db.scalar(
        select(Approval).where(
            Approval.org_id == org_id,
            Approval.entity_type == ApprovalEntityType.AD_CAMPAIGN,
            Approval.entity_id == campaign_id,
            Approval.status == ApprovalStatus.PENDING,
            Approval.deleted_at.is_(None),
        )
    )
    return pending is None


def mark_campaign_pending_activation(campaign: AdCampaign) -> None:
    campaign.status = AdCampaignStatus.PENDING_ACTIVATION
