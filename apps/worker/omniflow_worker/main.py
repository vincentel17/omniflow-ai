import os
import uuid
from datetime import datetime, timedelta, timezone

from celery import Celery
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    AuditLog,
    ConnectorAccount,
    ContentItem,
    ContentItemStatus,
    Event,
    InboxMessage,
    InboxMessageDirection,
    InboxThread,
    InboxThreadStatus,
    NurtureTask,
    NurtureTaskStatus,
    NurtureTaskType,
    Org,
    PresenceAuditRun,
    PresenceAuditRunStatus,
    PresenceTask,
    PresenceTaskStatus,
    PresenceTaskType,
    PublishJob,
    PublishJobStatus,
    ReputationReview,
    RiskTier,
    SLAConfig,
)

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


@app.task(name="worker.inbox.ingest_poll")
def inbox_ingest_poll(provider: str, account_ref: str) -> str:
    connector_mode = os.getenv("CONNECTOR_MODE", "mock")
    if connector_mode == "mock":
        return "noop_mock_mode"
    raise NotImplementedError(f"live ingest polling not implemented for {provider}:{account_ref}")


@app.task(name="worker.sla.monitor_tick")
def sla_monitor_tick() -> int:
    escalations = 0
    now = _now()
    with SessionLocal() as db:
        configs = db.scalars(select(SLAConfig).where(SLAConfig.deleted_at.is_(None))).all()
        for config in configs:
            threshold_minutes = config.response_time_minutes
            open_threads = db.scalars(
                select(InboxThread).where(
                    InboxThread.org_id == config.org_id,
                    InboxThread.status != InboxThreadStatus.CLOSED,
                    InboxThread.deleted_at.is_(None),
                )
            ).all()
            for thread in open_threads:
                last_inbound = db.scalar(
                    select(InboxMessage)
                    .where(
                        InboxMessage.org_id == config.org_id,
                        InboxMessage.thread_id == thread.id,
                        InboxMessage.direction == InboxMessageDirection.INBOUND,
                        InboxMessage.deleted_at.is_(None),
                    )
                    .order_by(InboxMessage.created_at.desc())
                    .limit(1)
                )
                if last_inbound is None:
                    continue
                age_minutes = (now - last_inbound.created_at).total_seconds() / 60.0
                if age_minutes < threshold_minutes:
                    continue
                existing = db.scalar(
                    select(NurtureTask).where(
                        NurtureTask.org_id == config.org_id,
                        NurtureTask.lead_id == thread.lead_id,
                        NurtureTask.template_key == "sla_escalation",
                        NurtureTask.status == NurtureTaskStatus.OPEN,
                        NurtureTask.deleted_at.is_(None),
                    )
                )
                if existing is not None:
                    continue
                task = NurtureTask(
                    org_id=config.org_id,
                    lead_id=thread.lead_id,
                    type=NurtureTaskType.TASK,
                    due_at=now,
                    status=NurtureTaskStatus.OPEN,
                    template_key="sla_escalation",
                    payload_json={"thread_id": str(thread.id), "reason": "response_sla_exceeded"},
                    created_by=None,
                )
                db.add(task)
                db.flush()
                _write_system_event(
                    db=db,
                    org_id=config.org_id,
                    channel="inbox",
                    event_type="SLA_ESCALATED",
                    content_id=thread.id,
                    payload={"thread_id": str(thread.id), "task_id": str(task.id)},
                )
                _write_system_audit(
                    db=db,
                    org_id=config.org_id,
                    action="sla.escalated",
                    target_type="inbox_thread",
                    target_id=str(thread.id),
                    risk_tier=RiskTier.TIER_2,
                    metadata={"task_id": str(task.id)},
                )
                escalations += 1
        db.commit()
    return escalations


@app.task(name="worker.presence.audit_tick")
def presence_audit_tick() -> int:
    """Mock-first scheduler stub: creates periodic successful audit runs for connected orgs."""
    runs_created = 0
    now = _now()
    with SessionLocal() as db:
        orgs = db.scalars(select(Org).where(Org.deleted_at.is_(None))).all()
        for org in orgs:
            has_connector = db.scalar(
                select(ConnectorAccount.id).where(
                    ConnectorAccount.org_id == org.id,
                    ConnectorAccount.deleted_at.is_(None),
                )
            )
            if has_connector is None:
                continue
            latest = db.scalar(
                select(PresenceAuditRun)
                .where(PresenceAuditRun.org_id == org.id, PresenceAuditRun.deleted_at.is_(None))
                .order_by(PresenceAuditRun.created_at.desc())
                .limit(1)
            )
            if latest is not None and latest.created_at >= now - timedelta(hours=24):
                continue

            run = PresenceAuditRun(
                org_id=org.id,
                started_at=now,
                completed_at=now,
                status=PresenceAuditRunStatus.SUCCEEDED,
                inputs_json={"providers_to_audit": ["gbp", "meta", "linkedin"], "run_mode": "scheduled"},
                summary_scores_json={"overall_score": 80, "category_scores": {"profile": 80, "seo": 80}},
                notes_json={"mode": "scheduled_mock"},
                error_json={},
            )
            db.add(run)
            db.flush()
            _write_system_event(
                db=db,
                org_id=org.id,
                channel="presence",
                event_type="PRESENCE_AUDIT_RUN",
                content_id=run.id,
                payload={"audit_run_id": str(run.id), "overall_score": 80},
            )
            _write_system_audit(
                db=db,
                org_id=org.id,
                action="presence.audit_tick_executed",
                target_type="presence_audit_run",
                target_id=str(run.id),
                risk_tier=RiskTier.TIER_1,
                metadata={"mode": "scheduled_mock"},
            )
            runs_created += 1
        db.commit()
    return runs_created


@app.task(name="worker.reputation.sla_tick")
def reputation_sla_tick() -> int:
    """Creates response tasks for negative reviews that remain unanswered past SLA."""
    created = 0
    now = _now()
    threshold = now - timedelta(hours=24)
    with SessionLocal() as db:
        reviews = db.scalars(
            select(ReputationReview).where(
                ReputationReview.deleted_at.is_(None),
                ReputationReview.rating <= 2,
                ReputationReview.responded_at.is_(None),
                ReputationReview.created_at <= threshold,
            )
        ).all()
        for review in reviews:
            existing = db.scalar(
                select(PresenceTask.id).where(
                    PresenceTask.org_id == review.org_id,
                    PresenceTask.type == PresenceTaskType.RESPOND_REVIEW,
                    PresenceTask.status == PresenceTaskStatus.OPEN,
                    PresenceTask.deleted_at.is_(None),
                    PresenceTask.payload_json["review_id"].as_string() == str(review.id),
                )
            )
            if existing is not None:
                continue
            task = PresenceTask(
                org_id=review.org_id,
                finding_id=None,
                type=PresenceTaskType.RESPOND_REVIEW,
                assigned_to_user_id=None,
                due_at=now,
                status=PresenceTaskStatus.OPEN,
                payload_json={"review_id": str(review.id), "reason": "negative_review_sla"},
            )
            db.add(task)
            db.flush()
            _write_system_event(
                db=db,
                org_id=review.org_id,
                channel="reputation",
                event_type="SLA_ESCALATED",
                content_id=task.id,
                payload={"review_id": str(review.id), "task_id": str(task.id)},
            )
            _write_system_audit(
                db=db,
                org_id=review.org_id,
                action="reputation.sla_escalated",
                target_type="reputation_review",
                target_id=str(review.id),
                risk_tier=RiskTier.TIER_2,
                metadata={"task_id": str(task.id)},
            )
            created += 1
        db.commit()
    return created
