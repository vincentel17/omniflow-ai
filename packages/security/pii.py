from __future__ import annotations

import re
from typing import Any

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})")
_TOKEN_RE = re.compile(r"\b(?:access|refresh|api|secret|token)[_-]?(?:key|token)?\b", re.IGNORECASE)


_FIELD_CATEGORY_MAP: dict[str, str] = {
    "email": "contact_info",
    "phone": "contact_info",
    "mobile": "contact_info",
    "address": "personal_identifier",
    "name": "personal_identifier",
    "first_name": "personal_identifier",
    "last_name": "personal_identifier",
    "full_name": "personal_identifier",
    "ssn": "personal_identifier",
    "tax": "financial",
    "card": "financial",
    "bank": "financial",
    "routing": "financial",
    "diagnosis": "health_related",
    "health": "health_related",
    "medical": "health_related",
    "condition": "health_related",
    "token": "system_secret",
    "secret": "system_secret",
    "password": "system_secret",
    "api_key": "system_secret",
    "refresh_token": "system_secret",
    "access_token": "system_secret",
}


def classify_field(field_name: str, value: Any) -> str:
    normalized = field_name.strip().lower()
    for key, category in _FIELD_CATEGORY_MAP.items():
        if key in normalized:
            return category

    if isinstance(value, str):
        pii = detect_pii(value)
        if pii["contains_token"]:
            return "system_secret"
        if pii["contains_health"]:
            return "health_related"
        if pii["contains_email"] or pii["contains_phone"]:
            return "contact_info"

    return "public"


def detect_pii(text: str) -> dict[str, bool]:
    lowered = text.lower()
    return {
        "contains_email": bool(_EMAIL_RE.search(text)),
        "contains_phone": bool(_PHONE_RE.search(text)),
        "contains_token": bool(_TOKEN_RE.search(lowered)),
        "contains_health": any(token in lowered for token in ("diagnosis", "medical", "patient", "hipaa")),
    }


def redact_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    redacted = _EMAIL_RE.sub("[redacted-email]", value)
    redacted = _PHONE_RE.sub("[redacted-phone]", redacted)

    if _TOKEN_RE.search(value):
        return "[redacted-secret]"
    return redacted


def redact_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        category = classify_field(key, value)
        if category == "system_secret":
            sanitized[key] = "[redacted-secret]"
            continue
        if isinstance(value, dict):
            sanitized[key] = redact_mapping(value)
            continue
        if isinstance(value, list):
            sanitized[key] = [redact_value(item) for item in value]
            continue
        sanitized[key] = redact_value(value)
    return sanitized
