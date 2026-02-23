from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from ..models import (
    ContentItem,
    InboxMessage,
    InboxMessageDirection,
    InboxThread,
    InboxThreadStatus,
    Lead,
    LinkClick,
    LinkTracking,
    OrgSettings,
    PresenceAuditRun,
    SEOWorkItem,
)


DEFAULT_AUTOMATION_WEIGHTS: dict[str, int] = {
    "CONTENT_APPROVED_AUTO": 2,
    "CONTENT_SCHEDULED_AUTO": 2,
    "REPLY_SUGGESTED": 3,
    "NURTURE_TASK_CREATED": 2,
    "PRESENCE_AUDIT_RUN": 10,
    "SEO_CONTENT_GENERATED": 8,
    "REVIEW_RESPONSE_DRAFTED": 4,
}


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


@dataclass
class ResponseTimeMetrics:
    avg_minutes: float | None
    within_sla_percent: float
    measured_threads: int


def calculate_first_response_metrics(
    messages: list[InboxMessage],
    response_time_minutes: int,
) -> ResponseTimeMetrics:
    first_inbound_by_thread: dict[uuid.UUID, datetime] = {}
    first_outbound_by_thread: dict[uuid.UUID, datetime] = {}
    for message in sorted(messages, key=lambda item: item.created_at):
        if message.direction == InboxMessageDirection.INBOUND and message.thread_id not in first_inbound_by_thread:
            first_inbound_by_thread[message.thread_id] = _utc(message.created_at)
        if message.direction == InboxMessageDirection.OUTBOUND:
            inbound = first_inbound_by_thread.get(message.thread_id)
            if inbound and message.thread_id not in first_outbound_by_thread and _utc(message.created_at) >= inbound:
                first_outbound_by_thread[message.thread_id] = _utc(message.created_at)

    durations: list[float] = []
    for thread_id, inbound_time in first_inbound_by_thread.items():
        outbound_time = first_outbound_by_thread.get(thread_id)
        if outbound_time is None:
            continue
        durations.append((outbound_time - inbound_time).total_seconds() / 60.0)

    if not durations:
        return ResponseTimeMetrics(avg_minutes=None, within_sla_percent=0.0, measured_threads=0)
    within = sum(1 for minutes in durations if minutes <= response_time_minutes)
    return ResponseTimeMetrics(
        avg_minutes=round(sum(durations) / len(durations), 2),
        within_sla_percent=round((within / len(durations)) * 100.0, 2),
        measured_threads=len(durations),
    )


def calculate_staff_reduction_index(
    action_counts: dict[str, int],
    total_actions: int,
    weights: dict[str, int] | None = None,
) -> dict[str, Any]:
    used_weights = DEFAULT_AUTOMATION_WEIGHTS if weights is None else {**DEFAULT_AUTOMATION_WEIGHTS, **weights}
    breakdown: dict[str, int] = {}
    minutes_saved_total = 0
    automated_actions = 0
    for action_type, count in action_counts.items():
        weight = max(0, int(used_weights.get(action_type, 0)))
        saved = weight * max(0, count)
        breakdown[action_type] = saved
        minutes_saved_total += saved
        automated_actions += max(0, count)

    if total_actions <= 0:
        coverage = 0.0
    else:
        coverage = round(min(1.0, automated_actions / total_actions) * 100.0, 2)

    return {
        "estimated_minutes_saved_total": minutes_saved_total,
        "breakdown_by_action_type": breakdown,
        "automation_coverage_rate": coverage,
    }


def load_org_automation_weights(db: Session, org_id: uuid.UUID) -> dict[str, int]:
    row = db.scalar(select(OrgSettings).where(OrgSettings.org_id == org_id, OrgSettings.deleted_at.is_(None)))
    if row is None:
        return {}
    raw = row.settings_json.get("automation_weights")
    if not isinstance(raw, dict):
        return {}
    parsed: dict[str, int] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, int):
            parsed[key] = value
    return parsed


def click_counts_by_content(
    db: Session,
    org_id: uuid.UUID,
    from_dt: datetime,
    to_dt: datetime,
) -> dict[str, int]:
    rows = db.execute(
        select(LinkTracking.utm_json)
        .join(LinkClick, LinkClick.tracked_link_id == LinkTracking.id)
        .where(
            LinkTracking.org_id == org_id,
            LinkTracking.deleted_at.is_(None),
            LinkClick.org_id == org_id,
            LinkClick.deleted_at.is_(None),
            LinkClick.clicked_at >= from_dt,
            LinkClick.clicked_at <= to_dt,
        )
    ).all()
    result: dict[str, int] = {}
    for (utm_json,) in rows:
        if isinstance(utm_json, dict) and utm_json.get("content_id"):
            key = str(utm_json["content_id"])
            result[key] = result.get(key, 0) + 1
    return result


def leads_by_content_from_clicks(
    db: Session,
    org_id: uuid.UUID,
    from_dt: datetime,
    to_dt: datetime,
) -> dict[str, int]:
    rows = db.execute(
        select(LinkTracking.utm_json, LinkClick.lead_id)
        .join(LinkClick, LinkClick.tracked_link_id == LinkTracking.id)
        .where(
            LinkTracking.org_id == org_id,
            LinkTracking.deleted_at.is_(None),
            LinkClick.org_id == org_id,
            LinkClick.deleted_at.is_(None),
            LinkClick.clicked_at >= from_dt,
            LinkClick.clicked_at <= to_dt,
            LinkClick.lead_id.is_not(None),
        )
    ).all()
    unique_leads_by_content: dict[str, set[str]] = {}
    for utm_json, lead_id in rows:
        if isinstance(utm_json, dict) and utm_json.get("content_id"):
            key = str(utm_json["content_id"])
            unique_leads_by_content.setdefault(key, set()).add(str(lead_id))
    result: dict[str, int] = {}
    for key, lead_ids in unique_leads_by_content.items():
        result[key] = len(lead_ids)
    return result


def get_top_channels(
    db: Session,
    org_id: uuid.UUID,
    from_dt: datetime,
    to_dt: datetime,
) -> list[dict[str, Any]]:
    content_rows = db.execute(
        select(ContentItem.channel, func.count(ContentItem.id))
        .where(
            ContentItem.org_id == org_id,
            ContentItem.deleted_at.is_(None),
            ContentItem.created_at >= from_dt,
            ContentItem.created_at <= to_dt,
        )
        .group_by(ContentItem.channel)
    ).all()
    clicks_rows = db.execute(
        select(LinkTracking.utm_json)
        .join(LinkClick, LinkClick.tracked_link_id == LinkTracking.id)
        .where(
            LinkTracking.org_id == org_id,
            LinkTracking.deleted_at.is_(None),
            LinkClick.org_id == org_id,
            LinkClick.deleted_at.is_(None),
            LinkClick.clicked_at >= from_dt,
            LinkClick.clicked_at <= to_dt,
        )
    ).all()
    leads_rows = db.execute(
        select(Lead.source, func.count(Lead.id))
        .where(
            Lead.org_id == org_id,
            Lead.deleted_at.is_(None),
            Lead.created_at >= from_dt,
            Lead.created_at <= to_dt,
        )
        .group_by(Lead.source)
    ).all()

    merged: dict[str, dict[str, Any]] = defaultdict(lambda: {"channel": "", "content_items": 0, "clicks": 0, "leads": 0})
    for channel, count in content_rows:
        channel_key = str(channel)
        merged[channel_key]["channel"] = channel_key
        merged[channel_key]["content_items"] = int(count)
    for (utm_json,) in clicks_rows:
        if isinstance(utm_json, dict):
            channel_key = str(utm_json.get("channel") or "unknown")
            merged[channel_key]["channel"] = channel_key
            merged[channel_key]["clicks"] += 1
    for source, count in leads_rows:
        channel_key = str(source)
        merged[channel_key]["channel"] = channel_key
        merged[channel_key]["leads"] += int(count)

    return sorted(merged.values(), key=lambda item: (item["clicks"], item["leads"], item["content_items"]), reverse=True)[:5]


def workload_action_counts(db: Session, org_id: uuid.UUID, from_dt: datetime, to_dt: datetime) -> tuple[dict[str, int], int]:
    action_query = (
        select(func.count())
        .select_from(SEOWorkItem)
        .where(
            SEOWorkItem.org_id == org_id,
            SEOWorkItem.deleted_at.is_(None),
            SEOWorkItem.created_at >= from_dt,
            SEOWorkItem.created_at <= to_dt,
        )
    )
    seo_work_total = int(db.scalar(action_query) or 0)

    from ..models import Event

    rows = db.execute(
        select(Event.type, func.count(Event.id))
        .where(
            Event.org_id == org_id,
            Event.deleted_at.is_(None),
            Event.created_at >= from_dt,
            Event.created_at <= to_dt,
            Event.type.in_(
                [
                    "CONTENT_APPROVED_AUTO",
                    "CONTENT_SCHEDULED_AUTO",
                    "REPLY_SUGGESTED",
                    "NURTURE_TASK_CREATED",
                    "PRESENCE_AUDIT_RUN",
                    "SEO_CONTENT_GENERATED",
                    "REVIEW_RESPONSE_DRAFTED",
                    "CONTENT_APPROVAL_DECIDED",
                    "PUBLISH_ATTEMPT",
                    "OUTBOUND_DRAFT_CREATED",
                    "SEO_WORKITEM_CREATED",
                    "REVIEW_IMPORTED",
                ]
            ),
        )
        .group_by(Event.type)
    ).all()
    counts = {str(event_type): int(count) for event_type, count in rows}
    automated = {
        "CONTENT_APPROVED_AUTO": counts.get("CONTENT_APPROVED_AUTO", 0),
        "CONTENT_SCHEDULED_AUTO": counts.get("CONTENT_SCHEDULED_AUTO", 0),
        "REPLY_SUGGESTED": counts.get("REPLY_SUGGESTED", 0),
        "NURTURE_TASK_CREATED": counts.get("NURTURE_TASK_CREATED", 0),
        "PRESENCE_AUDIT_RUN": counts.get("PRESENCE_AUDIT_RUN", 0),
        "SEO_CONTENT_GENERATED": counts.get("SEO_CONTENT_GENERATED", 0),
        "REVIEW_RESPONSE_DRAFTED": counts.get("REVIEW_RESPONSE_DRAFTED", 0),
    }
    manual = (
        counts.get("CONTENT_APPROVAL_DECIDED", 0)
        + counts.get("PUBLISH_ATTEMPT", 0)
        + counts.get("OUTBOUND_DRAFT_CREATED", 0)
        + counts.get("SEO_WORKITEM_CREATED", 0)
        + counts.get("REVIEW_IMPORTED", 0)
        + seo_work_total
    )
    total_actions = sum(automated.values()) + manual
    return automated, total_actions


def open_overdue_threads_count(
    db: Session,
    org_id: uuid.UUID,
    response_time_minutes: int,
) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=response_time_minutes)
    latest_inbound = (
        select(
            InboxMessage.thread_id.label("thread_id"),
            func.max(InboxMessage.created_at).label("inbound_at"),
        )
        .where(
            InboxMessage.org_id == org_id,
            InboxMessage.deleted_at.is_(None),
            InboxMessage.direction == InboxMessageDirection.INBOUND,
        )
        .group_by(InboxMessage.thread_id)
        .subquery()
    )
    latest_outbound = (
        select(
            InboxMessage.thread_id.label("thread_id"),
            func.max(InboxMessage.created_at).label("outbound_at"),
        )
        .where(
            InboxMessage.org_id == org_id,
            InboxMessage.deleted_at.is_(None),
            InboxMessage.direction == InboxMessageDirection.OUTBOUND,
        )
        .group_by(InboxMessage.thread_id)
        .subquery()
    )
    rows = db.execute(
        select(func.count(InboxThread.id))
        .select_from(InboxThread)
        .join(latest_inbound, latest_inbound.c.thread_id == InboxThread.id)
        .outerjoin(latest_outbound, latest_outbound.c.thread_id == InboxThread.id)
        .where(
            InboxThread.org_id == org_id,
            InboxThread.deleted_at.is_(None),
            InboxThread.status != InboxThreadStatus.CLOSED,
            latest_inbound.c.inbound_at <= cutoff,
            and_(
                latest_outbound.c.outbound_at.is_(None),
                latest_inbound.c.inbound_at.is_not(None),
            )
            | (latest_outbound.c.outbound_at < latest_inbound.c.inbound_at),
        )
    ).one()
    return int(rows[0] or 0)


def latest_presence_score(db: Session, org_id: uuid.UUID) -> int | None:
    latest = db.scalar(
        select(PresenceAuditRun)
        .where(PresenceAuditRun.org_id == org_id, PresenceAuditRun.deleted_at.is_(None))
        .order_by(desc(PresenceAuditRun.created_at))
        .limit(1)
    )
    if latest is None:
        return None
    score = latest.summary_scores_json.get("overall_score")
    return int(score) if isinstance(score, (int, float)) else None
