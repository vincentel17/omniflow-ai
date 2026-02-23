from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.schemas import LeadCaptureJSON, LeadScoreExplanationJSON, NurturePlanJSON, ReplySuggestionJSON
from packages.schemas.phase4 import LeadFields, LeadScoreFactor, NurtureTaskJSON

from ..models import (
    BrandProfile,
    Lead,
    LeadAssignment,
    LeadScore,
    Membership,
    Pipeline,
    Role,
    SLAConfig,
    Stage,
)
from .phase3 import utcnow
from .verticals import load_pack_file

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"\+?\d[\d\-\s()]{7,}\d")
INTENT_KEYWORDS = ("buy", "sell", "listing", "appointment", "tour", "visit", "asap", "today", "urgent")


def _load_brand_disclaimers(db: Session, org_id: uuid.UUID) -> list[str]:
    profile = db.scalar(select(BrandProfile).where(BrandProfile.org_id == org_id, BrandProfile.deleted_at.is_(None)))
    if profile is None:
        return []
    disclaimers = profile.brand_voice_json.get("disclaimers", [])
    if not isinstance(disclaimers, list):
        return []
    return [str(item) for item in disclaimers if isinstance(item, str)]


def build_mock_reply_suggestion(db: Session, org_id: uuid.UUID, transcript: str) -> ReplySuggestionJSON:
    lower = transcript.lower()
    intent = "qualify" if any(word in lower for word in ("buy", "sell", "price", "showing")) else "answer"
    followups = ["What timeframe are you targeting?", "Which area is most important to you?"]
    reply_text = (
        "Thanks for reaching out. I can help with next steps and share options based on your timeline."
        if intent == "qualify"
        else "Thanks for the message. I can help clarify details and follow up with the right info."
    )
    risk_tier = "TIER_2" if "contract" in lower or "legal" in lower else "TIER_1"
    return ReplySuggestionJSON(
        intent=intent,
        reply_text=reply_text,
        followup_questions=followups,
        risk_tier=risk_tier,
        required_disclaimers=_load_brand_disclaimers(db=db, org_id=org_id),
    )


def extract_lead_capture(transcript: str, classification: str = "other") -> LeadCaptureJSON:
    email_match = EMAIL_PATTERN.search(transcript)
    phone_match = PHONE_PATTERN.search(transcript)
    name = "Inbound Lead"
    for token in transcript.split():
        clean = token.strip(",.!?")
        if clean.istitle() and len(clean) >= 3:
            name = clean
            break
    return LeadCaptureJSON(
        lead_fields=LeadFields(
            name=name,
            email=email_match.group(0) if email_match else None,
            phone=phone_match.group(0) if phone_match else None,
            location={},
        ),
        classification=classification,
        next_step_recommendation="Respond quickly and qualify timeline and intent.",
    )


def score_lead_from_context(lead: Lead, transcript: str, pack_slug: str) -> LeadScoreExplanationJSON:
    lower = transcript.lower()
    factors: list[LeadScoreFactor] = []
    total = 0.0

    completeness = 1.0 if lead.email and lead.phone else 0.5 if (lead.email or lead.phone) else 0.0
    factors.append(
        LeadScoreFactor(
            name="completeness",
            weight=25,
            value=completeness,
            explanation="Lead profile completeness based on contact fields.",
        )
    )
    total += 25 * completeness

    intent_value = 1.0 if any(word in lower for word in INTENT_KEYWORDS) else 0.2
    factors.append(
        LeadScoreFactor(
            name="intent_keywords",
            weight=30,
            value=intent_value,
            explanation="Inbound messages include conversion intent signals.",
        )
    )
    total += 30 * intent_value

    urgency_value = 1.0 if any(word in lower for word in ("asap", "today", "urgent", "now")) else 0.1
    factors.append(
        LeadScoreFactor(
            name="response_urgency",
            weight=20,
            value=urgency_value,
            explanation="Message urgency indicates near-term conversion potential.",
        )
    )
    total += 20 * urgency_value

    geo_value = 1.0 if lead.location_json else 0.1
    factors.append(
        LeadScoreFactor(
            name="geo_relevance",
            weight=10,
            value=geo_value,
            explanation="Location detail is available for routing and relevance.",
        )
    )
    total += 10 * geo_value

    scoring_cfg = load_pack_file(pack_slug, "scoring.json")
    vertical_weight = 15
    vertical_signal = 0.3
    for factor in scoring_cfg.get("factors", []):
        name = str(factor.get("name", "vertical_intent"))
        if name in lower:
            vertical_signal = 1.0
            break
    factors.append(
        LeadScoreFactor(
            name="vertical_intent",
            weight=vertical_weight,
            value=vertical_signal,
            explanation="Vertical-pack specific intent scoring.",
        )
    )
    total += vertical_weight * vertical_signal

    bounded = max(0, min(100, int(round(total))))
    return LeadScoreExplanationJSON(total=bounded, factors=factors)


def choose_round_robin_assignee(db: Session, org_id: uuid.UUID) -> tuple[uuid.UUID, str]:
    agent_memberships = db.scalars(
        select(Membership).where(
            Membership.org_id == org_id,
            Membership.role == Role.AGENT,
            Membership.deleted_at.is_(None),
        )
    ).all()
    if not agent_memberships:
        fallback = db.scalar(
            select(Membership).where(Membership.org_id == org_id, Membership.deleted_at.is_(None)).order_by(Membership.created_at)
        )
        if fallback is None:
            raise ValueError("no org members available for assignment")
        return fallback.user_id, "fallback:first-member"

    assignment_counts = defaultdict(int)
    rows = db.execute(
        select(LeadAssignment.assigned_to_user_id, func.count(LeadAssignment.id))
        .where(LeadAssignment.org_id == org_id, LeadAssignment.deleted_at.is_(None))
        .group_by(LeadAssignment.assigned_to_user_id)
    ).all()
    for user_id, count in rows:
        assignment_counts[user_id] = int(count)

    selected = sorted(agent_memberships, key=lambda member: (assignment_counts[member.user_id], str(member.user_id)))[0]
    return selected.user_id, "round_robin"


def build_nurture_plan(lead: Lead) -> NurturePlanJSON:
    intro = f"Hi {lead.name or 'there'}, thanks for reaching out. We can help with your request."
    return NurturePlanJSON(
        tasks=[
            NurtureTaskJSON(
                type="task",
                due_in_minutes=15,
                message_template_key="first_response",
                message_body="Respond to inbound lead and confirm key qualification details.",
            ),
            NurtureTaskJSON(
                type="email",
                due_in_minutes=60,
                message_template_key="value_followup",
                message_body=intro,
            ),
        ]
    )


def ensure_sla_config(db: Session, org_id: uuid.UUID) -> SLAConfig:
    config = db.scalar(select(SLAConfig).where(SLAConfig.org_id == org_id, SLAConfig.deleted_at.is_(None)))
    if config is None:
        config = SLAConfig(
            org_id=org_id,
            response_time_minutes=30,
            escalation_minutes=60,
            notify_channels_json=["in_app"],
        )
        db.add(config)
        db.flush()
    return config


def ensure_pipeline_templates(db: Session, org_id: uuid.UUID, pack_slug: str) -> None:
    payload = load_pack_file(pack_slug, "pipelines.json")
    pipelines = payload.get("pipelines", [])
    for pipeline_row in pipelines:
        slug = str(pipeline_row.get("id", "default")).strip()
        pipeline = db.scalar(
            select(Pipeline).where(Pipeline.org_id == org_id, Pipeline.slug == slug, Pipeline.deleted_at.is_(None))
        )
        if pipeline is None:
            pipeline = Pipeline(
                org_id=org_id,
                slug=slug,
                name=str(pipeline_row.get("name", slug)),
                is_default=False,
                config_json=pipeline_row,
            )
            db.add(pipeline)
            db.flush()
        stages = pipeline_row.get("stages") or [{"slug": step, "name": str(step).replace("-", " ").title()} for step in pipeline_row.get("steps", [])]
        for index, stage_row in enumerate(stages):
            stage_slug = str(stage_row.get("slug", f"stage-{index + 1}"))
            exists = db.scalar(
                select(Stage).where(
                    Stage.org_id == org_id,
                    Stage.pipeline_id == pipeline.id,
                    Stage.slug == stage_slug,
                    Stage.deleted_at.is_(None),
                )
            )
            if exists is not None:
                continue
            db.add(
                Stage(
                    org_id=org_id,
                    pipeline_id=pipeline.id,
                    slug=stage_slug,
                    name=str(stage_row.get("name", stage_slug)),
                    sequence=index,
                    exit_on_win=bool(stage_row.get("exit_on_win", False)),
                )
            )
    db.flush()


def due_at_from_minutes(minutes: int):
    return utcnow() + timedelta(minutes=minutes)


def upsert_lead_score(db: Session, org_id: uuid.UUID, lead: Lead, score_payload: LeadScoreExplanationJSON) -> LeadScore:
    score = db.scalar(
        select(LeadScore).where(
            LeadScore.org_id == org_id,
            LeadScore.lead_id == lead.id,
            LeadScore.deleted_at.is_(None),
        )
    )
    if score is None:
        score = LeadScore(
            org_id=org_id,
            lead_id=lead.id,
            score_total=score_payload.total,
            score_json=score_payload.model_dump(mode="json"),
            model_version="v1",
            scored_at=utcnow(),
        )
        db.add(score)
        db.flush()
        return score

    score.score_total = score_payload.total
    score.score_json = score_payload.model_dump(mode="json")
    score.scored_at = utcnow()
    score.model_version = "v1"
    db.flush()
    return score
