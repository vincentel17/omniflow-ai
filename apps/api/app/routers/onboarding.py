from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import OnboardingSession, OnboardingSessionStatus, RiskTier, Role
from ..schemas import OnboardingSessionResponse, OnboardingStepCompleteRequest
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..tenancy import RequestContext, get_request_context, require_role

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

DEFAULT_STEPS = [
    "select_vertical_pack",
    "create_brand_profile",
    "connect_account",
    "run_presence_audit",
    "generate_campaign_plan",
    "generate_content_items",
    "approve_schedule_first_post",
    "ingest_mock_inbox_interaction",
    "create_and_route_lead",
]


def _serialize(row: OnboardingSession) -> OnboardingSessionResponse:
    return OnboardingSessionResponse(
        id=row.id,
        org_id=row.org_id,
        status=row.status,
        steps_json=row.steps_json,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


def _latest_session(db: Session, org_id) -> OnboardingSession | None:  # noqa: ANN001
    return db.scalar(
        select(OnboardingSession)
        .where(
            OnboardingSession.org_id == org_id,
            OnboardingSession.deleted_at.is_(None),
        )
        .order_by(desc(OnboardingSession.created_at))
        .limit(1)
    )


@router.post("/start", response_model=OnboardingSessionResponse)
def start_onboarding(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> OnboardingSessionResponse:
    require_role(context, Role.ADMIN)
    existing = _latest_session(db=db, org_id=context.current_org_id)
    if existing and existing.status == OnboardingSessionStatus.IN_PROGRESS:
        return _serialize(existing)

    steps = {step: False for step in DEFAULT_STEPS}
    row = OnboardingSession(
        org_id=context.current_org_id,
        status=OnboardingSessionStatus.IN_PROGRESS,
        steps_json=steps,
        completed_at=None,
    )
    db.add(row)
    db.flush()
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="onboarding",
        channel="ops",
        event_type="ONBOARDING_STARTED",
        payload_json={"session_id": str(row.id)},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="onboarding.started",
        target_type="onboarding_session",
        target_id=str(row.id),
        metadata_json={"steps": list(steps.keys())},
        risk_tier=RiskTier.TIER_1,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.get("/status", response_model=OnboardingSessionResponse | None)
def onboarding_status(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> OnboardingSessionResponse | None:
    row = _latest_session(db=db, org_id=context.current_org_id)
    if row is None:
        return None
    return _serialize(row)


@router.post("/step/{step_id}/complete", response_model=OnboardingSessionResponse)
def complete_onboarding_step(
    step_id: str,
    payload: OnboardingStepCompleteRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> OnboardingSessionResponse:
    require_role(context, Role.AGENT)
    row = _latest_session(db=db, org_id=context.current_org_id)
    if row is None:
        steps = {step: False for step in DEFAULT_STEPS}
        row = OnboardingSession(
            org_id=context.current_org_id,
            status=OnboardingSessionStatus.IN_PROGRESS,
            steps_json=steps,
            completed_at=None,
        )
        db.add(row)
        db.flush()

    steps = cast(dict[str, bool], dict(row.steps_json or {}))
    if step_id not in steps:
        steps[step_id] = False
    steps[step_id] = payload.completed
    row.steps_json = cast(dict[str, object], steps)
    all_done = all(bool(value) for value in steps.values())
    row.status = OnboardingSessionStatus.COMPLETED if all_done else OnboardingSessionStatus.IN_PROGRESS
    row.completed_at = datetime.now(UTC) if all_done else None
    db.flush()

    write_event(
        db=db,
        org_id=context.current_org_id,
        source="onboarding",
        channel="ops",
        event_type="ONBOARDING_STEP_COMPLETED",
        payload_json={"session_id": str(row.id), "step_id": step_id, "completed": payload.completed},
        actor_id=str(context.current_user_id),
    )
    if all_done:
        write_event(
            db=db,
            org_id=context.current_org_id,
            source="onboarding",
            channel="ops",
            event_type="ONBOARDING_COMPLETED",
            payload_json={"session_id": str(row.id)},
            actor_id=str(context.current_user_id),
        )
    write_audit_log(
        db=db,
        context=context,
        action="onboarding.step_completed",
        target_type="onboarding_session",
        target_id=str(row.id),
        metadata_json={"step_id": step_id, "completed": payload.completed, "all_done": all_done},
        risk_tier=RiskTier.TIER_1,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)

