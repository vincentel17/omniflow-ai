from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    AdAccount,
    AdAccountStatus,
    AdCampaign,
    AdCampaignStatus,
    AdCreative,
    AdCreativeStatus,
    AdExperiment,
    AdExperimentStatus,
    AdSpendLedger,
    Approval,
    ApprovalEntityType,
    ApprovalStatus,
    LinkTracking,
    Role,
)
from ..schemas import (
    AdAccountCreateRequest,
    AdAccountResponse,
    AdCampaignCreateRequest,
    AdCampaignPatchRequest,
    AdCampaignResponse,
    AdCreativeCreateRequest,
    AdCreativeResponse,
    AdExperimentCreateRequest,
    AdExperimentResponse,
    AdsSettingsPatchRequest,
    AdsSettingsResponse,
    AdSpendLedgerResponse,
)
from ..services.ads import (
    ads_settings_for_org,
    assert_budget_within_caps,
    can_activate_campaign,
    create_ads_approval,
    mark_campaign_pending_activation,
    patch_ads_settings_for_org,
)
from ..services.audit import write_audit_log
from ..services.billing import ensure_org_active
from ..services.events import write_event
from ..services.org_settings import get_org_settings_payload
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/ads", tags=["ads"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_account(row: AdAccount) -> AdAccountResponse:
    return AdAccountResponse(
        id=row.id,
        org_id=row.org_id,
        provider=row.provider,
        account_ref=row.account_ref,
        display_name=row.display_name,
        status=row.status,
        linked_connector_account_id=row.linked_connector_account_id,
        created_at=row.created_at,
    )


def _serialize_campaign(row: AdCampaign) -> AdCampaignResponse:
    return AdCampaignResponse(
        id=row.id,
        org_id=row.org_id,
        provider=row.provider,
        ad_account_id=row.ad_account_id,
        name=row.name,
        objective=row.objective,
        status=row.status,
        daily_budget_usd=row.daily_budget_usd,
        lifetime_budget_usd=row.lifetime_budget_usd,
        start_at=row.start_at,
        end_at=row.end_at,
        targeting_json=row.targeting_json,
        utm_json=row.utm_json,
        created_by=row.created_by,
        external_id=row.external_id,
        last_synced_at=row.last_synced_at,
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _serialize_creative(row: AdCreative) -> AdCreativeResponse:
    return AdCreativeResponse(
        id=row.id,
        org_id=row.org_id,
        campaign_id=row.campaign_id,
        name=row.name,
        format=row.format,
        primary_text=row.primary_text,
        headline=row.headline,
        description=row.description,
        media_ref=row.media_ref,
        destination_tracked_link_id=row.destination_tracked_link_id,
        status=row.status,
        external_id=row.external_id,
        created_at=row.created_at,
    )


def _serialize_experiment(row: AdExperiment) -> AdExperimentResponse:
    return AdExperimentResponse(
        id=row.id,
        org_id=row.org_id,
        campaign_id=row.campaign_id,
        name=row.name,
        hypothesis=row.hypothesis,
        status=row.status,
        variants_json=row.variants_json,
        start_at=row.start_at,
        end_at=row.end_at,
        success_metric=row.success_metric,
        created_at=row.created_at,
    )


def _serialize_ledger(row: AdSpendLedger) -> AdSpendLedgerResponse:
    return AdSpendLedgerResponse(
        id=row.id,
        org_id=row.org_id,
        provider=row.provider,
        campaign_id=row.campaign_id,
        day=row.day,
        spend_usd=row.spend_usd,
        impressions=row.impressions,
        clicks=row.clicks,
        source=row.source,
        created_at=row.created_at,
    )


def _get_campaign_or_404(db: Session, org_id: uuid.UUID, campaign_id: uuid.UUID) -> AdCampaign:
    row = db.scalar(
        org_scoped(
            select(AdCampaign).where(AdCampaign.id == campaign_id, AdCampaign.deleted_at.is_(None)),
            org_id,
            AdCampaign,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found")
    return row


def _tracked_link_valid_for_ads(link: LinkTracking) -> bool:
    utm = link.utm_json if isinstance(link.utm_json, dict) else {}
    has_campaign = any(utm.get(k) for k in ("campaign", "utm_campaign"))
    has_content = any(utm.get(k) for k in ("content", "content_id", "utm_content"))
    return has_campaign and has_content

def _to_ads_settings_response(payload: dict[str, object]) -> AdsSettingsResponse:
    providers_raw = payload.get("ads_provider_enabled_json")
    budgets_raw = payload.get("ads_budget_caps_json")
    providers = cast(dict[str, bool], providers_raw) if isinstance(providers_raw, dict) else {}
    budgets = cast(dict[str, float], budgets_raw) if isinstance(budgets_raw, dict) else {}
    return AdsSettingsResponse(
        enable_ads_automation=payload.get("enable_ads_automation") is True,
        enable_ads_live=payload.get("enable_ads_live") is True,
        ads_provider_enabled_json=providers,
        ads_budget_caps_json=budgets,
        ads_canary_mode=payload.get("ads_canary_mode") is True,
        require_approval_for_ads=payload.get("require_approval_for_ads") is True,
    )



@router.get("/settings", response_model=AdsSettingsResponse)
def get_ads_settings(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdsSettingsResponse:
    require_role(context, Role.ADMIN)
    payload = ads_settings_for_org(db=db, org_id=context.current_org_id)
    return _to_ads_settings_response(payload)


@router.patch("/settings", response_model=AdsSettingsResponse)
def patch_ads_settings(
    req: AdsSettingsPatchRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdsSettingsResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    payload = patch_ads_settings_for_org(db=db, org_id=context.current_org_id, patch=req.model_dump(exclude_none=True))
    write_audit_log(
        db=db,
        context=context,
        action="ads.settings.updated",
        target_type="org_settings",
        target_id=str(context.current_org_id),
        metadata_json={"keys": sorted(req.model_dump(exclude_none=True).keys())},
    )
    db.commit()
    return _to_ads_settings_response(payload)


@router.post("/accounts", response_model=AdAccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    req: AdAccountCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdAccountResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    row = AdAccount(
        org_id=context.current_org_id,
        provider=req.provider,
        account_ref=req.account_ref,
        display_name=req.display_name,
        status=AdAccountStatus.ACTIVE,
        linked_connector_account_id=req.linked_connector_account_id,
    )
    db.add(row)
    db.flush()
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="ads",
        channel="ads",
        event_type="ADS_ACCOUNT_REGISTERED",
        payload_json={"ad_account_id": str(row.id), "provider": row.provider.value},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(row)
    return _serialize_account(row)


@router.get("/accounts", response_model=list[AdAccountResponse])
def list_accounts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[AdAccountResponse]:
    require_role(context, Role.ADMIN)
    rows = db.scalars(
        org_scoped(
            select(AdAccount)
            .where(AdAccount.deleted_at.is_(None))
            .order_by(desc(AdAccount.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            AdAccount,
        )
    ).all()
    return [_serialize_account(row) for row in rows]


@router.post("/campaigns", response_model=AdCampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    req: AdCampaignCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdCampaignResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    ad_account = db.scalar(
        org_scoped(
            select(AdAccount).where(AdAccount.id == req.ad_account_id, AdAccount.deleted_at.is_(None)),
            context.current_org_id,
            AdAccount,
        )
    )
    if ad_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ad account not found")
    assert_budget_within_caps(db=db, org_id=context.current_org_id, daily_budget_usd=req.daily_budget_usd)
    row = AdCampaign(
        org_id=context.current_org_id,
        provider=req.provider,
        ad_account_id=req.ad_account_id,
        name=req.name,
        objective=req.objective,
        status=AdCampaignStatus.DRAFT,
        daily_budget_usd=req.daily_budget_usd,
        lifetime_budget_usd=req.lifetime_budget_usd,
        start_at=req.start_at,
        end_at=req.end_at,
        targeting_json=req.targeting_json,
        utm_json=req.utm_json,
        created_by=context.current_user_id,
    )
    db.add(row)
    db.flush()
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="ads",
        channel="ads",
        event_type="ADS_CAMPAIGN_CREATED",
        payload_json={"campaign_id": str(row.id), "provider": row.provider.value},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(row)
    return _serialize_campaign(row)


@router.get("/campaigns", response_model=list[AdCampaignResponse])
def list_campaigns(
    status_filter: AdCampaignStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[AdCampaignResponse]:
    require_role(context, Role.ADMIN)
    stmt = org_scoped(
        select(AdCampaign)
        .where(AdCampaign.deleted_at.is_(None))
        .order_by(desc(AdCampaign.created_at))
        .limit(limit)
        .offset(offset),
        context.current_org_id,
        AdCampaign,
    )
    if status_filter is not None:
        stmt = stmt.where(AdCampaign.status == status_filter)
    rows = db.scalars(stmt).all()
    return [_serialize_campaign(row) for row in rows]


@router.get("/campaigns/{campaign_id}", response_model=AdCampaignResponse)
def get_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdCampaignResponse:
    require_role(context, Role.ADMIN)
    return _serialize_campaign(_get_campaign_or_404(db, context.current_org_id, campaign_id))


@router.patch("/campaigns/{campaign_id}", response_model=AdCampaignResponse)
def update_campaign(
    campaign_id: uuid.UUID,
    req: AdCampaignPatchRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdCampaignResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    row = _get_campaign_or_404(db, context.current_org_id, campaign_id)
    patch = req.model_dump(exclude_none=True)
    settings_payload = get_org_settings_payload(db=db, org_id=context.current_org_id)

    if "daily_budget_usd" in patch and patch["daily_budget_usd"] != row.daily_budget_usd:
        assert_budget_within_caps(db=db, org_id=context.current_org_id, daily_budget_usd=float(patch["daily_budget_usd"]))
        if settings_payload.get("require_approval_for_ads") is True:
            create_ads_approval(
                db=db,
                org_id=context.current_org_id,
                requested_by=context.current_user_id,
                entity_type=ApprovalEntityType.AD_SPEND_CHANGE,
                entity_id=row.id,
                notes="Budget change approval required",
            )
            db.commit()
            db.refresh(row)
            return _serialize_campaign(row)
        row.daily_budget_usd = float(patch["daily_budget_usd"])

    for field in ("name", "lifetime_budget_usd", "start_at", "end_at", "targeting_json", "utm_json"):
        if field in patch:
            setattr(row, field, patch[field])

    write_event(
        db=db,
        org_id=context.current_org_id,
        source="ads",
        channel="ads",
        event_type="ADS_CAMPAIGN_UPDATED",
        payload_json={"campaign_id": str(row.id)},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(row)
    return _serialize_campaign(row)


@router.post("/campaigns/{campaign_id}/request-activation", response_model=AdCampaignResponse)
def request_activation(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdCampaignResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    row = _get_campaign_or_404(db, context.current_org_id, campaign_id)
    create_ads_approval(
        db=db,
        org_id=context.current_org_id,
        requested_by=context.current_user_id,
        entity_type=ApprovalEntityType.AD_CAMPAIGN,
        entity_id=row.id,
        notes="Campaign activation requested",
    )
    mark_campaign_pending_activation(row)
    db.commit()
    db.refresh(row)
    return _serialize_campaign(row)


@router.post("/campaigns/{campaign_id}/activate", response_model=AdCampaignResponse)
def activate_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdCampaignResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    row = _get_campaign_or_404(db, context.current_org_id, campaign_id)
    settings_payload = get_org_settings_payload(db=db, org_id=context.current_org_id)
    if settings_payload.get("require_approval_for_ads") is True:
        approved = db.scalar(
            org_scoped(
                select(Approval).where(
                    Approval.entity_type == ApprovalEntityType.AD_CAMPAIGN,
                    Approval.entity_id == row.id,
                    Approval.status == ApprovalStatus.APPROVED,
                    Approval.deleted_at.is_(None),
                ),
                context.current_org_id,
                Approval,
            )
        )
        if approved is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ADS_APPROVAL_REQUIRED")
    if not can_activate_campaign(db=db, org_id=context.current_org_id, campaign_id=row.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ADS_APPROVAL_PENDING")

    row.status = AdCampaignStatus.ACTIVE
    row.external_id = row.external_id or f"mock-campaign-{row.id}"
    row.last_synced_at = _utcnow()
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="ads",
        channel="ads",
        event_type="ADS_CAMPAIGN_ACTIVATED",
        payload_json={"campaign_id": str(row.id)},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(row)
    return _serialize_campaign(row)


@router.post("/campaigns/{campaign_id}/pause", response_model=AdCampaignResponse)
def pause_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdCampaignResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    row = _get_campaign_or_404(db, context.current_org_id, campaign_id)
    row.status = AdCampaignStatus.PAUSED
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="ads",
        channel="ads",
        event_type="ADS_CAMPAIGN_PAUSED",
        payload_json={"campaign_id": str(row.id)},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(row)
    return _serialize_campaign(row)


@router.post("/campaigns/{campaign_id}/creatives", response_model=AdCreativeResponse, status_code=status.HTTP_201_CREATED)
def create_creative(
    campaign_id: uuid.UUID,
    req: AdCreativeCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdCreativeResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    _get_campaign_or_404(db, context.current_org_id, campaign_id)
    tracked = db.scalar(
        org_scoped(
            select(LinkTracking).where(LinkTracking.id == req.destination_tracked_link_id, LinkTracking.deleted_at.is_(None)),
            context.current_org_id,
            LinkTracking,
        )
    )
    if tracked is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tracked link not found")
    if not _tracked_link_valid_for_ads(tracked):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="TRACKED_LINK_UTM_INVALID")

    row = AdCreative(
        org_id=context.current_org_id,
        campaign_id=campaign_id,
        name=req.name,
        format=req.format,
        primary_text=req.primary_text,
        headline=req.headline,
        description=req.description,
        media_ref=req.media_ref,
        destination_tracked_link_id=req.destination_tracked_link_id,
        status=AdCreativeStatus.DRAFT,
    )
    db.add(row)
    db.flush()
    create_ads_approval(
        db=db,
        org_id=context.current_org_id,
        requested_by=context.current_user_id,
        entity_type=ApprovalEntityType.AD_CREATIVE,
        entity_id=row.id,
        notes="Creative approval required",
    )
    db.commit()
    db.refresh(row)
    return _serialize_creative(row)


@router.get("/creatives", response_model=list[AdCreativeResponse])
def list_creatives(
    status_filter: AdCreativeStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[AdCreativeResponse]:
    require_role(context, Role.ADMIN)
    stmt = org_scoped(
        select(AdCreative)
        .where(AdCreative.deleted_at.is_(None))
        .order_by(desc(AdCreative.created_at))
        .limit(limit)
        .offset(offset),
        context.current_org_id,
        AdCreative,
    )
    if status_filter is not None:
        stmt = stmt.where(AdCreative.status == status_filter)
    rows = db.scalars(stmt).all()
    return [_serialize_creative(row) for row in rows]


@router.post("/creatives/{creative_id}/approve", response_model=AdCreativeResponse)
def approve_creative(
    creative_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdCreativeResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    row = db.scalar(
        org_scoped(
            select(AdCreative).where(AdCreative.id == creative_id, AdCreative.deleted_at.is_(None)),
            context.current_org_id,
            AdCreative,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="creative not found")
    row.status = AdCreativeStatus.APPROVED
    db.commit()
    db.refresh(row)
    return _serialize_creative(row)


@router.post("/campaigns/{campaign_id}/experiments", response_model=AdExperimentResponse, status_code=status.HTTP_201_CREATED)
def create_experiment(
    campaign_id: uuid.UUID,
    req: AdExperimentCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdExperimentResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    _get_campaign_or_404(db, context.current_org_id, campaign_id)
    row = AdExperiment(
        org_id=context.current_org_id,
        campaign_id=campaign_id,
        name=req.name,
        hypothesis=req.hypothesis,
        status=AdExperimentStatus.DRAFT,
        variants_json=req.variants_json,
        start_at=req.start_at,
        end_at=req.end_at,
        success_metric=req.success_metric,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_experiment(row)


@router.post("/experiments/{experiment_id}/start", response_model=AdExperimentResponse)
def start_experiment(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdExperimentResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    row = db.scalar(
        org_scoped(
            select(AdExperiment).where(AdExperiment.id == experiment_id, AdExperiment.deleted_at.is_(None)),
            context.current_org_id,
            AdExperiment,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="experiment not found")
    settings_payload = get_org_settings_payload(db=db, org_id=context.current_org_id)
    campaign = _get_campaign_or_404(db, context.current_org_id, row.campaign_id)
    if settings_payload.get("ads_canary_mode") is True and campaign.daily_budget_usd > 5:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ADS_CANARY_BUDGET_LIMIT")
    create_ads_approval(
        db=db,
        org_id=context.current_org_id,
        requested_by=context.current_user_id,
        entity_type=ApprovalEntityType.AD_EXPERIMENT,
        entity_id=row.id,
        notes="Experiment start approval required",
    )
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ADS_APPROVAL_REQUIRED")


@router.post("/experiments/{experiment_id}/stop", response_model=AdExperimentResponse)
def stop_experiment(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdExperimentResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    row = db.scalar(
        org_scoped(
            select(AdExperiment).where(AdExperiment.id == experiment_id, AdExperiment.deleted_at.is_(None)),
            context.current_org_id,
            AdExperiment,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="experiment not found")
    row.status = AdExperimentStatus.COMPLETED
    db.commit()
    db.refresh(row)
    return _serialize_experiment(row)


@router.get("/experiments", response_model=list[AdExperimentResponse])
def list_experiments(
    status_filter: AdExperimentStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[AdExperimentResponse]:
    require_role(context, Role.ADMIN)
    stmt = org_scoped(
        select(AdExperiment)
        .where(AdExperiment.deleted_at.is_(None))
        .order_by(desc(AdExperiment.created_at))
        .limit(limit)
        .offset(offset),
        context.current_org_id,
        AdExperiment,
    )
    if status_filter is not None:
        stmt = stmt.where(AdExperiment.status == status_filter)
    rows = db.scalars(stmt).all()
    return [_serialize_experiment(row) for row in rows]


@router.post("/metrics/sync")
def sync_metrics(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    campaigns = db.scalars(
        org_scoped(
            select(AdCampaign).where(AdCampaign.status == AdCampaignStatus.ACTIVE, AdCampaign.deleted_at.is_(None)),
            context.current_org_id,
            AdCampaign,
        )
    ).all()
    created = 0
    today = date.today()
    for campaign in campaigns:
        spend = round(max(0.5, campaign.daily_budget_usd * 0.35), 2)
        row = AdSpendLedger(
            org_id=context.current_org_id,
            provider=campaign.provider,
            campaign_id=campaign.id,
            day=today,
            spend_usd=spend,
            impressions=max(100, int(spend * 120)),
            clicks=max(1, int(spend * 6)),
            source="mock",
        )
        db.add(row)
        created += 1

    write_event(
        db=db,
        org_id=context.current_org_id,
        source="ads",
        channel="ads",
        event_type="ADS_METRICS_SYNCED",
        payload_json={"rows_created": created},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    return {"rows_created": created}


@router.get("/metrics", response_model=list[AdSpendLedgerResponse])
def list_metrics(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[AdSpendLedgerResponse]:
    require_role(context, Role.ADMIN)
    rows = db.scalars(
        org_scoped(
            select(AdSpendLedger)
            .where(
                AdSpendLedger.deleted_at.is_(None),
                AdSpendLedger.day >= from_date,
                AdSpendLedger.day <= to_date,
            )
            .order_by(desc(AdSpendLedger.day), desc(AdSpendLedger.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            AdSpendLedger,
        )
    ).all()
    return [_serialize_ledger(row) for row in rows]





