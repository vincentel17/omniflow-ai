import os
import uuid
from datetime import datetime, timedelta, timezone

from celery import Celery
from sqlalchemy import and_, func, select
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
    OrgStatus,
    OrgSubscription,
    UsageMetric,
    UsageMetricType,
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
from app.services.events import write_event
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


def _org_is_active(db: Session, org_id: uuid.UUID) -> bool:
    row = db.scalar(select(Org).where(Org.id == org_id, Org.deleted_at.is_(None)))
    if row is None:
        return False
    return row.org_status == OrgStatus.ACTIVE
def _as_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


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
    write_event(
        db=db,
        org_id=org_id,
        source="worker",
        channel=channel,
        event_type=event_type,
        content_id=str(content_id),
        payload_json=payload or {},
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
        if not _org_is_active(db=db, org_id=job.org_id):
            job.status = PublishJobStatus.CANCELED
            job.last_error = "ORG_NOT_ACTIVE"
            db.commit()
            return "org_not_active"
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
            if not _org_is_active(db=db, org_id=row.org_id):
                continue
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


def _first_member_user_id(db: Session, org_id: uuid.UUID) -> uuid.UUID | None:
    from app.models import Membership

    row = db.scalar(
        select(Membership).where(Membership.org_id == org_id, Membership.deleted_at.is_(None)).order_by(Membership.created_at)
    )
    return row.user_id if row is not None else None


def _risk_tier_enum(value: int) -> RiskTier:
    mapping = {
        0: RiskTier.TIER_0,
        1: RiskTier.TIER_1,
        2: RiskTier.TIER_2,
        3: RiskTier.TIER_3,
        4: RiskTier.TIER_4,
    }
    return mapping.get(max(0, min(4, int(value))), RiskTier.TIER_2)


def _workflow_event_payload(base: dict[str, object], run_id: uuid.UUID, depth: int) -> dict[str, object]:
    payload = dict(base)
    payload["workflow_origin"] = {"workflow_run_id": str(run_id), "depth": depth}
    return payload


def _sanitize_workflow_error(value: object) -> str:
    message = str(value)
    lowered = message.lower()
    if "token" in lowered or "authorization" in lowered or "bearer" in lowered:
        return "redacted-sensitive-error"
    return message[:500]


def _execute_workflow_action(db: Session, action_run_id: uuid.UUID) -> dict[str, object]:
    from app.models import (
        CampaignPlan,
        CampaignPlanStatus,
        ConnectorWorkflowRun,
        ContentItem,
        ContentItemStatus,
        InboxMessage,
        InboxMessageDirection,
        Lead,
        LeadAssignment,
        NurtureTask,
        NurtureTaskStatus,
        NurtureTaskType,
        PresenceAuditRun,
        PresenceAuditRunStatus,
        PublishJob,
        PublishJobStatus,
        WorkflowActionRun,
        WorkflowRun,
    )
    from app.services.phase4 import choose_round_robin_assignee

    action_run = db.scalar(
        select(WorkflowActionRun).where(WorkflowActionRun.id == action_run_id, WorkflowActionRun.deleted_at.is_(None))
    )
    if action_run is None:
        return {"result": "missing"}

    workflow_run = db.scalar(
        select(WorkflowRun).where(WorkflowRun.id == action_run.workflow_run_id, WorkflowRun.deleted_at.is_(None))
    )
    if workflow_run is None:
        return {"result": "missing_workflow_run"}

    input_json = action_run.input_json if isinstance(action_run.input_json, dict) else {}
    raw_params = input_json.get("params_json")
    params = raw_params if isinstance(raw_params, dict) else {}
    action_type = action_run.action_type
    org_id = action_run.org_id


    if action_type == "CREATE_TASK":
        lead_id_raw = params.get("lead_id")
        if not lead_id_raw:
            trigger_event = db.scalar(select(Event).where(Event.id == workflow_run.trigger_event_id, Event.deleted_at.is_(None)))
            lead_id_raw = str(trigger_event.lead_id) if trigger_event is not None and trigger_event.lead_id else None
        if not lead_id_raw:
            raise ValueError("CREATE_TASK requires lead_id")
        lead_id = uuid.UUID(str(lead_id_raw))
        task = NurtureTask(
            org_id=org_id,
            lead_id=lead_id,
            type=NurtureTaskType.TASK,
            due_at=_now() + timedelta(minutes=_as_int(params.get("due_in_minutes", 30), 30)),
            status=NurtureTaskStatus.OPEN,
            template_key=str(params.get("template_key", "workflow_task")),
            payload_json={"title": str(params.get("title", "Workflow task"))},
            created_by=None,
        )
        db.add(task)
        db.flush()
        return {"task_id": str(task.id)}

    if action_type == "ROUTE_LEAD":
        if not _org_feature_enabled(db=db, org_id=org_id, key="enable_auto_lead_routing", fallback=True):
            raise ValueError("ROUTE_LEAD blocked by org setting")
        lead_id = uuid.UUID(str(params.get("lead_id")))
        assignee, rationale = choose_round_robin_assignee(db=db, org_id=org_id)
        existing = db.scalar(
            select(LeadAssignment).where(
                LeadAssignment.org_id == org_id,
                LeadAssignment.lead_id == lead_id,
                LeadAssignment.deleted_at.is_(None),
            )
        )
        if existing is None:
            existing = LeadAssignment(
                org_id=org_id,
                lead_id=lead_id,
                assigned_to_user_id=assignee,
                rule_applied=rationale,
            )
            db.add(existing)
        else:
            existing.assigned_to_user_id = assignee
            existing.rule_applied = rationale
        db.flush()
        return {"lead_id": str(lead_id), "assigned_to_user_id": str(assignee), "rule": rationale}

    if action_type == "APPLY_NURTURE_PLAN":
        if not _org_feature_enabled(db=db, org_id=org_id, key="enable_auto_nurture_apply", fallback=False):
            raise ValueError("APPLY_NURTURE_PLAN blocked by org setting")
        lead_id = uuid.UUID(str(params.get("lead_id")))
        task = NurtureTask(
            org_id=org_id,
            lead_id=lead_id,
            type=NurtureTaskType.TASK,
            due_at=_now() + timedelta(minutes=_as_int(params.get("due_in_minutes", 60), 60)),
            status=NurtureTaskStatus.OPEN,
            template_key=str(params.get("template_key", "nurture_followup")),
            payload_json={"message_body": str(params.get("message_body", "Follow up with this lead"))},
            created_by=None,
        )
        db.add(task)
        db.flush()
        return {"task_id": str(task.id)}

    if action_type == "CREATE_CONTENT_DRAFT":
        creator = _first_member_user_id(db=db, org_id=org_id)
        if creator is None:
            raise ValueError("No org member available to own campaign plan")
        week_start = _now().date()
        plan = db.scalar(
            select(CampaignPlan).where(
                CampaignPlan.org_id == org_id,
                CampaignPlan.week_start_date == week_start,
                CampaignPlan.deleted_at.is_(None),
            )
        )
        if plan is None:
            plan = CampaignPlan(
                org_id=org_id,
                vertical_pack_slug=str(params.get("vertical_pack", "generic")),
                week_start_date=week_start,
                status=CampaignPlanStatus.DRAFT,
                created_by=creator,
                plan_json={},
                metadata_json={"source": "workflow"},
            )
            db.add(plan)
            db.flush()
        item = ContentItem(
            org_id=org_id,
            campaign_plan_id=plan.id,
            channel=str(params.get("channel", "web")),
            account_ref=str(params.get("account_ref", "default")),
            status=ContentItemStatus.DRAFT,
            content_json={"template_key": str(params.get("template_key", "workflow"))},
            text_rendered=str(params.get("text", "Workflow generated draft")),
            media_refs_json=[],
            link_url=None,
            tags_json=["workflow"],
            risk_tier=_risk_tier_enum(_as_int(params.get("risk_tier", 1), 1)),
            policy_warnings_json=[],
        )
        db.add(item)
        db.flush()
        return {"content_item_id": str(item.id)}

    if action_type == "SCHEDULE_PUBLISH":
        if not _org_feature_enabled(db=db, org_id=org_id, key="enable_auto_posting", fallback=False):
            raise ValueError("SCHEDULE_PUBLISH blocked by org setting")
        content_item_id = uuid.UUID(str(params.get("content_item_id")))
        content = db.scalar(
            select(ContentItem).where(
                ContentItem.id == content_item_id,
                ContentItem.org_id == org_id,
                ContentItem.deleted_at.is_(None),
            )
        )
        if content is None:
            raise ValueError("content item not found")
        if content.status not in {ContentItemStatus.APPROVED, ContentItemStatus.SCHEDULED, ContentItemStatus.DRAFT}:
            raise ValueError("content is not in schedulable status")
        job = db.scalar(
            select(PublishJob).where(
                PublishJob.org_id == org_id,
                PublishJob.content_item_id == content.id,
                PublishJob.deleted_at.is_(None),
            )
        )
        if job is None:
            job = PublishJob(
                org_id=org_id,
                content_item_id=content.id,
                provider=str(params.get("provider", "mock-provider")),
                account_ref=str(params.get("account_ref", content.account_ref)),
                schedule_at=None,
                status=PublishJobStatus.QUEUED,
                idempotency_key=f"workflow:{action_run.id}",
                attempts=0,
            )
            db.add(job)
            db.flush()
        return {"publish_job_id": str(job.id)}

    if action_type == "RUN_PRESENCE_AUDIT":
        if not _org_feature_enabled(db=db, org_id=org_id, key="enable_scheduled_audits", fallback=True):
            raise ValueError("RUN_PRESENCE_AUDIT blocked by org setting")
        run = PresenceAuditRun(
            org_id=org_id,
            started_at=_now(),
            completed_at=_now(),
            status=PresenceAuditRunStatus.SUCCEEDED,
            inputs_json={"mode": "workflow"},
            summary_scores_json={"overall_score": 80},
            notes_json={"source": "workflow"},
            error_json={},
        )
        db.add(run)
        db.flush()
        return {"presence_audit_run_id": str(run.id)}

    if action_type == "DRAFT_REPLY":
        thread_id = uuid.UUID(str(params.get("thread_id")))
        message = InboxMessage(
            org_id=org_id,
            thread_id=thread_id,
            external_message_id=f"draft-{action_run.id}",
            direction=InboxMessageDirection.OUTBOUND,
            sender_ref="workflow",
            sender_display="Workflow Draft",
            body_text=str(params.get("body_text", "Draft response generated by workflow")),
            body_raw_json={"mode": "draft"},
            flags_json={"draft": True},
        )
        db.add(message)
        db.flush()
        return {"inbox_message_id": str(message.id)}

    if action_type == "TAG_LEAD":
        lead_id = uuid.UUID(str(params.get("lead_id")))
        lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.org_id == org_id, Lead.deleted_at.is_(None)))
        if lead is None:
            raise ValueError("lead not found")
        existing_raw = lead.tags_json if isinstance(lead.tags_json, list) else []
        existing_tags = [str(item) for item in existing_raw]
        additions = params.get("tags", [])
        tags = [str(item) for item in additions] if isinstance(additions, list) else []
        lead.tags_json = sorted(set(existing_tags + tags))
        db.flush()
        return {"lead_id": str(lead.id), "tags": lead.tags_json}

    if action_type == "WEBHOOK":
        row = ConnectorWorkflowRun(
            org_id=org_id,
            provider="webhook",
            account_ref=str(params.get("endpoint", "workflow-webhook")),
            operation="webhook",
            idempotency_key=f"workflow-webhook:{action_run.id}",
            status="queued",
            attempt_count=0,
            max_attempts=1,
            payload_json={"url": params.get("url"), "body": params.get("body")},
            result_json={},
        )
        db.add(row)
        db.flush()
        return {"connector_workflow_run_id": str(row.id), "status": "queued"}

    raise ValueError(f"Unsupported action type: {action_type}")


@app.task(name="worker.workflow.evaluate")
def workflow_evaluate(event_id: str) -> str:
    from app.models import (
        Approval,
        ApprovalEntityType,
        ApprovalStatus,
        Event,
        Workflow,
        WorkflowActionRun,
        WorkflowActionRunStatus,
        WorkflowRun,
        WorkflowRunStatus,
        WorkflowTriggerType,
    )
    from app.services.workflows import (
        action_idempotency_key,
        current_vertical_pack,
        evaluate_definition,
        event_depth,
        local_hour_for_org,
        org_automation_limits,
        settings_for_org,
    )

    with SessionLocal() as db:
        row = db.scalar(select(Event).where(Event.id == uuid.UUID(event_id), Event.deleted_at.is_(None)))
        if row is None:
            return "missing_event"
        if not _org_is_active(db=db, org_id=row.org_id):
            return "org_not_active"

        settings_payload = settings_for_org(db=db, org_id=row.org_id)
        limits = org_automation_limits(settings_payload)
        current_depth = event_depth(row.payload_json if isinstance(row.payload_json, dict) else {})
        if current_depth >= limits["max_depth"]:
            return "max_depth_reached"

        hour_window_start = _now() - timedelta(hours=1)
        recent_runs = db.scalar(
            select(WorkflowRun)
            .where(
                WorkflowRun.org_id == row.org_id,
                WorkflowRun.created_at >= hour_window_start,
                WorkflowRun.deleted_at.is_(None),
            )
            .limit(1)
        )
        if recent_runs is not None:
            run_count = int(
                db.scalar(
                    select(func.count(WorkflowRun.id)).where(
                        WorkflowRun.org_id == row.org_id,
                        WorkflowRun.created_at >= hour_window_start,
                        WorkflowRun.deleted_at.is_(None),
                    )
                )
                or 0
            )
            if run_count >= limits["max_workflow_runs_per_hour"]:
                return "max_workflow_runs_per_hour_reached"

        workflows = db.scalars(
            select(Workflow).where(
                Workflow.org_id == row.org_id,
                Workflow.enabled.is_(True),
                Workflow.trigger_type == WorkflowTriggerType.EVENT,
                Workflow.deleted_at.is_(None),
            )
        ).all()

        auto_tier = _as_int(settings_payload.get("default_autonomy_max_tier", 1), 1)
        local_hour = local_hour_for_org(settings_payload)
        vertical_pack = current_vertical_pack(db, row.org_id)
        total_action_runs = 0

        for workflow in workflows:
            workflow_definition = workflow.definition_json if isinstance(workflow.definition_json, dict) else {}
            now = _now()
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            max_runs_per_day = _as_int(workflow_definition.get("max_runs_per_day", 0), 0)
            if max_runs_per_day > 0:
                runs_today = int(
                    db.scalar(
                        select(func.count(WorkflowRun.id)).where(
                            WorkflowRun.org_id == row.org_id,
                            WorkflowRun.workflow_id == workflow.id,
                            WorkflowRun.created_at >= day_start,
                            WorkflowRun.deleted_at.is_(None),
                        )
                    )
                    or 0
                )
                if runs_today >= max_runs_per_day:
                    run = WorkflowRun(
                        org_id=row.org_id,
                        workflow_id=workflow.id,
                        trigger_event_id=row.id,
                        status=WorkflowRunStatus.SKIPPED,
                        started_at=now,
                        finished_at=now,
                        summary_json={"reason": "max_runs_per_day", "max_runs_per_day": max_runs_per_day},
                        error_json={},
                        loop_guard_hits=0,
                    )
                    db.add(run)
                    db.flush()
                    continue

            cooldown_minutes = _as_int(workflow_definition.get("cooldown_minutes", 0), 0)
            if cooldown_minutes > 0:
                last_run = db.scalar(
                    select(WorkflowRun)
                    .where(
                        WorkflowRun.org_id == row.org_id,
                        WorkflowRun.workflow_id == workflow.id,
                        WorkflowRun.deleted_at.is_(None),
                    )
                    .order_by(WorkflowRun.started_at.desc())
                    .limit(1)
                )
                if last_run is not None and last_run.started_at is not None:
                    if last_run.started_at >= now - timedelta(minutes=cooldown_minutes):
                        run = WorkflowRun(
                            org_id=row.org_id,
                            workflow_id=workflow.id,
                            trigger_event_id=row.id,
                            status=WorkflowRunStatus.SKIPPED,
                            started_at=now,
                            finished_at=now,
                            summary_json={"reason": "cooldown_minutes", "cooldown_minutes": cooldown_minutes},
                            error_json={},
                            loop_guard_hits=0,
                        )
                        db.add(run)
                        db.flush()
                        continue

            run = WorkflowRun(
                org_id=row.org_id,
                workflow_id=workflow.id,
                trigger_event_id=row.id,
                status=WorkflowRunStatus.RUNNING,
                started_at=now,
                summary_json={},
                error_json={},
                loop_guard_hits=0,
            )
            db.add(run)
            db.flush()

            evaluation = evaluate_definition(
                definition_json=workflow.definition_json,
                event_type=row.type,
                channel=row.channel,
                payload_json=row.payload_json if isinstance(row.payload_json, dict) else {},
                risk_tier=0,
                org_settings=settings_payload,
                vertical_pack=vertical_pack,
                local_hour=local_hour,
            )

            if not evaluation.matched:
                run.status = WorkflowRunStatus.SKIPPED
                run.finished_at = _now()
                run.summary_json = {"reason": evaluation.skipped_reason}
                db.flush()
                continue

            created = 0
            queued = 0
            approvals = 0
            succeeded = 0
            for action in evaluation.actions:
                if total_action_runs >= limits["max_actions_per_event"]:
                    run.loop_guard_hits += 1
                    break
                action_run = WorkflowActionRun(
                    org_id=row.org_id,
                    workflow_run_id=run.id,
                    action_type=action.action_type.value,
                    status=WorkflowActionRunStatus.QUEUED,
                    idempotency_key="pending",
                    input_json={"params_json": action.params_json, "risk_tier": action.risk_tier, "depth": current_depth + 1},
                    output_json={},
                    error_json={},
                )
                db.add(action_run)
                db.flush()
                action_run.idempotency_key = action_idempotency_key(row.org_id, action_run)

                requires_approval = action.requires_approval or action.risk_tier > auto_tier
                if requires_approval:
                    action_run.status = WorkflowActionRunStatus.APPROVAL_PENDING
                    requester = _first_member_user_id(db=db, org_id=row.org_id)
                    if requester is not None:
                        db.add(
                            Approval(
                                org_id=row.org_id,
                                entity_type=ApprovalEntityType.WORKFLOW_ACTION_RUN,
                                entity_id=action_run.id,
                                status=ApprovalStatus.PENDING,
                                requested_by=requester,
                                notes="Phase 10 risk-tier approval gate",
                            )
                        )
                    approvals += 1
                else:
                    queued += 1
                    app.send_task("worker.workflow.action.execute", args=[str(action_run.id)])

                created += 1
                total_action_runs += 1

            if created == 0 and run.loop_guard_hits > 0:
                run.status = WorkflowRunStatus.BLOCKED
                run.summary_json = {"reason": "max_actions_per_event", "created_actions": 0}
            elif approvals > 0 and queued == 0:
                run.status = WorkflowRunStatus.APPROVAL_PENDING
                run.summary_json = {"actions_created": created, "approval_pending": approvals}
            else:
                run.status = WorkflowRunStatus.QUEUED
                run.summary_json = {"actions_created": created, "queued": queued, "approval_pending": approvals, "succeeded": succeeded}
            run.finished_at = _now()
            db.flush()

        db.commit()
    return "ok"


@app.task(name="worker.workflow.action.execute", bind=True, max_retries=3, retry_backoff=True)
def workflow_action_execute(self: Celery, action_run_id: str) -> str:
    from app.models import WorkflowActionRun, WorkflowActionRunStatus, WorkflowRun, WorkflowRunStatus

    with SessionLocal() as db:
        action_run = db.scalar(
            select(WorkflowActionRun).where(WorkflowActionRun.id == uuid.UUID(action_run_id), WorkflowActionRun.deleted_at.is_(None))
        )
        if action_run is None:
            return "missing"
        if action_run.status == WorkflowActionRunStatus.SUCCEEDED:
            return "already_succeeded"
        if action_run.status in {WorkflowActionRunStatus.BLOCKED, WorkflowActionRunStatus.SKIPPED, WorkflowActionRunStatus.APPROVAL_PENDING}:
            return "blocked"

        run = db.scalar(
            select(WorkflowRun).where(WorkflowRun.id == action_run.workflow_run_id, WorkflowRun.deleted_at.is_(None))
        )
        if run is None:
            return "missing_run"
        if not _org_is_active(db=db, org_id=action_run.org_id):
            action_run.status = WorkflowActionRunStatus.BLOCKED
            action_run.error_json = {"error": "ORG_NOT_ACTIVE"}
            run.status = WorkflowRunStatus.BLOCKED
            run.error_json = {"error": "ORG_NOT_ACTIVE", "action_run_id": str(action_run.id)}
            run.finished_at = _now()
            db.commit()
            return "org_not_active"

        action_input = action_run.input_json if isinstance(action_run.input_json, dict) else {}
        depth = max(1, _as_int(action_input.get("depth", 1), 1))

        action_run.status = WorkflowActionRunStatus.RUNNING
        db.flush()

        try:
            output = _execute_workflow_action(db=db, action_run_id=action_run.id)
            action_run.output_json = output
            action_run.status = WorkflowActionRunStatus.SUCCEEDED
            _write_system_event(
                db=db,
                org_id=action_run.org_id,
                channel="automations",
                event_type=f"WORKFLOW_ACTION_{action_run.action_type}_SUCCEEDED",
                content_id=run.id,
                payload=_workflow_event_payload({"workflow_run_id": str(run.id), "action_run_id": str(action_run.id)}, run.id, depth),
            )
            _write_system_audit(
                db=db,
                org_id=action_run.org_id,
                action="workflow.action_executed",
                target_type="workflow_action_run",
                target_id=str(action_run.id),
                risk_tier=_risk_tier_enum(_as_int(action_input.get("risk_tier", 1), 1)),
                metadata={"action_type": action_run.action_type},
            )
            siblings = db.scalars(
                select(WorkflowActionRun).where(
                    WorkflowActionRun.workflow_run_id == run.id,
                    WorkflowActionRun.deleted_at.is_(None),
                )
            ).all()
            if siblings and all(item.status == WorkflowActionRunStatus.SUCCEEDED for item in siblings):
                run.status = WorkflowRunStatus.SUCCEEDED
                run.finished_at = _now()
            db.commit()
            return "succeeded"
        except Exception as exc:
            error_message = _sanitize_workflow_error(exc)
            action_run.error_json = {"error": error_message}
            if self.request.retries >= 2:
                action_run.status = WorkflowActionRunStatus.FAILED
                run.status = WorkflowRunStatus.FAILED
                run.error_json = {"error": error_message, "action_run_id": str(action_run.id)}
                run.finished_at = _now()
                _write_system_event(
                    db=db,
                    org_id=action_run.org_id,
                    channel="automations",
                    event_type=f"WORKFLOW_ACTION_{action_run.action_type}_FAILED",
                    content_id=run.id,
                    payload={"workflow_run_id": str(run.id), "action_run_id": str(action_run.id), "error": error_message[:200]},
                )
                db.commit()
                return "failed"
            db.commit()
            raise self.retry(exc=exc)


@app.task(name="worker.workflow.approval.apply")
def workflow_approval_apply(approval_id: str) -> str:
    from app.models import Approval, ApprovalEntityType, ApprovalStatus, WorkflowActionRun, WorkflowActionRunStatus

    with SessionLocal() as db:
        row = db.scalar(select(Approval).where(Approval.id == uuid.UUID(approval_id), Approval.deleted_at.is_(None)))
        if row is None:
            return "missing"
        if row.entity_type != ApprovalEntityType.WORKFLOW_ACTION_RUN:
            return "unsupported_entity"
        action_run = db.scalar(
            select(WorkflowActionRun).where(WorkflowActionRun.id == row.entity_id, WorkflowActionRun.deleted_at.is_(None))
        )
        if action_run is None:
            return "missing_action_run"
        if row.status == ApprovalStatus.APPROVED:
            action_run.status = WorkflowActionRunStatus.QUEUED
            db.commit()
            app.send_task("worker.workflow.action.execute", args=[str(action_run.id)])
            return "queued"
        if row.status == ApprovalStatus.REJECTED:
            action_run.status = WorkflowActionRunStatus.BLOCKED
            db.commit()
            return "rejected"
        return "pending"


















@app.task(name="worker.billing.status_sync_tick")
def billing_status_sync_tick() -> int:
    from app.services.billing import apply_subscription_status_to_org

    updated = 0
    with SessionLocal() as db:
        rows = db.scalars(select(OrgSubscription).where(OrgSubscription.deleted_at.is_(None))).all()
        for row in rows:
            previous = db.scalar(select(Org).where(Org.id == row.org_id, Org.deleted_at.is_(None)))
            before = previous.org_status if previous is not None else None
            after = apply_subscription_status_to_org(db=db, org_id=row.org_id)
            if before is not None and before != after:
                updated += 1
                if after == OrgStatus.SUSPENDED:
                    write_event(
                        db=db,
                        org_id=row.org_id,
                        source="billing",
                        channel="billing",
                        event_type="ORG_SUSPENDED",
                        payload_json={"reason": "subscription_status"},
                    )
        db.commit()
    return updated


@app.task(name="worker.usage.aggregator_tick")
def usage_aggregator_tick() -> int:
    month_start = _now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    metrics = {
        "CONTENT_DRAFT_CREATED": UsageMetricType.POST_CREATED,
        "AI_GENERATION_COMPLETED": UsageMetricType.AI_GENERATION,
        "WORKFLOW_RUN_COMPLETED": UsageMetricType.WORKFLOW_EXECUTED,
        "ADS_METRICS_SYNCED": UsageMetricType.AD_IMPRESSION,
        "MEMBERSHIP_CREATED": UsageMetricType.USER_CREATED,
    }

    updated = 0
    with SessionLocal() as db:
        for event_type, metric_type in metrics.items():
            rows = db.execute(
                select(Event.org_id, func.count(Event.id))
                .where(
                    Event.type == event_type,
                    Event.deleted_at.is_(None),
                    Event.created_at >= month_start,
                )
                .group_by(Event.org_id)
            ).all()
            for org_id, count_raw in rows:
                count = int(count_raw or 0)
                if count <= 0:
                    continue
                row = db.scalar(
                    select(UsageMetric).where(
                        UsageMetric.org_id == org_id,
                        UsageMetric.metric_type == metric_type,
                        UsageMetric.period_start == month_start.date(),
                        UsageMetric.deleted_at.is_(None),
                    )
                )
                if row is None:
                    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                    row = UsageMetric(
                        org_id=org_id,
                        metric_type=metric_type,
                        count=count,
                        period_start=month_start.date(),
                        period_end=month_end.date(),
                    )
                    db.add(row)
                else:
                    row.count = count
                updated += 1
        db.commit()
    return updated
@app.task(name="worker.retention.enforcer_tick")
def retention_enforcer_tick() -> int:
    from app.models import DataRetentionPolicy, Lead

    now = _now()
    soft_deleted = 0
    with SessionLocal() as db:
        policies = db.scalars(
            select(DataRetentionPolicy).where(
                DataRetentionPolicy.deleted_at.is_(None),
                DataRetentionPolicy.entity_type == "lead",
            )
        ).all()
        for policy in policies:
            if policy.retention_days <= 0:
                continue
            cutoff = now - timedelta(days=policy.retention_days)
            leads = db.scalars(
                select(Lead).where(
                    Lead.org_id == policy.org_id,
                    Lead.deleted_at.is_(None),
                    Lead.created_at < cutoff,
                )
            ).all()
            for lead in leads:
                lead.deleted_at = now
                lead.deletion_reason = "retention_policy"
                soft_deleted += 1

            if leads:
                write_event(
                    db=db,
                    org_id=policy.org_id,
                    source="worker",
                    channel="compliance",
                    event_type="DATA_RETENTION_APPLIED",
                    payload_json={"entity_type": "lead", "soft_deleted": len(leads)},
                )
        db.commit()
    return soft_deleted







