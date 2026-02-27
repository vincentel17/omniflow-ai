from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Role, VerticalPack
from ..schemas import VerticalPackResponse, VerticalPackSelectRequest
from ..services.audit import write_audit_log
from ..services.verticals import list_available_packs
from ..services.workflows import seed_pack_workflows
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/verticals", tags=["verticals"])


@router.get("/packs")
def get_packs() -> dict[str, list[str]]:
    return {"packs": list_available_packs()}


@router.post("/select", response_model=VerticalPackResponse)
def select_pack(
    payload: VerticalPackSelectRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> VerticalPackResponse:
    require_role(context, Role.ADMIN)
    available = set(list_available_packs())
    if payload.pack_slug not in available:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vertical pack not found")

    existing = db.scalar(
        org_scoped(select(VerticalPack).where(VerticalPack.deleted_at.is_(None)), context.current_org_id, VerticalPack)
    )
    if existing is None:
        existing = VerticalPack(org_id=context.current_org_id, pack_slug=payload.pack_slug)
        db.add(existing)
    else:
        existing.pack_slug = payload.pack_slug

    db.flush()
    seeded_workflows = seed_pack_workflows(db=db, org_id=context.current_org_id, pack_slug=payload.pack_slug)

    write_audit_log(
        db=db,
        context=context,
        action="vertical_pack.selected",
        target_type="vertical_pack",
        target_id=str(existing.id),
        metadata_json={"pack_slug": payload.pack_slug, "seeded_workflows": seeded_workflows},
    )
    db.commit()
    db.refresh(existing)
    return VerticalPackResponse(
        id=existing.id,
        org_id=existing.org_id,
        pack_slug=existing.pack_slug,
        created_at=existing.created_at,
    )


@router.get("/current", response_model=VerticalPackResponse)
def current_pack(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> VerticalPackResponse:
    current = db.scalar(
        org_scoped(select(VerticalPack).where(VerticalPack.deleted_at.is_(None)), context.current_org_id, VerticalPack)
    )
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no vertical pack selected")
    return VerticalPackResponse(
        id=current.id,
        org_id=current.org_id,
        pack_slug=current.pack_slug,
        created_at=current.created_at,
    )
