from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid role header") from exc


def get_request_context(
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

    if not x_omniflow_user_id or not x_omniflow_org_id or not x_omniflow_role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing auth context headers")

    try:
        user_id = uuid.UUID(x_omniflow_user_id)
        org_id = uuid.UUID(x_omniflow_org_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid auth context headers") from exc

    role = _parse_role(x_omniflow_role)
    membership = db.scalar(
        select(Membership).where(
            Membership.org_id == org_id,
            Membership.user_id == user_id,
            Membership.deleted_at.is_(None),
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="org membership required")

    return RequestContext(current_user_id=user_id, current_org_id=org_id, current_role=role)
