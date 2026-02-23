from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    CampaignPlan,
    ContentItem,
    Event,
    InboxMessage,
    InboxMessageDirection,
    Lead,
    LeadAssignment,
    LeadScore,
    LeadStatus,
    PresenceAuditRun,
    PresenceFinding,
    PresenceFindingStatus,
    PublishJob,
    PublishJobStatus,
    SLAConfig,
)
from ..schemas import (
    AnalyticsContentResponse,
    AnalyticsFunnelResponse,
    AnalyticsOverviewResponse,
    AnalyticsPresenceResponse,
    AnalyticsSLAResponse,
    AnalyticsWorkloadResponse,
)
from ..services.analytics import (
    calculate_first_response_metrics,
    calculate_staff_reduction_index,
    click_counts_by_content,
    get_top_channels,
    latest_presence_score,
    leads_by_content_from_clicks,
    load_org_automation_weights,
    open_overdue_threads_count,
    workload_action_counts,
)
from ..tenancy import RequestContext, get_request_context

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _range(from_dt: datetime | None, to_dt: datetime | None) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    end = now if to_dt is None else (to_dt if to_dt.tzinfo else to_dt.replace(tzinfo=UTC))
    start = end - timedelta(days=30) if from_dt is None else (from_dt if from_dt.tzinfo else from_dt.replace(tzinfo=UTC))
    return start, end


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def analytics_overview(
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AnalyticsOverviewResponse:
    start, end = _range(from_dt, to_dt)
    org_id = context.current_org_id
    totals = {
        "campaigns_created": int(
            db.scalar(
                select(func.count(CampaignPlan.id)).where(
                    CampaignPlan.org_id == org_id,
                    CampaignPlan.deleted_at.is_(None),
                    CampaignPlan.created_at >= start,
                    CampaignPlan.created_at <= end,
                )
            )
            or 0
        ),
        "content_items_created": int(
            db.scalar(
                select(func.count(ContentItem.id)).where(
                    ContentItem.org_id == org_id,
                    ContentItem.deleted_at.is_(None),
                    ContentItem.created_at >= start,
                    ContentItem.created_at <= end,
                )
            )
            or 0
        ),
        "publish_succeeded": int(
            db.scalar(
                select(func.count(PublishJob.id)).where(
                    PublishJob.org_id == org_id,
                    PublishJob.deleted_at.is_(None),
                    PublishJob.status == PublishJobStatus.SUCCEEDED,
                    PublishJob.created_at >= start,
                    PublishJob.created_at <= end,
                )
            )
            or 0
        ),
        "publish_failed": int(
            db.scalar(
                select(func.count(PublishJob.id)).where(
                    PublishJob.org_id == org_id,
                    PublishJob.deleted_at.is_(None),
                    PublishJob.status == PublishJobStatus.FAILED,
                    PublishJob.created_at >= start,
                    PublishJob.created_at <= end,
                )
            )
            or 0
        ),
        "inbox_inbound_count": int(
            db.scalar(
                select(func.count(InboxMessage.id)).where(
                    InboxMessage.org_id == org_id,
                    InboxMessage.deleted_at.is_(None),
                    InboxMessage.direction == InboxMessageDirection.INBOUND,
                    InboxMessage.created_at >= start,
                    InboxMessage.created_at <= end,
                )
            )
            or 0
        ),
        "leads_created": int(
            db.scalar(
                select(func.count(Lead.id)).where(
                    Lead.org_id == org_id,
                    Lead.deleted_at.is_(None),
                    Lead.created_at >= start,
                    Lead.created_at <= end,
                )
            )
            or 0
        ),
        "leads_qualified": int(
            db.scalar(
                select(func.count(Lead.id)).where(
                    Lead.org_id == org_id,
                    Lead.deleted_at.is_(None),
                    Lead.status == LeadStatus.QUALIFIED,
                    Lead.created_at >= start,
                    Lead.created_at <= end,
                )
            )
            or 0
        ),
        "leads_assigned": int(
            db.scalar(
                select(func.count(LeadAssignment.id)).where(
                    LeadAssignment.org_id == org_id,
                    LeadAssignment.deleted_at.is_(None),
                    LeadAssignment.created_at >= start,
                    LeadAssignment.created_at <= end,
                )
            )
            or 0
        ),
    }
    response_metric = calculate_first_response_metrics(
        list(
            db.scalars(
            select(InboxMessage).where(
                InboxMessage.org_id == org_id,
                InboxMessage.deleted_at.is_(None),
                InboxMessage.created_at >= start,
                InboxMessage.created_at <= end,
            )
            ).all()
        ),
        response_time_minutes=int(
            db.scalar(
                select(SLAConfig.response_time_minutes).where(SLAConfig.org_id == org_id, SLAConfig.deleted_at.is_(None))
            )
            or 30
        ),
    )
    action_counts, total_actions = workload_action_counts(db, org_id, start, end)
    weights = load_org_automation_weights(db, org_id)
    staff_index = calculate_staff_reduction_index(action_counts, total_actions, weights=weights)
    return AnalyticsOverviewResponse(
        totals=totals,
        avg_response_time_minutes=response_metric.avg_minutes,
        presence_overall_score_latest=latest_presence_score(db, org_id),
        staff_reduction_index=staff_index,
        top_channels=get_top_channels(db, org_id, start, end),
    )


@router.get("/content", response_model=AnalyticsContentResponse)
def analytics_content(
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    group_by: str = Query(default="day", pattern="^(day|week)$"),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AnalyticsContentResponse:
    start, end = _range(from_dt, to_dt)
    org_id = context.current_org_id
    status_rows = db.execute(
        select(ContentItem.status, func.count(ContentItem.id))
        .where(
            ContentItem.org_id == org_id,
            ContentItem.deleted_at.is_(None),
            ContentItem.created_at >= start,
            ContentItem.created_at <= end,
        )
        .group_by(ContentItem.status)
    ).all()
    content_items_by_status = {str(status.value if hasattr(status, "value") else status): int(count) for status, count in status_rows}
    success = int(
        db.scalar(
            select(func.count(PublishJob.id)).where(
                PublishJob.org_id == org_id,
                PublishJob.deleted_at.is_(None),
                PublishJob.status == PublishJobStatus.SUCCEEDED,
                PublishJob.created_at >= start,
                PublishJob.created_at <= end,
            )
        )
        or 0
    )
    failed = int(
        db.scalar(
            select(func.count(PublishJob.id)).where(
                PublishJob.org_id == org_id,
                PublishJob.deleted_at.is_(None),
                PublishJob.status == PublishJobStatus.FAILED,
                PublishJob.created_at >= start,
                PublishJob.created_at <= end,
            )
        )
        or 0
    )
    total_publish = success + failed
    success_rate = round((success / total_publish) * 100.0, 2) if total_publish else 0.0
    clicks = click_counts_by_content(db, org_id, start, end)
    leads = leads_by_content_from_clicks(db, org_id, start, end)
    return AnalyticsContentResponse(
        group_by=group_by,
        content_items_by_status=content_items_by_status,
        publish_success_rate=success_rate,
        clicks_by_content=[{"content_id": key, "clicks": value} for key, value in sorted(clicks.items())],
        leads_by_content=[{"content_id": key, "leads": value} for key, value in sorted(leads.items())],
    )


@router.get("/funnel", response_model=AnalyticsFunnelResponse)
def analytics_funnel(
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AnalyticsFunnelResponse:
    start, end = _range(from_dt, to_dt)
    org_id = context.current_org_id
    inbound = int(
        db.scalar(
            select(func.count(InboxMessage.id)).where(
                InboxMessage.org_id == org_id,
                InboxMessage.deleted_at.is_(None),
                InboxMessage.direction == InboxMessageDirection.INBOUND,
                InboxMessage.created_at >= start,
                InboxMessage.created_at <= end,
            )
        )
        or 0
    )
    leads_created = int(
        db.scalar(
            select(func.count(Lead.id)).where(
                Lead.org_id == org_id,
                Lead.deleted_at.is_(None),
                Lead.created_at >= start,
                Lead.created_at <= end,
            )
        )
        or 0
    )
    leads_scored = int(
        db.scalar(
            select(func.count(LeadScore.id)).where(
                LeadScore.org_id == org_id,
                LeadScore.deleted_at.is_(None),
                LeadScore.created_at >= start,
                LeadScore.created_at <= end,
            )
        )
        or 0
    )
    leads_assigned = int(
        db.scalar(
            select(func.count(LeadAssignment.id)).where(
                LeadAssignment.org_id == org_id,
                LeadAssignment.deleted_at.is_(None),
                LeadAssignment.created_at >= start,
                LeadAssignment.created_at <= end,
            )
        )
        or 0
    )
    qualified = int(
        db.scalar(
            select(func.count(Lead.id)).where(
                Lead.org_id == org_id,
                Lead.deleted_at.is_(None),
                Lead.status == LeadStatus.QUALIFIED,
                Lead.updated_at >= start,
                Lead.updated_at <= end,
            )
        )
        or 0
    )
    outcome = int(
        db.scalar(
            select(func.count(Lead.id)).where(
                Lead.org_id == org_id,
                Lead.deleted_at.is_(None),
                Lead.status == LeadStatus.ARCHIVED,
                Lead.updated_at >= start,
                Lead.updated_at <= end,
            )
        )
        or 0
    )
    stages = {
        "inbox_inbound": inbound,
        "leads_created": leads_created,
        "leads_scored": leads_scored,
        "leads_assigned": leads_assigned,
        "qualified": qualified,
        "outcome": outcome,
    }
    conversion_rates = {
        "inbound_to_lead": round((leads_created / inbound) * 100.0, 2) if inbound else 0.0,
        "lead_to_scored": round((leads_scored / leads_created) * 100.0, 2) if leads_created else 0.0,
        "scored_to_assigned": round((leads_assigned / leads_scored) * 100.0, 2) if leads_scored else 0.0,
        "assigned_to_qualified": round((qualified / leads_assigned) * 100.0, 2) if leads_assigned else 0.0,
        "qualified_to_outcome": round((outcome / qualified) * 100.0, 2) if qualified else 0.0,
    }
    return AnalyticsFunnelResponse(stages=stages, conversion_rates=conversion_rates)


@router.get("/sla", response_model=AnalyticsSLAResponse)
def analytics_sla(
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AnalyticsSLAResponse:
    start, end = _range(from_dt, to_dt)
    org_id = context.current_org_id
    response_time_minutes = int(
        db.scalar(select(SLAConfig.response_time_minutes).where(SLAConfig.org_id == org_id, SLAConfig.deleted_at.is_(None)))
        or 30
    )
    metrics = calculate_first_response_metrics(
        list(
            db.scalars(
            select(InboxMessage).where(
                InboxMessage.org_id == org_id,
                InboxMessage.deleted_at.is_(None),
                InboxMessage.created_at >= start,
                InboxMessage.created_at <= end,
            )
            ).all()
        ),
        response_time_minutes=response_time_minutes,
    )
    escalations = int(
        db.scalar(
            select(func.count(Event.id)).where(
                Event.org_id == org_id,
                Event.deleted_at.is_(None),
                Event.type == "SLA_ESCALATED",
                Event.created_at >= start,
                Event.created_at <= end,
            )
        )
        or 0
    )
    return AnalyticsSLAResponse(
        avg_first_response_time_minutes=metrics.avg_minutes,
        within_sla_percent=metrics.within_sla_percent,
        escalations_triggered=escalations,
        overdue_threads_count=open_overdue_threads_count(db, org_id, response_time_minutes),
    )


@router.get("/presence", response_model=AnalyticsPresenceResponse)
def analytics_presence(
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    group_by: str = Query(default="week", pattern="^(day|week)$"),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AnalyticsPresenceResponse:
    start, end = _range(from_dt, to_dt)
    org_id = context.current_org_id
    runs = db.scalars(
        select(PresenceAuditRun)
        .where(
            PresenceAuditRun.org_id == org_id,
            PresenceAuditRun.deleted_at.is_(None),
            PresenceAuditRun.created_at >= start,
            PresenceAuditRun.created_at <= end,
        )
        .order_by(PresenceAuditRun.created_at)
    ).all()
    trend: list[dict[str, object]] = []
    for run in runs:
        bucket = run.created_at.date().isoformat()
        if group_by == "week":
            iso = run.created_at.isocalendar()
            bucket = f"{iso.year}-W{iso.week:02d}"
        overall_raw = run.summary_scores_json.get("overall_score", 0)
        overall_score = int(overall_raw) if isinstance(overall_raw, (int, float)) else 0
        trend.append(
            {
                "bucket": bucket,
                "overall_score": overall_score,
                "category_scores": run.summary_scores_json.get("category_scores", {}),
            }
        )
    open_findings = int(
        db.scalar(
            select(func.count(PresenceFinding.id)).where(
                PresenceFinding.org_id == org_id,
                PresenceFinding.deleted_at.is_(None),
                PresenceFinding.status.in_([PresenceFindingStatus.OPEN, PresenceFindingStatus.IN_PROGRESS]),
            )
        )
        or 0
    )
    return AnalyticsPresenceResponse(
        group_by=group_by,
        audit_runs_count=len(runs),
        score_trend=trend,
        open_findings_count=open_findings,
    )


@router.get("/workload", response_model=AnalyticsWorkloadResponse)
def analytics_workload(
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AnalyticsWorkloadResponse:
    start, end = _range(from_dt, to_dt)
    action_counts, total_actions = workload_action_counts(db, context.current_org_id, start, end)
    weights = load_org_automation_weights(db, context.current_org_id)
    result = calculate_staff_reduction_index(action_counts, total_actions, weights=weights)
    return AnalyticsWorkloadResponse(**result)
