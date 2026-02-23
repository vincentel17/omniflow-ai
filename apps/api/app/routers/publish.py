from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ContentItem, ContentItemStatus, PublishJob, PublishJobStatus, Role
from ..schemas import PublishJobCreateRequest, PublishJobResponse
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..services.rate_limit import enforce_org_rate_limit
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/publish/jobs", tags=["publish"])


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


@router.post("", response_model=PublishJobResponse, status_code=status.HTTP_201_CREATED)
def create_publish_job(
    payload: PublishJobCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> PublishJobResponse:
    require_role(context, Role.AGENT)
    enforce_org_rate_limit(org_id=context.current_org_id, bucket_name="publish_jobs", max_requests=30, window_seconds=60)
    item = db.scalar(
        org_scoped(
            select(ContentItem).where(ContentItem.id == payload.content_item_id, ContentItem.deleted_at.is_(None)),
            context.current_org_id,
            ContentItem,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content item not found")
    if item.status not in (ContentItemStatus.APPROVED, ContentItemStatus.SCHEDULED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="content is not ready to publish")

    existing = db.scalar(
        org_scoped(
            select(PublishJob).where(PublishJob.content_item_id == item.id, PublishJob.deleted_at.is_(None)),
            context.current_org_id,
            PublishJob,
        )
    )
    if existing is not None:
        return _serialize_publish_job(existing)

    key = f"{context.current_org_id}:{item.id}:{payload.provider}:{payload.account_ref}"
    job = PublishJob(
        org_id=context.current_org_id,
        content_item_id=item.id,
        provider=payload.provider,
        account_ref=payload.account_ref,
        schedule_at=payload.schedule_at,
        status=PublishJobStatus.QUEUED,
        idempotency_key=key,
        attempts=0,
    )
    item.status = ContentItemStatus.SCHEDULED
    db.add(job)
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="publish.job_created",
        target_type="publish_job",
        target_id=str(job.id),
        metadata_json={"provider": job.provider},
        risk_tier=item.risk_tier,
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="publish",
        channel=item.channel,
        event_type="PUBLISH_JOB_CREATED",
        content_id=str(item.id),
        payload_json={"publish_job_id": str(job.id)},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(job)
    return _serialize_publish_job(job)


@router.get("", response_model=list[PublishJobResponse])
def list_publish_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[PublishJobResponse]:
    rows = db.scalars(
        org_scoped(
            select(PublishJob)
            .where(PublishJob.deleted_at.is_(None))
            .order_by(desc(PublishJob.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            PublishJob,
        )
    ).all()
    return [_serialize_publish_job(row) for row in rows]


@router.post("/{job_id}/cancel", response_model=PublishJobResponse)
def cancel_publish_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> PublishJobResponse:
    require_role(context, Role.AGENT)
    job = db.scalar(
        org_scoped(
            select(PublishJob).where(PublishJob.id == job_id, PublishJob.deleted_at.is_(None)),
            context.current_org_id,
            PublishJob,
        )
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="publish job not found")
    if job.status in (PublishJobStatus.SUCCEEDED, PublishJobStatus.CANCELED):
        return _serialize_publish_job(job)

    job.status = PublishJobStatus.CANCELED
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="publish.job_canceled",
        target_type="publish_job",
        target_id=str(job.id),
        metadata_json={},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="publish",
        channel=job.provider,
        event_type="PUBLISH_JOB_CANCELED",
        content_id=str(job.content_item_id),
        payload_json={"publish_job_id": str(job.id)},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(job)
    return _serialize_publish_job(job)
