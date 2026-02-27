from __future__ import annotations

import uuid
from datetime import UTC, datetime


from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from packages.optimization.engine import (
    build_ad_budget_recommendation,
    build_next_best_action,
    build_nurture_recommendation,
    combine_lead_score,
    compute_posting_optimization,
    compute_predictive_score,
    detect_model_drift,
    extract_features,
    workflow_recommendations,
)

from ..db import get_db
from ..models import (
    AdBudgetRecommendation,
    AdCampaign,
    AdSpendLedger,
    Event,
    Lead,
    LeadScore,
    ModelMetadata,
    ModelStatus,
    OrgOptimizationSettings,
    PostingOptimization,
    PredictiveLeadScore,
    Role,
    WorkflowActionRun,
    WorkflowRun,
)
from ..schemas import (
    AdBudgetRecommendationResponse,
    ModelActivateRequest,
    ModelMetadataResponse,
    NextBestActionResponse,
    NurtureRecommendationResponse,
    OrgOptimizationSettingsPatchRequest,
    OrgOptimizationSettingsResponse,
    PostingOptimizationResponse,
    PredictiveLeadScoreResponse,
    WorkflowOptimizationSuggestion,
)
from ..services.audit import write_audit_log
from ..services.billing import ensure_org_active
from ..services.events import write_event
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/optimization", tags=["optimization"])


def _get_optimization_settings(db: Session, org_id: uuid.UUID) -> OrgOptimizationSettings:
    row = db.scalar(
        org_scoped(
            select(OrgOptimizationSettings).where(OrgOptimizationSettings.deleted_at.is_(None)),
            org_id,
            OrgOptimizationSettings,
        )
    )
    if row is None:
        row = OrgOptimizationSettings(org_id=org_id)
        db.add(row)
        db.flush()
    return row


def _serialize_settings(row: OrgOptimizationSettings) -> OrgOptimizationSettingsResponse:
    return OrgOptimizationSettingsResponse(
        enable_predictive_scoring=row.enable_predictive_scoring,
        enable_post_timing_optimization=row.enable_post_timing_optimization,
        enable_nurture_optimization=row.enable_nurture_optimization,
        enable_ad_budget_recommendations=row.enable_ad_budget_recommendations,
        auto_apply_low_risk_optimizations=row.auto_apply_low_risk_optimizations,
    )


def _as_float_map(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, float] = {}
    for key, raw in value.items():
        if isinstance(key, str) and isinstance(raw, (int, float)) and not isinstance(raw, bool):
            out[key] = float(raw)
    return out


def _as_scalar_map(value: object) -> dict[str, float | str]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, float | str] = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(raw, bool):
            out[key] = str(raw).lower()
        elif isinstance(raw, (int, float)):
            out[key] = float(raw)
        elif isinstance(raw, str):
            out[key] = raw
    return out


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _serialize_predictive_score(
    row: PredictiveLeadScore,
    *,
    explanation: str,
    final_score: int,
) -> PredictiveLeadScoreResponse:
    return PredictiveLeadScoreResponse(
        id=row.id,
        org_id=row.org_id,
        lead_id=row.lead_id,
        model_version=row.model_version,
        score_probability=row.score_probability,
        feature_importance_json=_as_float_map(row.feature_importance_json),
        predicted_stage_probability_json=_as_float_map(row.predicted_stage_probability_json),
        explanation=explanation,
        final_score=final_score,
        scored_at=row.scored_at,
    )


def _model_rows(db: Session, org_id: uuid.UUID, model_name: str | None = None) -> list[ModelMetadata]:
    stmt = org_scoped(
        select(ModelMetadata).where(ModelMetadata.deleted_at.is_(None)),
        org_id,
        ModelMetadata,
    )
    if model_name:
        stmt = stmt.where(ModelMetadata.name == model_name)
    stmt = stmt.order_by(desc(ModelMetadata.created_at))
    return list(db.scalars(stmt).all())


@router.get("/settings", response_model=OrgOptimizationSettingsResponse)
def get_optimization_settings(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> OrgOptimizationSettingsResponse:
    require_role(context, Role.ADMIN)
    row = _get_optimization_settings(db=db, org_id=context.current_org_id)
    return _serialize_settings(row)


@router.patch("/settings", response_model=OrgOptimizationSettingsResponse)
def patch_optimization_settings(
    payload: OrgOptimizationSettingsPatchRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> OrgOptimizationSettingsResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)
    row = _get_optimization_settings(db=db, org_id=context.current_org_id)
    updates = payload.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(row, key, value)
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="optimization.settings_updated",
        target_type="org_optimization_settings",
        target_id=str(row.id),
        metadata_json={"updated": sorted(updates.keys())},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="optimization",
        channel="optimization",
        event_type="OPTIMIZATION_SETTINGS_UPDATED",
        payload_json={"updated": sorted(updates.keys())},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(row)
    return _serialize_settings(row)


@router.post("/lead-score/{lead_id}", response_model=PredictiveLeadScoreResponse)
def score_predictive_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> PredictiveLeadScoreResponse:
    require_role(context, Role.AGENT)
    ensure_org_active(db=db, org_id=context.current_org_id)

    lead = db.scalar(
        org_scoped(
            select(Lead).where(Lead.id == lead_id, Lead.deleted_at.is_(None)),
            context.current_org_id,
            Lead,
        )
    )
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lead not found")

    samples = db.scalars(
        org_scoped(
            select(Event)
            .where(Event.lead_id == str(lead_id), Event.deleted_at.is_(None))
            .order_by(desc(Event.created_at))
            .limit(200),
            context.current_org_id,
            Event,
        )
    ).all()
    payloads: list[dict[str, object]] = []
    for row in samples:
        payload = dict(row.payload_json)
        payload.setdefault("event_type", row.type)
        payloads.append(payload)

    vector = extract_features(org_id=str(context.current_org_id), lead_id=str(lead_id), payloads=payloads)
    inferred = compute_predictive_score(vector)
    rule_score = db.scalar(
        org_scoped(
            select(LeadScore.score_total)
            .where(LeadScore.lead_id == lead_id, LeadScore.deleted_at.is_(None))
            .order_by(desc(LeadScore.scored_at))
            .limit(1),
            context.current_org_id,
            LeadScore,
        )
    )
    final_score = combine_lead_score(rule_score=int(rule_score or 0), predictive_score=inferred.score_probability)

    row = db.scalar(
        org_scoped(
            select(PredictiveLeadScore).where(
                PredictiveLeadScore.lead_id == lead_id,
                PredictiveLeadScore.model_version == "lead_score_model_v1",
                PredictiveLeadScore.deleted_at.is_(None),
            ),
            context.current_org_id,
            PredictiveLeadScore,
        )
    )
    if row is None:
        row = PredictiveLeadScore(
            org_id=context.current_org_id,
            lead_id=lead_id,
            model_version="lead_score_model_v1",
            score_probability=inferred.score_probability,
            feature_importance_json=inferred.feature_importance_json,
            predicted_stage_probability_json=inferred.predicted_stage_probability_json,
            scored_at=datetime.now(UTC),
        )
        db.add(row)
    else:
        row.score_probability = inferred.score_probability
        row.feature_importance_json = inferred.feature_importance_json
        row.predicted_stage_probability_json = inferred.predicted_stage_probability_json
        row.scored_at = datetime.now(UTC)

    db.flush()
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="optimization",
        channel="lead",
        event_type="LEAD_PREDICTIVE_SCORED",
        lead_id=str(lead_id),
        payload_json={
            "model_version": row.model_version,
            "score_probability": row.score_probability,
            "final_score": final_score,
        },
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="optimization.lead_scored",
        target_type="lead",
        target_id=str(lead_id),
        metadata_json={"model_version": row.model_version, "final_score": final_score},
    )
    db.commit()
    db.refresh(row)
    return _serialize_predictive_score(row, explanation=inferred.explanation, final_score=final_score)


@router.get("/campaigns", response_model=list[PostingOptimizationResponse])
def get_post_timing_optimizations(
    channel: str = Query(default="meta", min_length=1, max_length=80),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[PostingOptimizationResponse]:
    require_role(context, Role.AGENT)
    samples: list[dict[str, object]] = []
    rows = db.scalars(
        org_scoped(
            select(Event)
            .where(Event.type.in_(["PUBLISH_SUCCEEDED", "LINK_CLICKED"]), Event.deleted_at.is_(None))
            .order_by(desc(Event.created_at))
            .limit(500),
            context.current_org_id,
            Event,
        )
    ).all()
    for row in rows:
        event_hour = row.created_at.hour if row.created_at else 10
        event_day = row.created_at.weekday() if row.created_at else 2
        conversion_rate = float(row.payload_json.get("conversion_rate") or 0.05)
        samples.append({"day_of_week": event_day, "hour": event_hour, "conversion_rate": conversion_rate})

    result = compute_posting_optimization(channel=channel, samples=samples)
    persisted = db.scalar(
        org_scoped(
            select(PostingOptimization).where(
                PostingOptimization.channel == channel,
                PostingOptimization.deleted_at.is_(None),
            ),
            context.current_org_id,
            PostingOptimization,
        )
    )
    if persisted is None:
        persisted = PostingOptimization(org_id=context.current_org_id, channel=channel)
        db.add(persisted)
    persisted.best_day_of_week = result.best_day_of_week
    persisted.best_hour = result.best_hour
    persisted.confidence_score = result.confidence_score
    persisted.model_version = "post_timing_model_v1"
    db.flush()
    db.commit()
    db.refresh(persisted)
    return [
        PostingOptimizationResponse(
            id=persisted.id,
            org_id=persisted.org_id,
            channel=persisted.channel,
            best_day_of_week=persisted.best_day_of_week,
            best_hour=persisted.best_hour,
            confidence_score=persisted.confidence_score,
            model_version=persisted.model_version,
            explanation=result.explanation,
            updated_at=persisted.updated_at,
        )
    ]


@router.get("/nurture/recommendations", response_model=NurtureRecommendationResponse)
def get_nurture_recommendations(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> NurtureRecommendationResponse:
    require_role(context, Role.AGENT)
    rows = db.scalars(
        org_scoped(
            select(Event)
            .where(Event.type.in_(["NURTURE_TASK_CREATED", "LEAD_STATUS_CHANGED"]), Event.deleted_at.is_(None))
            .order_by(desc(Event.created_at))
            .limit(250),
            context.current_org_id,
            Event,
        )
    ).all()
    intervals = [int(row.payload_json.get("delay_minutes", 120)) for row in rows if isinstance(row.payload_json.get("delay_minutes"), (int, float))]
    progressed = [row for row in rows if row.type == "LEAD_STATUS_CHANGED"]
    progress_rate = min(1.0, len(progressed) / max(1, len(rows)))
    recommendation = build_nurture_recommendation(
        touch_intervals_minutes=intervals,
        stage_progress_rate=progress_rate,
    )
    return NurtureRecommendationResponse(
        recommended_delays_minutes=recommendation.recommended_delays_minutes,
        explanation=recommendation.explanation,
    )


@router.get("/ads", response_model=list[AdBudgetRecommendationResponse])
def get_ad_budget_recommendations(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[AdBudgetRecommendationResponse]:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)

    campaigns = db.scalars(
        org_scoped(
            select(AdCampaign)
            .where(AdCampaign.deleted_at.is_(None))
            .order_by(desc(AdCampaign.updated_at))
            .limit(limit),
            context.current_org_id,
            AdCampaign,
        )
    ).all()
    responses: list[AdBudgetRecommendationResponse] = []
    for campaign in campaigns:
        metrics = db.scalars(
            org_scoped(
                select(AdSpendLedger)
                .where(
                    AdSpendLedger.campaign_id == campaign.id,
                    AdSpendLedger.deleted_at.is_(None),
                )
                .order_by(desc(AdSpendLedger.day))
                .limit(30),
                context.current_org_id,
                AdSpendLedger,
            )
        ).all()
        spend_total = float(sum(row.spend_usd for row in metrics))
        clicks_total = int(sum(int(row.clicks or 0) for row in metrics))
        cpl = spend_total / max(1, clicks_total)
        recommendation = build_ad_budget_recommendation(
            current_daily_budget=float(campaign.daily_budget_usd),
            cpl=cpl,
            benchmark_cpl=max(1.0, cpl * 0.9),
            campaign_cap=max(float(campaign.daily_budget_usd), 500.0),
        )
        row = AdBudgetRecommendation(
            org_id=context.current_org_id,
            campaign_id=campaign.id,
            recommended_daily_budget=recommendation.recommended_daily_budget,
            reasoning_json=recommendation.reasoning_json,
            projected_cpl=recommendation.projected_cpl,
            model_version="ad_budget_allocator_v1",
        )
        db.add(row)
        db.flush()
        responses.append(
            AdBudgetRecommendationResponse(
                id=row.id,
                org_id=row.org_id,
                campaign_id=row.campaign_id,
                recommended_daily_budget=row.recommended_daily_budget,
                reasoning_json=_as_scalar_map(row.reasoning_json),
                projected_cpl=row.projected_cpl,
                model_version=row.model_version,
                explanation=recommendation.explanation,
                created_at=row.created_at,
            )
        )
        write_event(
            db=db,
            org_id=context.current_org_id,
            source="optimization",
            channel="ads",
            event_type="AD_BUDGET_RECOMMENDATION_GENERATED",
            payload_json={
                "campaign_id": str(campaign.id),
                "recommended_daily_budget": recommendation.recommended_daily_budget,
            },
            actor_id=str(context.current_user_id),
        )
    db.commit()
    return responses


@router.get("/workflows", response_model=list[WorkflowOptimizationSuggestion])
def get_workflow_optimization_recommendations(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[WorkflowOptimizationSuggestion]:
    require_role(context, Role.ADMIN)
    runs = db.scalars(
        org_scoped(
            select(WorkflowRun)
            .where(WorkflowRun.deleted_at.is_(None))
            .order_by(desc(WorkflowRun.created_at))
            .limit(100),
            context.current_org_id,
            WorkflowRun,
        )
    ).all()
    failures_by_workflow: dict[uuid.UUID, int] = {}
    totals_by_workflow: dict[uuid.UUID, int] = {}
    for run in runs:
        totals_by_workflow[run.workflow_id] = totals_by_workflow.get(run.workflow_id, 0) + 1
        if run.status in {"failed", "blocked"}:
            failures_by_workflow[run.workflow_id] = failures_by_workflow.get(run.workflow_id, 0) + 1

    action_rows = db.scalars(
        org_scoped(
            select(WorkflowActionRun)
            .where(WorkflowActionRun.deleted_at.is_(None))
            .order_by(desc(WorkflowActionRun.created_at))
            .limit(200),
            context.current_org_id,
            WorkflowActionRun,
        )
    ).all()
    approval_pending = sum(1 for row in action_rows if row.status == "approval_pending")

    payload: list[dict[str, object]] = []
    for workflow_id, total in totals_by_workflow.items():
        failed = failures_by_workflow.get(workflow_id, 0)
        success_rate = (total - failed) / max(1, total)
        payload.append(
            {
                "workflow_key": str(workflow_id),
                "success_rate": success_rate,
                "approval_latency_minutes": 180 if approval_pending else 30,
            }
        )
    suggestions = workflow_recommendations(workflow_stats=payload)
    return [WorkflowOptimizationSuggestion.model_validate(item) for item in suggestions]


@router.get("/next-best-action/{entity_type}/{entity_id}", response_model=NextBestActionResponse)
def get_next_best_action(
    entity_type: str,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> NextBestActionResponse:
    require_role(context, Role.AGENT)
    inactivity_hours = 24.0
    predictive_score = 0.5
    stage: str | None = None

    if entity_type == "lead":
        lead = db.scalar(
            org_scoped(
                select(Lead).where(Lead.id == entity_id, Lead.deleted_at.is_(None)),
                context.current_org_id,
                Lead,
            )
        )
        if lead is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lead not found")
        stage = lead.status.value
        if lead.updated_at:
            inactivity_hours = max(0.0, (datetime.now(UTC) - lead.updated_at).total_seconds() / 3600.0)
        predictive = db.scalar(
            org_scoped(
                select(PredictiveLeadScore)
                .where(PredictiveLeadScore.lead_id == entity_id, PredictiveLeadScore.deleted_at.is_(None))
                .order_by(desc(PredictiveLeadScore.scored_at))
                .limit(1),
                context.current_org_id,
                PredictiveLeadScore,
            )
        )
        if predictive is not None:
            predictive_score = float(predictive.score_probability)

    result = build_next_best_action(
        entity_type=entity_type,
        inactivity_hours=inactivity_hours,
        predictive_score=predictive_score,
        stage=stage,
    )
    return NextBestActionResponse.model_validate(result.model_dump())


@router.get("/models", response_model=list[ModelMetadataResponse])
def list_models(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[ModelMetadataResponse]:
    require_role(context, Role.ADMIN)
    rows = _model_rows(db=db, org_id=context.current_org_id)

    if not rows:
        seeds = [
            ("lead_score_model", "v1", {"auc": 0.72, "precision": 0.68, "recall": 0.63}),
            ("post_timing_model", "v1", {"uplift": 0.11}),
            ("nurture_timing_model", "v1", {"uplift": 0.09}),
            ("ad_budget_allocator", "v1", {"uplift": 0.07}),
        ]
        for name, version, metrics in seeds:
            db.add(
                ModelMetadata(
                    org_id=context.current_org_id,
                    name=name,
                    version=version,
                    training_window="90d",
                    metrics_json=metrics,
                    status=ModelStatus.ACTIVE if name == "lead_score_model" else ModelStatus.INACTIVE,
                )
            )
        db.flush()
        db.commit()
        rows = _model_rows(db=db, org_id=context.current_org_id)

    response: list[ModelMetadataResponse] = []
    for row in rows:
        baseline = _safe_float(row.metrics_json.get("auc"), 0.0)
        if baseline <= 0:
            baseline = _safe_float(row.metrics_json.get("uplift"), 0.8)
        recent = baseline * 0.98
        drifted, reason = detect_model_drift(baseline_metric=baseline, recent_metric=recent)
        if drifted and row.status == ModelStatus.ACTIVE:
            row.status = ModelStatus.DEGRADED
            write_event(
                db=db,
                org_id=context.current_org_id,
                source="optimization",
                channel="models",
                event_type="MODEL_ROLLBACK",
                payload_json={"name": row.name, "version": row.version, "reason": reason},
                actor_id=str(context.current_user_id),
            )
        response.append(
            ModelMetadataResponse(
                id=row.id,
                org_id=row.org_id,
                name=row.name,
                version=row.version,
                trained_at=row.trained_at,
                training_window=row.training_window,
                metrics_json=row.metrics_json,
                status=row.status.value,
                created_at=row.created_at,
            )
        )
    db.commit()
    return response


@router.post("/models/{name}/activate", response_model=ModelMetadataResponse)
def activate_model_version(
    name: str,
    payload: ModelActivateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ModelMetadataResponse:
    require_role(context, Role.ADMIN)
    ensure_org_active(db=db, org_id=context.current_org_id)

    rows = _model_rows(db=db, org_id=context.current_org_id, model_name=name)
    target = next((row for row in rows if row.version == payload.version), None)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model version not found")

    for row in rows:
        row.status = ModelStatus.ACTIVE if row.id == target.id else ModelStatus.INACTIVE

    db.flush()
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="optimization",
        channel="models",
        event_type="MODEL_ACTIVATED",
        payload_json={"name": name, "version": target.version},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="optimization.model_activated",
        target_type="model_metadata",
        target_id=str(target.id),
        metadata_json={"name": name, "version": target.version},
    )
    db.commit()
    db.refresh(target)
    return ModelMetadataResponse(
        id=target.id,
        org_id=target.org_id,
        name=target.name,
        version=target.version,
        trained_at=target.trained_at,
        training_window=target.training_window,
        metrics_json=target.metrics_json,
        status=target.status.value,
        created_at=target.created_at,
    )


