from __future__ import annotations

import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import LinkTracking, Role
from ..schemas import LinkCreateRequest, LinkResponse
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..tenancy import RequestContext, get_request_context, require_role

router = APIRouter(tags=["links"])
ALPHABET = string.ascii_lowercase + string.digits


def _short_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(8))


@router.post("/links", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
def create_link(
    payload: LinkCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> LinkResponse:
    require_role(context, Role.AGENT)
    code = _short_code()
    row = LinkTracking(
        org_id=context.current_org_id,
        short_code=code,
        destination_url=str(payload.destination_url),
        utm_json=payload.utm_json,
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
        payload_json={"short_code": row.short_code},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(row)
    return LinkResponse(
        id=row.id,
        org_id=row.org_id,
        short_code=row.short_code,
        destination_url=row.destination_url,
        utm_json=row.utm_json,
        created_at=row.created_at,
    )


@router.get("/r/{code}")
def resolve_link(code: str, db: Session = Depends(get_db)) -> RedirectResponse:
    row = db.scalar(select(LinkTracking).where(LinkTracking.short_code == code, LinkTracking.deleted_at.is_(None)))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link not found")
    write_event(
        db=db,
        org_id=row.org_id,
        source="links",
        channel="web",
        event_type="LINK_REDIRECT",
        payload_json={"short_code": code},
    )
    db.commit()
    return RedirectResponse(url=row.destination_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
