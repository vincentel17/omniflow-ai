from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from packages.policy import apply_inbound_safety_filters
from packages.security import detect_pii
from packages.schemas import NormalizedThread, ReplySuggestionJSON

from ..db import get_db
from ..models import InboxMessage, InboxMessageDirection, InboxThread, InboxThreadStatus, InboxThreadType, RiskTier, Role
from ..schemas import (
    DraftReplyRequest,
    InboxAssignRequest,
    InboxIngestMockRequest,
    InboxIngestMockResponse,
    InboxMessageResponse,
    InboxThreadResponse,
    ReplySuggestionResponse,
)
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..services.org_settings import get_org_settings_payload
from ..services.phase3 import get_vertical_pack_slug, utcnow
from ..services.phase4 import build_mock_reply_suggestion
from ..services.policy import load_policy_engine
from ..services.rate_limit import enforce_org_rate_limit
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/inbox", tags=["inbox"])


def _serialize_thread(row: InboxThread) -> InboxThreadResponse:
    return InboxThreadResponse(
        id=row.id,
        org_id=row.org_id,
        provider=row.provider,
        account_ref=row.account_ref,
        external_thread_id=row.external_thread_id,
        thread_type=row.thread_type,
        subject=row.subject,
        participants_json=row.participants_json,
        last_message_at=row.last_message_at,
        status=row.status,
        lead_id=row.lead_id,
        assigned_to_user_id=row.assigned_to_user_id,
        created_at=row.created_at,
    )


def _serialize_message(row: InboxMessage) -> InboxMessageResponse:
    return InboxMessageResponse(
        id=row.id,
        org_id=row.org_id,
        thread_id=row.thread_id,
        external_message_id=row.external_message_id,
        direction=row.direction,
        sender_ref=row.sender_ref,
        sender_display=row.sender_display,
        body_text=row.body_text,
        body_raw_json=row.body_raw_json,
        flags_json=row.flags_json,
        created_at=row.created_at,
    )


@router.post("/ingest/mock", response_model=InboxIngestMockResponse, status_code=status.HTTP_201_CREATED)
def ingest_mock_thread(
    payload: InboxIngestMockRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> InboxIngestMockResponse:
    require_role(context, Role.AGENT)
    normalized = NormalizedThread.model_validate({"messages": payload.messages, **payload.thread})
    thread = db.scalar(
        org_scoped(
            select(InboxThread).where(
                InboxThread.provider == normalized.provider,
                InboxThread.account_ref == normalized.account_ref,
                InboxThread.external_thread_id == normalized.external_thread_id,
                InboxThread.deleted_at.is_(None),
            ),
            context.current_org_id,
            InboxThread,
        )
    )
    if thread is None:
        thread = InboxThread(
            org_id=context.current_org_id,
            provider=normalized.provider,
            account_ref=normalized.account_ref,
            external_thread_id=normalized.external_thread_id,
            thread_type=InboxThreadType(normalized.thread_type),
            subject=normalized.subject,
            participants_json=normalized.participants_json,
            last_message_at=normalized.last_message_at,
            status=InboxThreadStatus.OPEN,
        )
        db.add(thread)
        db.flush()

    pack_slug = get_vertical_pack_slug(db=db, org_id=context.current_org_id)
    policy = load_policy_engine(pack_slug)
    inserted = 0
    for message in normalized.messages:
        existing = db.scalar(
            org_scoped(
                select(InboxMessage).where(
                    InboxMessage.thread_id == thread.id,
                    InboxMessage.external_message_id == message.external_message_id,
                    InboxMessage.deleted_at.is_(None),
                ),
                context.current_org_id,
                InboxMessage,
            )
        )
        if existing is not None:
            continue
        safety = apply_inbound_safety_filters(message.body_text)
        validation = policy.validate_content(safety.sanitized_text, context={"channel": "inbox"})
        flags = dict(safety.flags)
        pii_flags = detect_pii(safety.sanitized_text)
        if pii_flags.get("contains_health"):
            flags["health_related"] = True
            flags["needs_human_review"] = True
        if not validation.allowed:
            flags["policy_blocked"] = True
            flags["needs_human_review"] = True
        db.add(
            InboxMessage(
                org_id=context.current_org_id,
                thread_id=thread.id,
                external_message_id=message.external_message_id,
                direction=InboxMessageDirection(message.direction),
                sender_ref=message.sender_ref,
                sender_display=message.sender_display,
                body_text=safety.sanitized_text,
                body_raw_json=message.body_raw_json,
                flags_json=flags,
            )
        )
        inserted += 1
    thread.last_message_at = normalized.last_message_at or utcnow()
    db.flush()

    write_event(
        db=db,
        org_id=context.current_org_id,
        source="connector",
        channel="inbox",
        event_type="INBOX_INGESTED",
        payload_json={"thread_id": str(thread.id), "inserted_messages": inserted},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="inbox.ingest_mock",
        target_type="inbox_thread",
        target_id=str(thread.id),
        metadata_json={"inserted_messages": inserted},
        risk_tier=RiskTier.TIER_1,
    )
    db.commit()
    return InboxIngestMockResponse(thread_id=thread.id, inserted_messages=inserted)


@router.get("/threads", response_model=list[InboxThreadResponse])
def list_threads(
    status_filter: InboxThreadStatus | None = Query(default=None, alias="status"),
    provider: str | None = Query(default=None),
    assigned_to: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[InboxThreadResponse]:
    stmt = org_scoped(
        select(InboxThread)
        .where(InboxThread.deleted_at.is_(None))
        .order_by(desc(InboxThread.last_message_at), desc(InboxThread.created_at))
        .limit(limit)
        .offset(offset),
        context.current_org_id,
        InboxThread,
    )
    if status_filter is not None:
        stmt = stmt.where(InboxThread.status == status_filter)
    if provider is not None:
        stmt = stmt.where(InboxThread.provider == provider)
    if assigned_to is not None:
        stmt = stmt.where(InboxThread.assigned_to_user_id == assigned_to)
    rows = db.scalars(stmt).all()
    return [_serialize_thread(row) for row in rows]


@router.get("/threads/{thread_id}", response_model=InboxThreadResponse)
def get_thread(
    thread_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> InboxThreadResponse:
    thread = db.scalar(
        org_scoped(
            select(InboxThread).where(InboxThread.id == thread_id, InboxThread.deleted_at.is_(None)),
            context.current_org_id,
            InboxThread,
        )
    )
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thread not found")
    return _serialize_thread(thread)


@router.get("/threads/{thread_id}/messages", response_model=list[InboxMessageResponse])
def list_thread_messages(
    thread_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[InboxMessageResponse]:
    thread = db.scalar(
        org_scoped(select(InboxThread).where(InboxThread.id == thread_id, InboxThread.deleted_at.is_(None)), context.current_org_id, InboxThread)
    )
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thread not found")
    rows = db.scalars(
        org_scoped(
            select(InboxMessage)
            .where(InboxMessage.thread_id == thread_id, InboxMessage.deleted_at.is_(None))
            .order_by(InboxMessage.created_at)
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            InboxMessage,
        )
    ).all()
    return [_serialize_message(row) for row in rows]


@router.post("/threads/{thread_id}/assign", response_model=InboxThreadResponse)
def assign_thread(
    thread_id: uuid.UUID,
    payload: InboxAssignRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> InboxThreadResponse:
    require_role(context, Role.MEMBER)
    thread = db.scalar(
        org_scoped(
            select(InboxThread).where(InboxThread.id == thread_id, InboxThread.deleted_at.is_(None)),
            context.current_org_id,
            InboxThread,
        )
    )
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thread not found")
    thread.assigned_to_user_id = payload.assigned_to_user_id
    db.flush()
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="inbox",
        channel="inbox",
        event_type="THREAD_ASSIGNED",
        payload_json={"thread_id": str(thread.id), "assigned_to_user_id": str(payload.assigned_to_user_id)},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="inbox.thread_assigned",
        target_type="inbox_thread",
        target_id=str(thread.id),
        metadata_json={"assigned_to_user_id": str(payload.assigned_to_user_id)},
    )
    db.commit()
    db.refresh(thread)
    return _serialize_thread(thread)


@router.post("/threads/{thread_id}/close", response_model=InboxThreadResponse)
def close_thread(
    thread_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> InboxThreadResponse:
    require_role(context, Role.AGENT)
    thread = db.scalar(
        org_scoped(
            select(InboxThread).where(InboxThread.id == thread_id, InboxThread.deleted_at.is_(None)),
            context.current_org_id,
            InboxThread,
        )
    )
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thread not found")
    thread.status = InboxThreadStatus.CLOSED
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="inbox.thread_closed",
        target_type="inbox_thread",
        target_id=str(thread.id),
    )
    db.commit()
    db.refresh(thread)
    return _serialize_thread(thread)


@router.post("/threads/{thread_id}/suggest-reply", response_model=ReplySuggestionResponse)
def suggest_reply(
    thread_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> ReplySuggestionResponse:
    require_role(context, Role.AGENT)
    enforce_org_rate_limit(org_id=context.current_org_id, bucket_name="reply_suggestions", max_requests=60, window_seconds=60)
    thread = db.scalar(
        org_scoped(
            select(InboxThread).where(InboxThread.id == thread_id, InboxThread.deleted_at.is_(None)),
            context.current_org_id,
            InboxThread,
        )
    )
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thread not found")
    messages = db.scalars(
        org_scoped(
            select(InboxMessage)
            .where(InboxMessage.thread_id == thread.id, InboxMessage.deleted_at.is_(None))
            .order_by(desc(InboxMessage.created_at))
            .limit(6),
            context.current_org_id,
            InboxMessage,
        )
    ).all()
    transcript = "\n".join(message.body_text for message in reversed(messages))
    settings_payload = get_org_settings_payload(db=db, org_id=context.current_org_id)
    compliance_mode = str(settings_payload.get("compliance_mode", "none"))
    health_thread = any((message.flags_json or {}).get("health_related") is True for message in messages if isinstance(message.flags_json, dict))
    if compliance_mode == "home_care" and health_thread:
        write_audit_log(
            db=db,
            context=context,
            action="inbox.reply_suggestion_blocked",
            target_type="inbox_thread",
            target_id=str(thread.id),
            metadata_json={"reason": "home_care_health_related"},
            risk_tier=RiskTier.TIER_3,
        )
        db.commit()
        return ReplySuggestionResponse(
            intent="escalate",
            reply_text="This thread contains health-related content and requires human review.",
            followup_questions=[],
            risk_tier=RiskTier.TIER_3,
            required_disclaimers=[],
            policy_warnings=["home_care_health_related_requires_approval"],
        )

    suggestion = build_mock_reply_suggestion(db=db, org_id=context.current_org_id, transcript=transcript)

    pack_slug = get_vertical_pack_slug(db=db, org_id=context.current_org_id)
    policy = load_policy_engine(pack_slug)
    validation = policy.validate_content(suggestion.reply_text, context={"channel": "inbox"})
    if not validation.allowed:
        suggestion = ReplySuggestionJSON(
            intent="escalate",
            reply_text="This thread requires human review before replying.",
            followup_questions=[],
            risk_tier="TIER_3",
            required_disclaimers=suggestion.required_disclaimers,
        )

    write_event(
        db=db,
        org_id=context.current_org_id,
        source="ai",
        channel="inbox",
        event_type="REPLY_SUGGESTED",
        payload_json={"thread_id": str(thread.id), "risk_tier": suggestion.risk_tier},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="ai.suggest_reply",
        target_type="inbox_thread",
        target_id=str(thread.id),
        metadata_json={"risk_tier": suggestion.risk_tier},
        risk_tier=RiskTier(suggestion.risk_tier),
    )
    db.commit()
    return ReplySuggestionResponse(
        intent=suggestion.intent,
        reply_text=suggestion.reply_text,
        followup_questions=suggestion.followup_questions,
        risk_tier=RiskTier(suggestion.risk_tier),
        required_disclaimers=suggestion.required_disclaimers,
        policy_warnings=validation.reasons,
    )


@router.post("/threads/{thread_id}/draft-reply", response_model=InboxMessageResponse, status_code=status.HTTP_201_CREATED)
def draft_reply(
    thread_id: uuid.UUID,
    payload: DraftReplyRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> InboxMessageResponse:
    require_role(context, Role.AGENT)
    thread = db.scalar(
        org_scoped(
            select(InboxThread).where(InboxThread.id == thread_id, InboxThread.deleted_at.is_(None)),
            context.current_org_id,
            InboxThread,
        )
    )
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thread not found")
    settings_payload = get_org_settings_payload(db=db, org_id=context.current_org_id)
    compliance_mode = str(settings_payload.get("compliance_mode", "none"))
    recent_messages = db.scalars(
        org_scoped(
            select(InboxMessage)
            .where(InboxMessage.thread_id == thread.id, InboxMessage.deleted_at.is_(None))
            .order_by(desc(InboxMessage.created_at))
            .limit(12),
            context.current_org_id,
            InboxMessage,
        )
    ).all()
    health_thread = any((message.flags_json or {}).get("health_related") is True for message in recent_messages if isinstance(message.flags_json, dict))
    if compliance_mode == "home_care" and health_thread:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="home care compliance blocks auto-reply drafting for health-related threads",
        )

    policy = load_policy_engine(get_vertical_pack_slug(db=db, org_id=context.current_org_id))
    validation = policy.validate_content(payload.body_text, context={"channel": "inbox"})
    flags = {"policy_blocked": not validation.allowed, "needs_human_review": not validation.allowed}
    draft = InboxMessage(
        org_id=context.current_org_id,
        thread_id=thread.id,
        external_message_id=f"draft-{uuid.uuid4()}",
        direction=InboxMessageDirection.OUTBOUND,
        sender_ref=str(context.current_user_id),
        sender_display="OmniFlow Draft",
        body_text=payload.body_text,
        body_raw_json={"draft": True},
        flags_json=flags,
    )
    db.add(draft)
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="inbox.draft_reply_created",
        target_type="inbox_message",
        target_id=str(draft.id),
        metadata_json={"thread_id": str(thread.id), "policy_warnings": validation.reasons},
    )
    db.commit()
    db.refresh(draft)
    return _serialize_message(draft)














