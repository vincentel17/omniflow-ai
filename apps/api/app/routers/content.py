from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Approval,
    ApprovalEntityType,
    ApprovalStatus,
    BrandProfile,
    ContentItem,
    ContentItemStatus,
    PublishJob,
    PublishJobStatus,
    Role,
)
from ..schemas import (
    ApprovalDecisionRequest,
    ContentDetailResponse,
    ContentListItemResponse,
    ContentScheduleRequest,
    PublishJobResponse,
)
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..services.phase3 import utcnow
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/content", tags=["content"])


def _serialize_content_item(item: ContentItem) -> ContentListItemResponse:
    return ContentListItemResponse(
        id=item.id,
        org_id=item.org_id,
        campaign_plan_id=item.campaign_plan_id,
        channel=item.channel,
        account_ref=item.account_ref,
        status=item.status,
        risk_tier=item.risk_tier,
        policy_warnings_json=item.policy_warnings_json,
        created_at=item.created_at,
    )


def _serialize_publish_job(job: PublishJob) -> PublishJobResponse:
    return PublishJobResponse(
        id=job.id,
        org_id=job.org_id,
        content_item_id=job.content_item_id,
        provider=job.provider,
        account_ref=job.account_ref,
        schedule_at=job.schedule_at,
        status=job.status,
        idempotency_key=job.idempotency_key,
        attempts=job.attempts,
        last_error=job.last_error,
        external_id=job.external_id,
        published_at=job.published_at,
        created_at=job.created_at,
    )


def _approval_required(db: Session, org_id: uuid.UUID) -> bool:
    profile = db.scalar(select(BrandProfile).where(BrandProfile.org_id == org_id, BrandProfile.deleted_at.is_(None)))
    return True if profile is None else profile.require_approval_for_publish


@router.get("", response_model=list[ContentListItemResponse])
def list_content(
    status_filter: ContentItemStatus | None = Query(default=None, alias="status"),
    channel: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[ContentListItemResponse]:
    stmt = org_scoped(
        select(ContentItem)
        .where(ContentItem.deleted_at.is_(None))
        .order_by(desc(ContentItem.created_at))
        .limit(limit)
        .offset(offset),
        context.current_org_id,
        ContentItem,
    )
    if status_filter is not None:
        stmt = stmt.where(ContentItem.status == status_filter)
    if channel is not None:
        stmt = stmt.where(ContentItem.channel == channel)
    rows = db.scalars(stmt).all()
    return [_serialize_content_item(row) for row in rows]


@router.get("/{content_id}", response_model=ContentDetailResponse)
def get_content(
    content_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ContentDetailResponse:
    item = db.scalar(
        org_scoped(
            select(ContentItem).where(ContentItem.id == content_id, ContentItem.deleted_at.is_(None)),
            context.current_org_id,
            ContentItem,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content item not found")
    return ContentDetailResponse(
        **_serialize_content_item(item).model_dump(),
        content_json=item.content_json,
        text_rendered=item.text_rendered,
        media_refs_json=item.media_refs_json,
        link_url=item.link_url,
        tags_json=item.tags_json,
    )


@router.post("/{content_id}/approve", response_model=ContentDetailResponse)
def approve_content(
    content_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ContentDetailResponse:
    require_role(context, Role.ADMIN)
    if payload.status not in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid approval status")

    item = db.scalar(
        org_scoped(
            select(ContentItem).where(ContentItem.id == content_id, ContentItem.deleted_at.is_(None)),
            context.current_org_id,
            ContentItem,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content item not found")
    item.status = ContentItemStatus.APPROVED if payload.status == ApprovalStatus.APPROVED else ContentItemStatus.FAILED

    approval = Approval(
        org_id=context.current_org_id,
        entity_type=ApprovalEntityType.CONTENT_ITEM,
        entity_id=item.id,
        status=payload.status,
        requested_by=context.current_user_id,
        decided_by=context.current_user_id,
        decided_at=utcnow(),
        notes=payload.notes,
    )
    db.add(approval)
    db.flush()

    write_audit_log(
        db=db,
        context=context,
        action="content.approval_decided",
        target_type="content_item",
        target_id=str(item.id),
        metadata_json={"status": payload.status.value},
        risk_tier=item.risk_tier,
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="approval",
        channel=item.channel,
        event_type="CONTENT_APPROVAL_DECIDED",
        content_id=str(item.id),
        payload_json={"status": payload.status.value},
        actor_id=str(context.current_user_id),
    )

    db.commit()
    db.refresh(item)
    return ContentDetailResponse(
        **_serialize_content_item(item).model_dump(),
        content_json=item.content_json,
        text_rendered=item.text_rendered,
        media_refs_json=item.media_refs_json,
        link_url=item.link_url,
        tags_json=item.tags_json,
    )


@router.post("/{content_id}/schedule", response_model=PublishJobResponse, status_code=status.HTTP_201_CREATED)
def schedule_content(
    content_id: uuid.UUID,
    payload: ContentScheduleRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> PublishJobResponse:
    require_role(context, Role.AGENT)
    item = db.scalar(
        org_scoped(
            select(ContentItem).where(ContentItem.id == content_id, ContentItem.deleted_at.is_(None)),
            context.current_org_id,
            ContentItem,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content item not found")
    if _approval_required(db=db, org_id=context.current_org_id) and item.status != ContentItemStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="content must be approved before scheduling")

    existing = db.scalar(
        org_scoped(
            select(PublishJob).where(PublishJob.content_item_id == item.id, PublishJob.deleted_at.is_(None)),
            context.current_org_id,
            PublishJob,
        )
    )
    if existing is not None:
        return _serialize_publish_job(existing)

    idempotency_key = f"{context.current_org_id}:{item.id}:{payload.provider}:{payload.account_ref}"
    job = PublishJob(
        org_id=context.current_org_id,
        content_item_id=item.id,
        provider=payload.provider,
        account_ref=payload.account_ref,
        schedule_at=payload.schedule_at,
        status=PublishJobStatus.QUEUED,
        idempotency_key=idempotency_key,
        attempts=0,
    )
    item.status = ContentItemStatus.SCHEDULED
    db.add(job)
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="publish.job_scheduled",
        target_type="publish_job",
        target_id=str(job.id),
        metadata_json={"provider": job.provider, "account_ref": job.account_ref},
        risk_tier=item.risk_tier,
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="publish",
        channel=item.channel,
        event_type="PUBLISH_JOB_QUEUED",
        content_id=str(item.id),
        payload_json={"publish_job_id": str(job.id)},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(job)
    return _serialize_publish_job(job)
