from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

from .models import Role
from .settings import settings


def _to_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _from_base64url(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _secret_bytes() -> bytes:
    raw = settings.token_encryption_key.encode("utf-8")
    try:
        return base64.b64decode(raw, validate=True)
    except Exception:
        return raw


def create_session_token(user_id: uuid.UUID, org_id: uuid.UUID, role: Role, ttl_seconds: int = 60 * 60 * 8) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org": str(org_id),
        "role": role.value,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = _to_base64url(payload_bytes)
    signature = hmac.new(_secret_bytes(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    signature_b64 = _to_base64url(signature)
    return f"{payload_b64}.{signature_b64}"


def verify_session_token(token: str) -> dict[str, Any] | None:
    try:
        payload_b64, signature_b64 = token.split(".", maxsplit=1)
    except ValueError:
        return None

    expected_signature = hmac.new(_secret_bytes(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    try:
        actual_signature = _from_base64url(signature_b64)
    except Exception:
        return None

    if not hmac.compare_digest(expected_signature, actual_signature):
        return None

    try:
        payload = json.loads(_from_base64url(payload_b64).decode("utf-8"))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp <= int(time.time()):
        return None

    required_fields = ("sub", "org", "role")
    if any(field not in payload for field in required_fields):
        return None

    return payload
