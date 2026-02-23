from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import BrandProfile, Role
from ..schemas import BrandProfilePayload, BrandProfileResponse
from ..services.audit import write_audit_log
from ..tenancy import RequestContext, get_request_context, require_role

router = APIRouter(prefix="/brand/profile", tags=["brand"])


@router.get("", response_model=BrandProfileResponse)
def get_brand_profile(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> BrandProfileResponse:
    profile = db.scalar(
        select(BrandProfile).where(BrandProfile.org_id == context.current_org_id, BrandProfile.deleted_at.is_(None))
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="brand profile not found")
    return BrandProfileResponse.from_model(profile)


@router.post("", response_model=BrandProfileResponse)
def upsert_brand_profile(
    payload: BrandProfilePayload,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> BrandProfileResponse:
    require_role(context, Role.ADMIN)
    profile = db.scalar(
        select(BrandProfile).where(BrandProfile.org_id == context.current_org_id, BrandProfile.deleted_at.is_(None))
    )
    if profile is None:
        profile = BrandProfile(org_id=context.current_org_id)
        db.add(profile)
    profile.brand_voice_json = payload.brand_voice_json
    profile.brand_assets_json = payload.brand_assets_json
    profile.locations_json = payload.locations_json
    profile.auto_approve_tiers_max = payload.auto_approve_tiers_max
    profile.require_approval_for_publish = payload.require_approval_for_publish
    db.flush()

    write_audit_log(
        db=db,
        context=context,
        action="brand.profile_upserted",
        target_type="brand_profile",
        target_id=str(profile.id),
        metadata_json={
            "auto_approve_tiers_max": profile.auto_approve_tiers_max,
            "require_approval_for_publish": profile.require_approval_for_publish,
        },
    )
    db.commit()
    db.refresh(profile)
    return BrandProfileResponse.from_model(profile)
