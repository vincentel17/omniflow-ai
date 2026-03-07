from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth_session import verify_session_token
from .db import get_db
from .models import Membership, Role
from .settings import settings


ROLE_ORDER: dict[Role, int] = {
    Role.OWNER: 4,
    Role.ADMIN: 3,
    Role.MEMBER: 2,
    Role.AGENT: 1,
}


@dataclass(frozen=True)
class RequestContext:
    current_user_id: uuid.UUID
    current_org_id: uuid.UUID
    current_role: Role


def org_scoped(stmt: Any, org_id: uuid.UUID, model: Any) -> Any:
    return stmt.where(getattr(model, "org_id") == org_id)


def require_role(context: RequestContext, minimum_role: Role) -> None:
    if ROLE_ORDER[context.current_role] < ROLE_ORDER[minimum_role]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role")


def _parse_role(value: str) -> Role:
    try:
        return Role(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid role") from exc


def _load_membership(db: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> Membership:
    membership = db.scalar(
        select(Membership).where(
            Membership.org_id == org_id,
            Membership.user_id == user_id,
            Membership.deleted_at.is_(None),
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="org membership required")
    return membership


def _context_from_headers(db: Session, user_id_raw: str, org_id_raw: str, role_raw: str) -> RequestContext:
    try:
        user_id = uuid.UUID(user_id_raw)
        org_id = uuid.UUID(org_id_raw)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid auth context headers") from exc

    _parse_role(role_raw)
    membership = _load_membership(db=db, user_id=user_id, org_id=org_id)
    return RequestContext(current_user_id=user_id, current_org_id=org_id, current_role=membership.role)


def _context_from_cookie(db: Session, request: Request) -> RequestContext | None:
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return None

    payload = verify_session_token(token)
    if payload is None:
        return None

    try:
        user_id = uuid.UUID(str(payload["sub"]))
        org_id = uuid.UUID(str(payload["org"]))
        _parse_role(str(payload["role"]))
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid auth session") from exc

    membership = _load_membership(db=db, user_id=user_id, org_id=org_id)
    return RequestContext(current_user_id=user_id, current_org_id=org_id, current_role=membership.role)


def get_request_context(
    request: Request,
    db: Session = Depends(get_db),
    x_omniflow_user_id: str | None = Header(default=None),
    x_omniflow_org_id: str | None = Header(default=None),
    x_omniflow_role: str | None = Header(default=None),
) -> RequestContext:
    if settings.dev_auth_bypass:
        return RequestContext(
            current_user_id=uuid.UUID(settings.dev_user_id),
            current_org_id=uuid.UUID(settings.dev_org_id),
            current_role=_parse_role(settings.dev_role),
        )

    if settings.auth_mode in {"headers", "hybrid"}:
        if x_omniflow_user_id and x_omniflow_org_id and x_omniflow_role:
            return _context_from_headers(
                db=db,
                user_id_raw=x_omniflow_user_id,
                org_id_raw=x_omniflow_org_id,
                role_raw=x_omniflow_role,
            )

    if settings.auth_mode in {"session", "hybrid"}:
        cookie_context = _context_from_cookie(db=db, request=request)
        if cookie_context is not None:
            return cookie_context

    if settings.auth_mode == "headers":
        detail = "missing auth context headers"
    elif settings.auth_mode == "session":
        detail = "missing auth session"
    else:
        detail = "missing auth context"
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
