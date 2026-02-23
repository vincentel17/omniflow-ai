import os
import uuid
from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import AuditLog, ContentItem, ContentItemStatus, Event, PublishJob, PublishJobStatus, RiskTier

broker_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = Celery("omniflow-worker", broker=broker_url, backend=broker_url)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _publish_mock(provider: str, account_ref: str, content: ContentItem) -> str:
    suffix = str(content.id).split("-")[0]
    return f"mock-{provider}-{account_ref}-{suffix}"


def _write_system_event(
    db: Session,
    org_id: uuid.UUID,
    channel: str,
    event_type: str,
    content_id: uuid.UUID,
    payload: dict[str, object] | None = None,
) -> None:
    db.add(
        Event(
            org_id=org_id,
            source="worker",
            channel=channel,
            type=event_type,
            content_id=str(content_id),
            payload_json=payload or {},
        )
    )


def _write_system_audit(
    db: Session,
    org_id: uuid.UUID,
    action: str,
    target_type: str,
    target_id: str,
    risk_tier: RiskTier,
    metadata: dict[str, object] | None = None,
) -> None:
    db.add(
        AuditLog(
            org_id=org_id,
            actor_user_id=None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            risk_tier=risk_tier,
            metadata_json=metadata or {},
        )
    )


@app.task(name="worker.health.ping")
def ping() -> str:
    return "pong"


@app.task(name="worker.publish.execute", bind=True, max_retries=3, retry_backoff=True)
def publish_job_execute(self: Celery, publish_job_id: str) -> str:
    with SessionLocal() as db:
        job = db.scalar(select(PublishJob).where(PublishJob.id == uuid.UUID(publish_job_id), PublishJob.deleted_at.is_(None)))
        if job is None:
            return "missing"
        if job.status == PublishJobStatus.SUCCEEDED:
            return "already_succeeded"
        if job.status == PublishJobStatus.CANCELED:
            return "canceled"

        content = db.scalar(
            select(ContentItem).where(
                and_(
                    ContentItem.id == job.content_item_id,
                    ContentItem.org_id == job.org_id,
                    ContentItem.deleted_at.is_(None),
                )
            )
        )
        if content is None:
            job.status = PublishJobStatus.FAILED
            job.last_error = "content item not found"
            db.commit()
            return "missing_content"

        job.status = PublishJobStatus.RUNNING
        job.attempts += 1
        content.status = ContentItemStatus.PUBLISHING
        db.flush()
        _write_system_event(
            db=db,
            org_id=job.org_id,
            channel=content.channel,
            event_type="PUBLISH_ATTEMPT",
            content_id=content.id,
            payload={"publish_job_id": str(job.id), "attempt": job.attempts},
        )

        try:
            connector_mode = os.getenv("CONNECTOR_MODE", "mock")
            if connector_mode != "mock":
                raise NotImplementedError("live connector publish is not implemented")
            external_id = _publish_mock(provider=job.provider, account_ref=job.account_ref, content=content)

            job.status = PublishJobStatus.SUCCEEDED
            job.external_id = external_id
            job.published_at = _now()
            job.last_error = None
            content.status = ContentItemStatus.PUBLISHED
            _write_system_event(
                db=db,
                org_id=job.org_id,
                channel=content.channel,
                event_type="PUBLISH_SUCCESS",
                content_id=content.id,
                payload={"publish_job_id": str(job.id), "external_id": external_id},
            )
            _write_system_audit(
                db=db,
                org_id=job.org_id,
                action="publish.job_succeeded",
                target_type="publish_job",
                target_id=str(job.id),
                risk_tier=content.risk_tier,
                metadata={"external_id": external_id},
            )
            db.commit()
            return "succeeded"
        except Exception as exc:  # pragma: no cover - retry path
            job.last_error = str(exc)[:500]
            if job.attempts >= 3:
                job.status = PublishJobStatus.FAILED
                content.status = ContentItemStatus.FAILED
                _write_system_event(
                    db=db,
                    org_id=job.org_id,
                    channel=content.channel,
                    event_type="PUBLISH_FAIL",
                    content_id=content.id,
                    payload={"publish_job_id": str(job.id), "error": job.last_error},
                )
                _write_system_audit(
                    db=db,
                    org_id=job.org_id,
                    action="publish.job_failed",
                    target_type="publish_job",
                    target_id=str(job.id),
                    risk_tier=content.risk_tier,
                    metadata={"error": job.last_error},
                )
                db.commit()
                return "failed"
            job.status = PublishJobStatus.QUEUED
            db.commit()
            raise self.retry(exc=exc)


@app.task(name="worker.publish.scheduler_tick")
def scheduler_tick() -> int:
    enqueued = 0
    with SessionLocal() as db:
        rows = db.scalars(
            select(PublishJob).where(
                PublishJob.deleted_at.is_(None),
                PublishJob.status == PublishJobStatus.QUEUED,
                (PublishJob.schedule_at.is_(None) | (PublishJob.schedule_at <= _now())),
            )
        ).all()
        for row in rows:
            publish_job_execute.delay(str(row.id))
            enqueued += 1
    return enqueued
