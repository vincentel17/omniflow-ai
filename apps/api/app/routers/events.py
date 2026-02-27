from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Event, Role
from ..schemas import EventCreateRequest, EventResponse
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role
from packages.events import EventPayload, build_event_payload

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> EventResponse:
    require_role(context, Role.AGENT)

    event_payload = build_event_payload(
        EventPayload(
            source=payload.source,
            channel=payload.channel,
            event_type=payload.type,
            campaign_id=payload.campaign_id,
            content_id=payload.content_id,
            lead_id=payload.lead_id,
            actor_id=payload.actor_id,
            payload_json=payload.payload_json,
        )
    )
    event = write_event(
        db=db,
        org_id=context.current_org_id,
        source=str(event_payload["source"]),
        channel=str(event_payload["channel"]),
        event_type=str(event_payload["type"]),
        payload_json=dict(event_payload.get("payload_json", {})),
        campaign_id=event_payload.get("campaign_id"),
        content_id=event_payload.get("content_id"),
        lead_id=event_payload.get("lead_id"),
        actor_id=event_payload.get("actor_id"),
    )

    write_audit_log(
        db=db,
        context=context,
        action="event.created",
        target_type="event",
        target_id=str(event.id),
        metadata_json={"type": event.type, "channel": event.channel},
    )
    db.commit()
    db.refresh(event)
    return EventResponse(
        id=event.id,
        org_id=event.org_id,
        source=event.source,
        channel=event.channel,
        campaign_id=event.campaign_id,
        content_id=event.content_id,
        lead_id=event.lead_id,
        actor_id=event.actor_id,
        type=event.type,
        payload_json=event.payload_json,
        created_at=event.created_at,
    )


@router.get("", response_model=list[EventResponse])
def list_events(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[EventResponse]:
    stmt = org_scoped(
        select(Event).where(Event.deleted_at.is_(None)).order_by(desc(Event.created_at)).limit(limit).offset(offset),
        context.current_org_id,
        Event,
    )
    rows = db.scalars(stmt).all()
    return [
        EventResponse(
            id=row.id,
            org_id=row.org_id,
            source=row.source,
            channel=row.channel,
            campaign_id=row.campaign_id,
            content_id=row.content_id,
            lead_id=row.lead_id,
            actor_id=row.actor_id,
            type=row.type,
            payload_json=row.payload_json,
            created_at=row.created_at,
        )
        for row in rows
    ]
