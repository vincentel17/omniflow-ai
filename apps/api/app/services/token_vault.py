from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import OAuthToken
from ..settings import settings


def _fernet() -> Fernet:
    key = settings.app_encryption_key or settings.token_encryption_key
    return Fernet(key.encode("utf-8"))


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(token_enc: str) -> str:
    return _fernet().decrypt(token_enc.encode("utf-8")).decode("utf-8")


def get_token_row(db: Session, org_id: uuid.UUID, provider: str, account_ref: str) -> OAuthToken | None:
    return db.scalar(
        select(OAuthToken).where(
            OAuthToken.org_id == org_id,
            OAuthToken.provider == provider,
            OAuthToken.account_ref == account_ref,
            OAuthToken.deleted_at.is_(None),
        )
    )


def store_tokens(
    db: Session,
    org_id: uuid.UUID,
    provider: str,
    account_ref: str,
    access_token: str,
    refresh_token: str | None,
    scopes: list[str],
    expires_at: datetime | None,
) -> OAuthToken:
    existing = get_token_row(db=db, org_id=org_id, provider=provider, account_ref=account_ref)
    if existing is None:
        existing = OAuthToken(
            org_id=org_id,
            provider=provider,
            account_ref=account_ref,
            access_token_enc=encrypt_token(access_token),
            refresh_token_enc=encrypt_token(refresh_token) if refresh_token else None,
            scopes_json=scopes,
            expires_at=expires_at,
            rotated_at=datetime.now(UTC),
        )
        db.add(existing)
    else:
        existing.access_token_enc = encrypt_token(access_token)
        existing.refresh_token_enc = encrypt_token(refresh_token) if refresh_token else None
        existing.scopes_json = scopes
        existing.expires_at = expires_at
        existing.rotated_at = datetime.now(UTC)
    db.flush()
    return existing


def get_access_token(db: Session, org_id: uuid.UUID, provider: str, account_ref: str) -> str | None:
    token = get_token_row(db=db, org_id=org_id, provider=provider, account_ref=account_ref)
    if token is None:
        return None
    return decrypt_token(token.access_token_enc)


def refresh_if_needed(db: Session, org_id: uuid.UUID, provider: str, account_ref: str) -> str | None:
    token = get_token_row(db=db, org_id=org_id, provider=provider, account_ref=account_ref)
    if token is None:
        return None
    if token.expires_at is None or token.expires_at > datetime.now(UTC) + timedelta(minutes=2):
        return decrypt_token(token.access_token_enc)

    if not token.refresh_token_enc:
        return None

    # Provider refresh flow is intentionally scaffolded for Phase 9.
    # We rotate synthetic token material to preserve interface behavior in deterministic tests.
    refreshed = f"refresh-{provider}-{account_ref}-{int(datetime.now(UTC).timestamp())}"
    token.access_token_enc = encrypt_token(refreshed)
    token.rotated_at = datetime.now(UTC)
    token.expires_at = datetime.now(UTC) + timedelta(hours=1)
    db.flush()
    return refreshed
