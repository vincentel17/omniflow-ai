from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    PresenceTask,
    PresenceTaskStatus,
    PresenceTaskType,
    ReputationRequestCampaign,
    ReputationRequestCampaignStatus,
    ReputationReview,
    RiskTier,
    VerticalPack,
)
from ..schemas import (
    ReputationCampaignCreateRequest,
    ReputationCampaignResponse,
    ReputationDraftResponse,
    ReputationReviewImportRequest,
    ReputationReviewResponse,
)
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..services.phase5 import (
    build_review_response_draft,
    create_reputation_campaign_tasks,
    hash_review_text,
    mask_reviewer_name,
    score_review_sentiment,
)
from ..services.policy import load_policy_engine
from ..tenancy import RequestContext, get_request_context, org_scoped

router = APIRouter(prefix="/reputation", tags=["reputation"])


def _pack_slug(db: Session, org_id: uuid.UUID) -> str:
    row = db.scalar(
        org_scoped(select(VerticalPack).where(VerticalPack.deleted_at.is_(None)), org_id, VerticalPack)
    )
    return "generic" if row is None else row.pack_slug


def _serialize_review(row: ReputationReview) -> ReputationReviewResponse:
    return ReputationReviewResponse(
        id=row.id,
        org_id=row.org_id,
        source=row.source,
        external_id=row.external_id,
        reviewer_name_masked=row.reviewer_name_masked,
        rating=row.rating,
        review_text=row.review_text,
        review_text_hash=row.review_text_hash,
        sentiment_json=row.sentiment_json,
        responded_at=row.responded_at,
        created_at=row.created_at,
    )


def _serialize_campaign(row: ReputationRequestCampaign) -> ReputationCampaignResponse:
    return ReputationCampaignResponse(
        id=row.id,
        org_id=row.org_id,
        name=row.name,
        status=row.status,
        audience=row.audience,
        template_key=row.template_key,
        channel=row.channel,
        created_at=row.created_at,
    )


@router.post("/reviews/import", response_model=list[ReputationReviewResponse], status_code=status.HTTP_201_CREATED)
def import_reviews(
    payload: ReputationReviewImportRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[ReputationReviewResponse]:
    created: list[ReputationReview] = []
    for item in payload.reviews:
        sentiment = score_review_sentiment(review_text=item.review_text, rating=item.rating)
        review = ReputationReview(
            org_id=context.current_org_id,
            source=item.source,
            external_id=item.external_id,
            reviewer_name_masked=mask_reviewer_name(item.reviewer_name),
            rating=item.rating,
            review_text=item.review_text,
            review_text_hash=hash_review_text(item.review_text),
            sentiment_json=sentiment.model_dump(mode="json"),
            responded_at=None,
        )
        db.add(review)
        db.flush()
        created.append(review)

        write_event(
            db=db,
            org_id=context.current_org_id,
            source="reputation",
            channel="review",
            event_type="REVIEW_IMPORTED",
            payload_json={"review_id": str(review.id), "rating": review.rating},
            actor_id=str(context.current_user_id),
        )
        write_event(
            db=db,
            org_id=context.current_org_id,
            source="reputation",
            channel="review",
            event_type="REVIEW_SENTIMENT_SCORED",
            payload_json={"review_id": str(review.id), "urgency": sentiment.urgency},
            actor_id=str(context.current_user_id),
        )

        if sentiment.urgency == "high":
            task = PresenceTask(
                org_id=context.current_org_id,
                finding_id=None,
                type=PresenceTaskType.RESPOND_REVIEW,
                assigned_to_user_id=None,
                due_at=datetime.now(UTC) + timedelta(hours=4),
                status=PresenceTaskStatus.OPEN,
                payload_json={"review_id": str(review.id), "urgency": "high"},
            )
            db.add(task)

    write_audit_log(
        db=db,
        context=context,
        action="reputation.reviews_imported",
        target_type="reputation_review",
        target_id=f"count:{len(created)}",
        metadata_json={"count": len(created)},
        risk_tier=RiskTier.TIER_1,
    )
    db.commit()
    return [_serialize_review(row) for row in created]


@router.get("/reviews", response_model=list[ReputationReviewResponse])
def list_reviews(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[ReputationReviewResponse]:
    rows = db.scalars(
        org_scoped(
            select(ReputationReview)
            .where(ReputationReview.deleted_at.is_(None))
            .order_by(desc(ReputationReview.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            ReputationReview,
        )
    ).all()
    return [_serialize_review(row) for row in rows]


@router.post("/reviews/{review_id}/draft-response", response_model=ReputationDraftResponse)
def draft_review_response(
    review_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ReputationDraftResponse:
    review = db.scalar(
        org_scoped(
            select(ReputationReview).where(ReputationReview.id == review_id, ReputationReview.deleted_at.is_(None)),
            context.current_org_id,
            ReputationReview,
        )
    )
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review not found")
    policy = load_policy_engine(_pack_slug(db, context.current_org_id))
    draft = build_review_response_draft(review=review, policy=policy)
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="reputation",
        channel="review",
        event_type="REVIEW_RESPONSE_DRAFTED",
        payload_json={"review_id": str(review.id), "risk_tier": draft.risk_tier},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="reputation.review_response_drafted",
        target_type="reputation_review",
        target_id=str(review.id),
        metadata_json={"risk_tier": draft.risk_tier},
        risk_tier=RiskTier(draft.risk_tier),
    )
    db.commit()
    return ReputationDraftResponse(
        response_text=draft.response_text,
        tone=draft.tone,
        disclaimers=draft.disclaimers,
        risk_tier=RiskTier(draft.risk_tier),
        policy_warnings=draft.policy_warnings,
    )


@router.post("/campaigns", response_model=ReputationCampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: ReputationCampaignCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ReputationCampaignResponse:
    row = ReputationRequestCampaign(
        org_id=context.current_org_id,
        name=payload.name,
        status=ReputationRequestCampaignStatus.DRAFT,
        audience=payload.audience,
        template_key=payload.template_key,
        channel=payload.channel,
    )
    db.add(row)
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="reputation.campaign_created",
        target_type="reputation_campaign",
        target_id=str(row.id),
        metadata_json={"audience": row.audience.value, "channel": row.channel.value},
        risk_tier=RiskTier.TIER_1,
    )
    db.commit()
    db.refresh(row)
    return _serialize_campaign(row)


@router.post("/campaigns/{campaign_id}/start", response_model=ReputationCampaignResponse)
def start_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ReputationCampaignResponse:
    row = db.scalar(
        org_scoped(
            select(ReputationRequestCampaign).where(
                ReputationRequestCampaign.id == campaign_id,
                ReputationRequestCampaign.deleted_at.is_(None),
            ),
            context.current_org_id,
            ReputationRequestCampaign,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found")
    row.status = ReputationRequestCampaignStatus.RUNNING
    task_count = create_reputation_campaign_tasks(
        db=db,
        org_id=context.current_org_id,
        template_key=row.template_key,
        audience=row.audience.value,
    )
    db.flush()
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="reputation",
        channel="campaign",
        event_type="REVIEW_CAMPAIGN_STARTED",
        payload_json={"campaign_id": str(row.id), "tasks_created": task_count},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="reputation.campaign_started",
        target_type="reputation_campaign",
        target_id=str(row.id),
        metadata_json={"tasks_created": task_count},
        risk_tier=RiskTier.TIER_1,
    )
    db.commit()
    db.refresh(row)
    return _serialize_campaign(row)


@router.get("/campaigns", response_model=list[ReputationCampaignResponse])
def list_campaigns(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[ReputationCampaignResponse]:
    rows = db.scalars(
        org_scoped(
            select(ReputationRequestCampaign)
            .where(ReputationRequestCampaign.deleted_at.is_(None))
            .order_by(desc(ReputationRequestCampaign.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            ReputationRequestCampaign,
        )
    ).all()
    return [_serialize_campaign(row) for row in rows]
