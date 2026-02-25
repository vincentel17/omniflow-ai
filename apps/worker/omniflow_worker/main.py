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
    ConnectorHealth,
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
    OrgSettings,
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
from app.services.connector_manager import get_publisher
from app.services.live_publishers import ConnectorError

broker_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = Celery("omniflow-worker", broker=broker_url, backend=broker_url)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _publish_mock(provider: str, account_ref: str, content: ContentItem) -> str:
    suffix = str(content.id).split("-")[0]
    return f"mock-{provider}-{account_ref}-{suffix}"


def _org_settings_payload(db: Session, org_id: uuid.UUID) -> dict[str, object]:
    row = db.scalar(select(OrgSettings).where(OrgSettings.org_id == org_id, OrgSettings.deleted_at.is_(None)))
    if row is None or not isinstance(row.settings_json, dict):
        return {}
    return row.settings_json


def _org_feature_enabled(db: Session, org_id: uuid.UUID, key: str, fallback: bool) -> bool:
    payload = _org_settings_payload(db=db, org_id=org_id)
    raw = payload.get(key)
    return raw if isinstance(raw, bool) else fallback


def _org_connector_mode(db: Session, org_id: uuid.UUID) -> str:
    payload = _org_settings_payload(db=db, org_id=org_id)
    raw = payload.get("connector_mode")
    if isinstance(raw, str) and raw in {"mock", "live"}:
        return raw
    return os.getenv("CONNECTOR_MODE", "mock")


_PROVIDER_PREFIX = {
    "google-business-profile": "gbp",
    "meta": "meta",
    "linkedin": "linkedin",
}


def _provider_publish_enabled(db: Session, org_id: uuid.UUID, provider: str) -> bool:
    payload = _org_settings_payload(db=db, org_id=org_id)
    if payload.get("connector_mode") != "live":
        return False
    prefix = _PROVIDER_PREFIX.get(provider)
    if prefix is None:
        return False
    providers_enabled = payload.get("providers_enabled_json")
    if not isinstance(providers_enabled, dict):
        return False
    return providers_enabled.get(f"{prefix}_publish_enabled") is True


def _record_connector_failure(db: Session, org_id: uuid.UUID, provider: str, account_ref: str, error_message: str) -> None:
    health = db.scalar(
        select(ConnectorHealth).where(
            ConnectorHealth.org_id == org_id,
            ConnectorHealth.provider == provider,
            ConnectorHealth.account_ref == account_ref,
            ConnectorHealth.deleted_at.is_(None),
        )
    )
    if health is None:
        health = ConnectorHealth(org_id=org_id, provider=provider, account_ref=account_ref, consecutive_failures=0)
        db.add(health)
    health.consecutive_failures = int(health.consecutive_failures or 0) + 1
    health.last_error_at = _now()
    health.last_error_msg = error_message[:500]

    threshold = int(os.getenv("CONNECTOR_CIRCUIT_BREAKER_THRESHOLD", "3"))
    if health.consecutive_failures >= threshold:
        account = db.scalar(
            select(ConnectorAccount).where(
                ConnectorAccount.org_id == org_id,
                ConnectorAccount.provider == provider,
                ConnectorAccount.account_ref == account_ref,
                ConnectorAccount.deleted_at.is_(None),
            )
        )
        if account is not None:
            account.status = "circuit_open"




def _connector_breaker_open(db: Session, org_id: uuid.UUID, provider: str, account_ref: str) -> bool:
    account = db.scalar(
        select(ConnectorAccount).where(
            ConnectorAccount.org_id == org_id,
            ConnectorAccount.provider == provider,
            ConnectorAccount.account_ref == account_ref,
            ConnectorAccount.deleted_at.is_(None),
        )
    )
    if account is None:
        return False

    health = db.scalar(
        select(ConnectorHealth).where(
            ConnectorHealth.org_id == org_id,
            ConnectorHealth.provider == provider,
            ConnectorHealth.account_ref == account_ref,
            ConnectorHealth.deleted_at.is_(None),
        )
    )

    threshold = int(os.getenv("CONNECTOR_CIRCUIT_BREAKER_THRESHOLD", "3"))
    cooldown_seconds = int(os.getenv("CONNECTOR_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "300"))
    failures = int(health.consecutive_failures or 0) if health is not None else 0

    if account.status == "circuit_open" or failures >= threshold:
        if health is None or health.last_error_at is None:
            return True
        cooldown_elapsed = _now() >= health.last_error_at + timedelta(seconds=max(1, cooldown_seconds))
        if cooldown_elapsed:
            account.status = "linked"
            health.consecutive_failures = 0
            return False
        return True
    return False

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
        if not _org_feature_enabled(db=db, org_id=job.org_id, key="enable_auto_posting", fallback=False):
            job.status = PublishJobStatus.CANCELED
            job.last_error = "auto posting disabled by org ops settings"
            db.commit()
            return "auto_posting_disabled"

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
            live_enabled = _provider_publish_enabled(db=db, org_id=job.org_id, provider=job.provider)
            if not live_enabled:
                job.status = PublishJobStatus.FAILED
                content.status = ContentItemStatus.FAILED
                job.last_error = "LIVE_DISABLED"
                _write_system_event(
                    db=db,
                    org_id=job.org_id,
                    channel=content.channel,
                    event_type="CONNECTOR_LIVE_CALL_FAIL",
                    content_id=content.id,
                    payload={"publish_job_id": str(job.id), "reason": "LIVE_DISABLED"},
                )
                _write_system_audit(
                    db=db,
                    org_id=job.org_id,
                    action="publish.live_blocked",
                    target_type="publish_job",
                    target_id=str(job.id),
                    risk_tier=content.risk_tier,
                    metadata={"reason": "LIVE_DISABLED"},
                )
                db.commit()
                return "live_disabled"

            if _connector_breaker_open(db=db, org_id=job.org_id, provider=job.provider, account_ref=job.account_ref):
                job.status = PublishJobStatus.FAILED
                content.status = ContentItemStatus.FAILED
                job.last_error = "BREAKER_TRIPPED"
                _write_system_event(
                    db=db,
                    org_id=job.org_id,
                    channel=content.channel,
                    event_type="CONNECTOR_LIVE_CALL_FAIL",
                    content_id=content.id,
                    payload={"publish_job_id": str(job.id), "reason": "BREAKER_TRIPPED"},
                )
                _write_system_audit(
                    db=db,
                    org_id=job.org_id,
                    action="publish.live_blocked",
                    target_type="publish_job",
                    target_id=str(job.id),
                    risk_tier=content.risk_tier,
                    metadata={"reason": "BREAKER_TRIPPED"},
                )
                db.commit()
                return "breaker_tripped"

            _write_system_event(
                db=db,
                org_id=job.org_id,
                channel=content.channel,
                event_type="CONNECTOR_LIVE_CALL_ATTEMPT",
                content_id=content.id,
                payload={"publish_job_id": str(job.id), "provider": job.provider},
            )

            publisher = get_publisher(provider=job.provider, org_id=job.org_id, account_ref=job.account_ref, db=db)
            result = publisher.publish_post(
                {
                    "channel": content.channel,
                    "text": content.text_rendered,
                    "media_urls": content.media_refs_json,
                    "link_url": content.link_url,
                    "tags": content.tags_json,
                    "account_ref": job.account_ref,
                }
            )
            external_id = str(result.get("external_id") or _publish_mock(provider=job.provider, account_ref=job.account_ref, content=content))

            job.status = PublishJobStatus.SUCCEEDED
            job.external_id = external_id
            job.published_at = _now()
            job.last_error = None
            content.status = ContentItemStatus.PUBLISHED
            _write_system_event(
                db=db,
                org_id=job.org_id,
                channel=content.channel,
                event_type="CONNECTOR_LIVE_CALL_SUCCESS",
                content_id=content.id,
                payload={"publish_job_id": str(job.id), "provider": job.provider},
            )
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
        except ConnectorError as exc:  # pragma: no cover - retry path
            job.last_error = str(exc)[:500]
            _record_connector_failure(
                db=db,
                org_id=job.org_id,
                provider=job.provider,
                account_ref=job.account_ref,
                error_message=job.last_error,
            )
            if exc.category in {"auth", "reauth_required"}:
                account = db.scalar(
                    select(ConnectorAccount).where(
                        ConnectorAccount.org_id == job.org_id,
                        ConnectorAccount.provider == job.provider,
                        ConnectorAccount.account_ref == job.account_ref,
                        ConnectorAccount.deleted_at.is_(None),
                    )
                )
                if account is not None:
                    account.status = "reauth_required"
                _write_system_event(
                    db=db,
                    org_id=job.org_id,
                    channel=content.channel,
                    event_type="CONNECTOR_REAUTH_REQUIRED",
                    content_id=content.id,
                    payload={"publish_job_id": str(job.id), "provider": job.provider},
                )
            _write_system_event(
                db=db,
                org_id=job.org_id,
                channel=content.channel,
                event_type="CONNECTOR_LIVE_CALL_FAIL",
                content_id=content.id,
                payload={"publish_job_id": str(job.id), "error_category": exc.category},
            )
            raise
        except Exception as exc:  # pragma: no cover - retry path
            job.last_error = str(exc)[:500]
            _record_connector_failure(
                db=db,
                org_id=job.org_id,
                provider=job.provider,
                account_ref=job.account_ref,
                error_message=job.last_error,
            )
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
            if not _org_feature_enabled(db=db, org_id=row.org_id, key="enable_auto_posting", fallback=False):
                continue
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
            if not _org_feature_enabled(db=db, org_id=org.id, key="enable_scheduled_audits", fallback=True):
                continue
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

