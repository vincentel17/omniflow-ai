from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..auth_password import generate_reset_token, hash_password, hash_reset_token, verify_password
from ..auth_session import create_session_token, verify_session_token
from ..db import get_db
from ..models import AuthCredential, Membership, Org, PasswordResetToken, Role, User
from ..settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str | None = None
    org_id: uuid.UUID | None = None


class SessionResponse(BaseModel):
    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str


class SessionInfoResponse(BaseModel):
    authenticated: bool
    session: SessionResponse | None = None


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str | None = None
    org_name: str | None = None


class RegisterResponse(BaseModel):
    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str


class PasswordResetRequestResponse(BaseModel):
    accepted: bool
    reset_token_preview: str | None = None


class PasswordResetConfirmResponse(BaseModel):
    reset: bool


class OrgOption(BaseModel):
    org_id: uuid.UUID
    org_name: str
    role: str


class OrgLookupResponse(BaseModel):
    items: list[OrgOption]


def _get_membership(db: Session, user_id: uuid.UUID, org_id: uuid.UUID | None) -> Membership | None:
    stmt = (
        select(Membership)
        .where(Membership.user_id == user_id, Membership.deleted_at.is_(None))
        .order_by(Membership.created_at.asc())
    )
    if org_id:
        stmt = stmt.where(Membership.org_id == org_id)
    return db.scalar(stmt)


def _validate_password_rules(password: str) -> None:
    if len(password) < 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="password must be at least 10 characters")


def _normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid email")
    return normalized


def _set_session_cookie(response: Response, user_id: uuid.UUID, org_id: uuid.UUID, role: Role) -> SessionResponse:
    token = create_session_token(user_id=user_id, org_id=org_id, role=role)
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=settings.auth_session_ttl_seconds,
        path="/",
    )
    return SessionResponse(user_id=user_id, org_id=org_id, role=role.value)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    normalized_email = _normalize_email(payload.email)
    _validate_password_rules(payload.password)

    user = db.scalar(select(User).where(User.deleted_at.is_(None), func.lower(User.email) == normalized_email))
    if user is None:
        user = User(email=normalized_email, full_name=(payload.full_name or "").strip() or None)
        db.add(user)
        db.flush()

    existing_credential = db.scalar(select(AuthCredential).where(AuthCredential.user_id == user.id))
    if existing_credential is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="credential already exists")

    credential = AuthCredential(user_id=user.id, password_hash=hash_password(payload.password))
    db.add(credential)

    membership = _get_membership(db=db, user_id=user.id, org_id=None)
    if membership is None:
        org_name = (payload.org_name or "").strip() or f"{normalized_email.split('@')[0]} org"
        org = Org(name=org_name)
        db.add(org)
        db.flush()
        membership = Membership(org_id=org.id, user_id=user.id, role=Role.OWNER)
        db.add(membership)

    db.commit()
    return RegisterResponse(user_id=user.id, org_id=membership.org_id, role=membership.role.value)


@router.post("/session", response_model=SessionResponse)
def create_session(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> SessionResponse:
    normalized_email = _normalize_email(payload.email)
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

    credential = db.scalar(select(AuthCredential).where(AuthCredential.user_id == user.id))
    if credential is not None:
        if not payload.password or not verify_password(payload.password, credential.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    elif settings.app_env != "development":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    membership = _get_membership(db=db, user_id=user.id, org_id=payload.org_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="org membership required")

    return _set_session_cookie(response=response, user_id=user.id, org_id=membership.org_id, role=membership.role)


@router.post("/org-options", response_model=OrgLookupResponse)
def list_org_options(payload: LoginRequest, db: Session = Depends(get_db)) -> OrgLookupResponse:
    normalized_email = _normalize_email(payload.email)
    user = db.scalar(select(User).where(User.deleted_at.is_(None), func.lower(User.email) == normalized_email))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    credential = db.scalar(select(AuthCredential).where(AuthCredential.user_id == user.id))
    if credential is not None:
        if not payload.password or not verify_password(payload.password, credential.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    elif settings.app_env != "development":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    rows = db.execute(
        select(Membership.org_id, Membership.role, Org.name)
        .join(Org, Org.id == Membership.org_id)
        .where(Membership.user_id == user.id, Membership.deleted_at.is_(None))
        .order_by(Membership.created_at.asc())
    ).all()
    items = [OrgOption(org_id=row[0], role=row[1].value, org_name=row[2]) for row in rows]
    return OrgLookupResponse(items=items)


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


@router.post("/password-reset/request", response_model=PasswordResetRequestResponse)
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> PasswordResetRequestResponse:
    normalized_email = _normalize_email(payload.email)
    user = db.scalar(select(User).where(User.deleted_at.is_(None), func.lower(User.email) == normalized_email))
    if user is None:
        return PasswordResetRequestResponse(accepted=True)

    credential = db.scalar(select(AuthCredential).where(AuthCredential.user_id == user.id))
    if credential is None:
        return PasswordResetRequestResponse(accepted=True)

    token = generate_reset_token()
    token_hash = hash_reset_token(token)
    expires_at = datetime.now(UTC) + timedelta(minutes=30)

    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=datetime.now(UTC))
    )
    db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    db.commit()

    if settings.app_env == "production" and not settings.password_reset_preview_in_production:
        return PasswordResetRequestResponse(accepted=True)
    return PasswordResetRequestResponse(accepted=True, reset_token_preview=token)


@router.post("/password-reset/confirm", response_model=PasswordResetConfirmResponse)
def confirm_password_reset(payload: PasswordResetConfirmRequest, db: Session = Depends(get_db)) -> PasswordResetConfirmResponse:
    _validate_password_rules(payload.new_password)
    token_hash = hash_reset_token(payload.token.strip())
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    if row is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired token")
    if row.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired token")
    if row.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired token")

    credential = db.scalar(select(AuthCredential).where(AuthCredential.user_id == row.user_id))
    if credential is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="credential missing")

    credential.password_hash = hash_password(payload.new_password)
    row.used_at = datetime.now(UTC)
    db.commit()
    return PasswordResetConfirmResponse(reset=True)

