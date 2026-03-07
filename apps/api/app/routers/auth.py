from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth_session import create_session_token, verify_session_token
from ..db import get_db
from ..models import Membership, User
from ..settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    org_id: uuid.UUID | None = None


class SessionResponse(BaseModel):
    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str


class SessionInfoResponse(BaseModel):
    authenticated: bool
    session: SessionResponse | None = None


def _get_membership(db: Session, user_id: uuid.UUID, org_id: uuid.UUID | None) -> Membership | None:
    stmt = (
        select(Membership)
        .where(Membership.user_id == user_id, Membership.deleted_at.is_(None))
        .order_by(Membership.created_at.asc())
    )
    if org_id:
        stmt = stmt.where(Membership.org_id == org_id)
    return db.scalar(stmt)


@router.post("/session", response_model=SessionResponse)
def create_session(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> SessionResponse:
    normalized_email = payload.email.strip().lower()
    if not normalized_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email is required")

    user = db.scalar(
        select(User).where(
            User.deleted_at.is_(None),
            func.lower(User.email) == normalized_email,
        )
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    membership = _get_membership(db=db, user_id=user.id, org_id=payload.org_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="org membership required")

    token = create_session_token(user_id=user.id, org_id=membership.org_id, role=membership.role)
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.auth_session_ttl_seconds,
        path="/",
    )

    return SessionResponse(user_id=user.id, org_id=membership.org_id, role=membership.role.value)


@router.get("/session", response_model=SessionInfoResponse)
def get_session(request: Request, db: Session = Depends(get_db)) -> SessionInfoResponse:
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return SessionInfoResponse(authenticated=False)

    payload = verify_session_token(token)
    if payload is None:
        return SessionInfoResponse(authenticated=False)

    try:
        user_id = uuid.UUID(str(payload["sub"]))
        org_id = uuid.UUID(str(payload["org"]))
    except ValueError:
        return SessionInfoResponse(authenticated=False)

    membership = _get_membership(db=db, user_id=user_id, org_id=org_id)
    if membership is None:
        return SessionInfoResponse(authenticated=False)

    return SessionInfoResponse(
        authenticated=True,
        session=SessionResponse(user_id=user_id, org_id=org_id, role=membership.role.value),
    )


@router.delete("/session", response_model=SessionInfoResponse)
def delete_session(response: Response) -> SessionInfoResponse:
    response.delete_cookie(key=settings.auth_cookie_name, path="/")
    return SessionInfoResponse(authenticated=False)
