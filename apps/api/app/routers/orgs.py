from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Membership, Org, Role
from ..schemas import MembershipResponse, MembershipUpsertRequest, OrgCreateRequest, OrgResponse
from ..services.audit import write_audit_log
from ..tenancy import RequestContext, get_request_context, require_role

router = APIRouter(prefix="/orgs", tags=["orgs"])


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
def create_org(
    payload: OrgCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> OrgResponse:
    org = Org(name=payload.name)
    db.add(org)
    db.flush()

    owner_membership = Membership(org_id=org.id, user_id=context.current_user_id, role=Role.OWNER)
    db.add(owner_membership)
    db.flush()

    write_audit_log(
        db=db,
        context=context,
        action="org.created",
        target_type="org",
        target_id=str(org.id),
        metadata_json={"name": org.name},
    )
    write_audit_log(
        db=db,
        context=context,
        action="membership.created",
        target_type="membership",
        target_id=str(owner_membership.id),
        metadata_json={"org_id": str(org.id), "user_id": str(context.current_user_id), "role": Role.OWNER.value},
    )

    db.commit()
    db.refresh(org)
    return OrgResponse(id=org.id, name=org.name, created_at=org.created_at)


@router.post("/memberships", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
def upsert_membership(
    payload: MembershipUpsertRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> MembershipResponse:
    if payload.org_id != context.current_org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="org scope mismatch")
    require_role(context, Role.ADMIN)

    membership = db.scalar(
        select(Membership).where(
            Membership.org_id == payload.org_id,
            Membership.user_id == payload.user_id,
            Membership.deleted_at.is_(None),
        )
    )
    action = "membership.updated"
    if membership is None:
        membership = Membership(org_id=payload.org_id, user_id=payload.user_id, role=payload.role)
        db.add(membership)
        action = "membership.created"
    else:
        membership.role = payload.role
    db.flush()

    write_audit_log(
        db=db,
        context=context,
        action=action,
        target_type="membership",
        target_id=str(membership.id),
        metadata_json={"org_id": str(payload.org_id), "user_id": str(payload.user_id), "role": payload.role.value},
    )
    db.commit()
    db.refresh(membership)
    return MembershipResponse(
        id=membership.id,
        org_id=membership.org_id,
        user_id=membership.user_id,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.post("/users/{user_id}", status_code=status.HTTP_201_CREATED)
def create_user_stub(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, str]:
    del context
    from ..models import User

    existing = db.scalar(select(User).where(User.id == user_id))
    if existing is None:
        db.add(User(id=user_id))
        db.commit()
    return {"status": "ok", "user_id": str(user_id)}
