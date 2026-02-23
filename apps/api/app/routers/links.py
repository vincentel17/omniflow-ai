from __future__ import annotations

import hashlib
import secrets
import string
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Lead, LinkClick, LinkTracking, Role
from ..schemas import LinkAttachLeadRequest, LinkCreateRequest, LinkResponse
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(tags=["links"])
ALPHABET = string.ascii_lowercase + string.digits


def _short_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(8))


def _hash_value(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _merged_utm(payload: LinkCreateRequest) -> dict[str, object]:
    utm = dict(payload.utm_json)
    if payload.source:
        utm["source"] = payload.source
    if payload.medium:
        utm["medium"] = payload.medium
    if payload.campaign:
        utm["campaign"] = payload.campaign
    if payload.content_id:
        utm["content_id"] = payload.content_id
    if payload.campaign_plan_id:
        utm["campaign_plan_id"] = payload.campaign_plan_id
    if payload.channel:
        utm["channel"] = payload.channel
    return utm


def _serialize_link(row: LinkTracking) -> LinkResponse:
    return LinkResponse(
        id=row.id,
        org_id=row.org_id,
        short_code=row.short_code,
        destination_url=row.destination_url,
        utm_json=row.utm_json,
        created_at=row.created_at,
        short_url_path=f"/r/{row.short_code}",
    )


@router.post("/links", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
def create_link(
    payload: LinkCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> LinkResponse:
    require_role(context, Role.AGENT)
    code = _short_code()
    while db.scalar(select(LinkTracking).where(LinkTracking.short_code == code, LinkTracking.deleted_at.is_(None))):
        code = _short_code()
    row = LinkTracking(
        org_id=context.current_org_id,
        short_code=code,
        destination_url=str(payload.destination_url),
        utm_json=_merged_utm(payload),
    )
    db.add(row)
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="link.created",
        target_type="link_tracking",
        target_id=str(row.id),
        metadata_json={"short_code": row.short_code},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="links",
        channel="web",
        event_type="LINK_CREATED",
        payload_json={"short_code": row.short_code, "utm": row.utm_json},
        content_id=str(row.utm_json.get("content_id")) if row.utm_json.get("content_id") else None,
        campaign_id=str(row.utm_json.get("campaign_plan_id")) if row.utm_json.get("campaign_plan_id") else None,
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(row)
    return _serialize_link(row)


@router.get("/links", response_model=list[LinkResponse])
def list_links(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[LinkResponse]:
    rows = db.scalars(
        org_scoped(
            select(LinkTracking)
            .where(LinkTracking.deleted_at.is_(None))
            .order_by(desc(LinkTracking.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            LinkTracking,
        )
    ).all()
    return [_serialize_link(row) for row in rows]


@router.get("/links/{link_id}", response_model=LinkResponse)
def get_link(
    link_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> LinkResponse:
    row = db.scalar(
        org_scoped(
            select(LinkTracking).where(LinkTracking.id == link_id, LinkTracking.deleted_at.is_(None)),
            context.current_org_id,
            LinkTracking,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link not found")
    return _serialize_link(row)


@router.post("/links/{link_id}/attach-lead", response_model=LinkResponse)
def attach_link_to_lead(
    link_id: uuid.UUID,
    payload: LinkAttachLeadRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> LinkResponse:
    link = db.scalar(
        org_scoped(
            select(LinkTracking).where(LinkTracking.id == link_id, LinkTracking.deleted_at.is_(None)),
            context.current_org_id,
            LinkTracking,
        )
    )
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link not found")
    lead = db.scalar(
        org_scoped(
            select(Lead).where(Lead.id == payload.lead_id, Lead.deleted_at.is_(None)),
            context.current_org_id,
            Lead,
        )
    )
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lead not found")
    db.query(LinkClick).filter(
        LinkClick.org_id == context.current_org_id,
        LinkClick.tracked_link_id == link_id,
        LinkClick.deleted_at.is_(None),
    ).update({"lead_id": payload.lead_id}, synchronize_session=False)
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="links",
        channel="web",
        event_type="LINK_LEAD_ATTACHED",
        payload_json={"link_id": str(link_id), "lead_id": str(payload.lead_id)},
        lead_id=str(payload.lead_id),
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(link)
    return _serialize_link(link)


@router.get("/r/{code}")
def resolve_link(code: str, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    row = db.scalar(select(LinkTracking).where(LinkTracking.short_code == code, LinkTracking.deleted_at.is_(None)))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link not found")
    forwarded_for = request.headers.get("x-forwarded-for")
    ip_value = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else None)
    click = LinkClick(
        org_id=row.org_id,
        tracked_link_id=row.id,
        short_code=code,
        referrer=request.headers.get("referer"),
        user_agent_hash=_hash_value(request.headers.get("user-agent")),
        ip_hash=_hash_value(ip_value),
        lead_id=None,
    )
    db.add(click)
    db.flush()
    write_event(
        db=db,
        org_id=row.org_id,
        source="links",
        channel="web",
        event_type="LINK_CLICKED",
        payload_json={"short_code": code, "utm": row.utm_json},
        content_id=str(row.utm_json.get("content_id")) if row.utm_json.get("content_id") else None,
        campaign_id=str(row.utm_json.get("campaign_plan_id")) if row.utm_json.get("campaign_plan_id") else None,
    )
    db.commit()
    return RedirectResponse(url=row.destination_url, status_code=status.HTTP_302_FOUND)
