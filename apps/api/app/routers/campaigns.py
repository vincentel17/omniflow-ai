from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from packages.schemas import CampaignPlanJSON

from ..db import get_db
from ..models import (
    Approval,
    ApprovalEntityType,
    ApprovalStatus,
    CampaignPlan,
    CampaignPlanStatus,
    ContentItem,
    ContentItemStatus,
    RiskTier,
    Role,
)
from ..schemas import (
    ApprovalDecisionRequest,
    CampaignPlanCreateRequest,
    CampaignPlanGenerateContentResponse,
    CampaignPlanResponse,
)
from ..services.ai import generate_campaign_plan, generate_content_items
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..services.org_settings import ai_mode_for_org
from ..services.phase3 import get_brand_profile, get_vertical_pack_slug, should_auto_approve, utcnow
from ..services.policy import load_policy_engine
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _serialize_campaign(plan: CampaignPlan) -> CampaignPlanResponse:
    return CampaignPlanResponse(
        id=plan.id,
        org_id=plan.org_id,
        vertical_pack_slug=plan.vertical_pack_slug,
        week_start_date=plan.week_start_date,
        status=plan.status,
        created_by=plan.created_by,
        approved_by=plan.approved_by,
        approved_at=plan.approved_at,
        plan_json=plan.plan_json,
        metadata_json=plan.metadata_json,
        created_at=plan.created_at,
    )


@router.post("/plan", response_model=CampaignPlanResponse, status_code=status.HTTP_201_CREATED)
def create_campaign_plan(
    payload: CampaignPlanCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> CampaignPlanResponse:
    require_role(context, Role.AGENT)
    org_ai_mode = ai_mode_for_org(db=db, org_id=context.current_org_id)
    if org_ai_mode == "live" and context.current_role not in (Role.ADMIN, Role.OWNER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="live AI mode requires admin or owner role")
    pack_slug = get_vertical_pack_slug(db=db, org_id=context.current_org_id, preferred_slug=payload.vertical_pack_slug)
    plan_json = generate_campaign_plan(
        week_start_date=payload.week_start_date,
        channels=payload.channels,
        objectives=payload.objectives,
    )

    campaign = CampaignPlan(
        org_id=context.current_org_id,
        vertical_pack_slug=pack_slug,
        week_start_date=payload.week_start_date,
        status=CampaignPlanStatus.DRAFT,
        created_by=context.current_user_id,
        plan_json=plan_json.model_dump(mode="json"),
        metadata_json={},
    )
    db.add(campaign)
    db.flush()

    write_audit_log(
        db=db,
        context=context,
        action="ai.generate_plan",
        target_type="campaign_plan",
        target_id=str(campaign.id),
        metadata_json={"week_start_date": str(payload.week_start_date), "channels": payload.channels},
        risk_tier=RiskTier.TIER_1,
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="ai",
        channel="campaigns",
        event_type="AI_GENERATE_PLAN",
        campaign_id=str(campaign.id),
        payload_json={"pack_slug": pack_slug},
        actor_id=str(context.current_user_id),
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="campaigns",
        channel="campaigns",
        event_type="CAMPAIGN_PLAN_CREATED",
        campaign_id=str(campaign.id),
        payload_json={"pack_slug": pack_slug},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(campaign)


@router.post("/{campaign_id}/approve", response_model=CampaignPlanResponse)
def approve_campaign(
    campaign_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> CampaignPlanResponse:
    require_role(context, Role.ADMIN)
    if payload.status not in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid approval status")
    campaign = db.scalar(
        org_scoped(
            select(CampaignPlan).where(CampaignPlan.id == campaign_id, CampaignPlan.deleted_at.is_(None)),
            context.current_org_id,
            CampaignPlan,
        )
    )
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found")

    approval = Approval(
        org_id=context.current_org_id,
        entity_type=ApprovalEntityType.CAMPAIGN_PLAN,
        entity_id=campaign.id,
        status=payload.status,
        requested_by=campaign.created_by,
        decided_by=context.current_user_id,
        decided_at=utcnow(),
        notes=payload.notes,
    )
    db.add(approval)
    campaign.status = CampaignPlanStatus.APPROVED if payload.status == ApprovalStatus.APPROVED else CampaignPlanStatus.DRAFT
    campaign.approved_by = context.current_user_id if payload.status == ApprovalStatus.APPROVED else None
    campaign.approved_at = utcnow() if payload.status == ApprovalStatus.APPROVED else None
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="campaign.approval_decided",
        target_type="campaign_plan",
        target_id=str(campaign.id),
        metadata_json={"status": payload.status.value},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="approval",
        channel="campaigns",
        event_type="CAMPAIGN_APPROVAL_DECIDED",
        campaign_id=str(campaign.id),
        payload_json={"status": payload.status.value},
        actor_id=str(context.current_user_id),
    )
    if payload.status == ApprovalStatus.APPROVED:
        write_event(
            db=db,
            org_id=context.current_org_id,
            source="approval",
            channel="campaigns",
            event_type="CAMPAIGN_PLAN_APPROVED",
            campaign_id=str(campaign.id),
            payload_json={"status": payload.status.value},
            actor_id=str(context.current_user_id),
        )
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(campaign)


@router.post("/{campaign_id}/generate-content", response_model=CampaignPlanGenerateContentResponse)
def generate_campaign_content(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> CampaignPlanGenerateContentResponse:
    require_role(context, Role.AGENT)
    org_ai_mode = ai_mode_for_org(db=db, org_id=context.current_org_id)
    if org_ai_mode == "live" and context.current_role not in (Role.ADMIN, Role.OWNER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="live AI mode requires admin or owner role")
    campaign = db.scalar(
        org_scoped(
            select(CampaignPlan).where(CampaignPlan.id == campaign_id, CampaignPlan.deleted_at.is_(None)),
            context.current_org_id,
            CampaignPlan,
        )
    )
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found")

    typed_plan = CampaignPlanJSON.model_validate(campaign.plan_json)
    content_rows = generate_content_items(typed_plan)
    policy_engine = load_policy_engine(campaign.vertical_pack_slug)
    brand_profile = get_brand_profile(db=db, org_id=context.current_org_id)
    auto_approve_tiers_max = brand_profile.auto_approve_tiers_max if brand_profile else 1

    created_count = 0
    for item in content_rows:
        validation = policy_engine.validate_content(item.caption, context={"channel": item.channel})
        risk_tier = RiskTier(policy_engine.risk_tier("publish_content", context={"channel": item.channel}).value)
        row_status = (
            ContentItemStatus.APPROVED
            if should_auto_approve(risk_tier=risk_tier, auto_approve_tiers_max=auto_approve_tiers_max)
            else ContentItemStatus.PENDING_APPROVAL
        )
        row = ContentItem(
            org_id=context.current_org_id,
            campaign_plan_id=campaign.id,
            channel=item.channel,
            account_ref="default",
            status=row_status,
            content_json=item.model_dump(mode="json"),
            text_rendered=item.caption,
            media_refs_json=[],
            link_url=str(item.link_url) if item.link_url else None,
            tags_json=item.hashtags,
            risk_tier=risk_tier,
            policy_warnings_json=validation.reasons,
        )
        db.add(row)
        db.flush()
        write_event(
            db=db,
            org_id=context.current_org_id,
            source="ai",
            channel=row.channel,
            event_type="AI_GENERATE_CONTENT",
            campaign_id=str(campaign.id),
            content_id=str(row.id),
            payload_json={"risk_tier": row.risk_tier.value, "warnings": row.policy_warnings_json},
            actor_id=str(context.current_user_id),
        )
        write_event(
            db=db,
            org_id=context.current_org_id,
            source="content",
            channel=row.channel,
            event_type="CONTENT_CREATED",
            campaign_id=str(campaign.id),
            content_id=str(row.id),
            payload_json={"status": row.status.value, "risk_tier": row.risk_tier.value},
            actor_id=str(context.current_user_id),
        )
        write_audit_log(
            db=db,
            context=context,
            action="ai.generate_content",
            target_type="content_item",
            target_id=str(row.id),
            metadata_json={"campaign_id": str(campaign.id), "risk_tier": row.risk_tier.value},
            risk_tier=row.risk_tier,
        )
        created_count += 1

    db.commit()
    return CampaignPlanGenerateContentResponse(items_created=created_count)


@router.get("", response_model=list[CampaignPlanResponse])
def list_campaigns(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[CampaignPlanResponse]:
    rows = db.scalars(
        org_scoped(
            select(CampaignPlan)
            .where(CampaignPlan.deleted_at.is_(None))
            .order_by(desc(CampaignPlan.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            CampaignPlan,
        )
    ).all()
    return [_serialize_campaign(row) for row in rows]


@router.get("/{campaign_id}", response_model=CampaignPlanResponse)
def get_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> CampaignPlanResponse:
    campaign = db.scalar(
        org_scoped(
            select(CampaignPlan).where(CampaignPlan.id == campaign_id, CampaignPlan.deleted_at.is_(None)),
            context.current_org_id,
            CampaignPlan,
        )
    )
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found")
    return _serialize_campaign(campaign)
