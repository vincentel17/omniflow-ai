from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import OrgSettings
from ..settings import settings

DEFAULT_ORG_SETTINGS: dict[str, Any] = {
    "enable_auto_posting": False,
    "enable_auto_reply": False,
    "enable_auto_lead_routing": True,
    "enable_auto_nurture_apply": False,
    "enable_scheduled_audits": True,
    "enable_seo_generation": True,
    "enable_review_response_drafts": True,
    "connector_mode": "mock",
    "providers_enabled_json": {
        "gbp_publish_enabled": False,
        "meta_publish_enabled": False,
        "linkedin_publish_enabled": False,
        "gbp_inbox_enabled": False,
        "meta_inbox_enabled": False,
        "linkedin_inbox_enabled": False,
    },
    "ai_mode": "mock",
    "max_auto_approve_tier": 1,
}


def _safe_bool(value: Any, fallback: bool) -> bool:
    return value if isinstance(value, bool) else fallback


def _safe_mode(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value in {"mock", "live"}:
        return value
    return fallback


def _safe_tier(value: Any, fallback: int) -> int:
    if isinstance(value, int):
        return max(0, min(4, value))
    return fallback


def _safe_provider_flags(value: Any) -> dict[str, bool]:
    defaults = dict(DEFAULT_ORG_SETTINGS["providers_enabled_json"])
    if not isinstance(value, dict):
        return defaults
    normalized: dict[str, bool] = {}
    for key, default in defaults.items():
        raw = value.get(key)
        normalized[key] = raw if isinstance(raw, bool) else bool(default)
    return normalized


def normalize_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    source = raw or {}
    normalized = dict(DEFAULT_ORG_SETTINGS)
    normalized["enable_auto_posting"] = _safe_bool(source.get("enable_auto_posting"), DEFAULT_ORG_SETTINGS["enable_auto_posting"])
    normalized["enable_auto_reply"] = _safe_bool(source.get("enable_auto_reply"), DEFAULT_ORG_SETTINGS["enable_auto_reply"])
    normalized["enable_auto_lead_routing"] = _safe_bool(
        source.get("enable_auto_lead_routing"),
        DEFAULT_ORG_SETTINGS["enable_auto_lead_routing"],
    )
    normalized["enable_auto_nurture_apply"] = _safe_bool(
        source.get("enable_auto_nurture_apply"),
        DEFAULT_ORG_SETTINGS["enable_auto_nurture_apply"],
    )
    normalized["enable_scheduled_audits"] = _safe_bool(
        source.get("enable_scheduled_audits"),
        DEFAULT_ORG_SETTINGS["enable_scheduled_audits"],
    )
    normalized["enable_seo_generation"] = _safe_bool(
        source.get("enable_seo_generation"),
        DEFAULT_ORG_SETTINGS["enable_seo_generation"],
    )
    normalized["enable_review_response_drafts"] = _safe_bool(
        source.get("enable_review_response_drafts"),
        DEFAULT_ORG_SETTINGS["enable_review_response_drafts"],
    )
    normalized["connector_mode"] = _safe_mode(
        source.get("connector_mode"),
        settings.connector_mode if settings.connector_mode in {"mock", "live"} else "mock",
    )
    normalized["providers_enabled_json"] = _safe_provider_flags(source.get("providers_enabled_json"))
    normalized["ai_mode"] = _safe_mode(
        source.get("ai_mode"),
        settings.ai_mode if settings.ai_mode in {"mock", "live"} else "mock",
    )
    normalized["max_auto_approve_tier"] = _safe_tier(
        source.get("max_auto_approve_tier"),
        int(DEFAULT_ORG_SETTINGS["max_auto_approve_tier"]),
    )
    if isinstance(source.get("automation_weights"), dict):
        normalized["automation_weights"] = source["automation_weights"]
    return normalized


def get_or_create_org_settings(db: Session, org_id: uuid.UUID) -> OrgSettings:
    row = db.scalar(select(OrgSettings).where(OrgSettings.org_id == org_id, OrgSettings.deleted_at.is_(None)))
    if row is None:
        row = OrgSettings(org_id=org_id, settings_json=dict(DEFAULT_ORG_SETTINGS))
        db.add(row)
        db.flush()
    else:
        row.settings_json = normalize_settings(row.settings_json)
        db.flush()
    return row


def get_org_settings_payload(db: Session, org_id: uuid.UUID) -> dict[str, Any]:
    row = get_or_create_org_settings(db=db, org_id=org_id)
    return normalize_settings(row.settings_json)


def update_org_settings_payload(db: Session, org_id: uuid.UUID, patch: dict[str, Any]) -> dict[str, Any]:
    row = get_or_create_org_settings(db=db, org_id=org_id)
    merged = normalize_settings({**row.settings_json, **patch})
    row.settings_json = merged
    db.flush()
    return merged


def is_feature_enabled(db: Session, org_id: uuid.UUID, key: str, fallback: bool = False) -> bool:
    payload = get_org_settings_payload(db=db, org_id=org_id)
    value = payload.get(key)
    return value if isinstance(value, bool) else fallback


def connector_mode_for_org(db: Session, org_id: uuid.UUID) -> str:
    payload = get_org_settings_payload(db=db, org_id=org_id)
    return _safe_mode(payload.get("connector_mode"), settings.connector_mode)


def ai_mode_for_org(db: Session, org_id: uuid.UUID) -> str:
    payload = get_org_settings_payload(db=db, org_id=org_id)
    return _safe_mode(payload.get("ai_mode"), settings.ai_mode)


def assert_feature_enabled(db: Session, org_id: uuid.UUID, feature_key: str, detail: str) -> None:
    if not is_feature_enabled(db=db, org_id=org_id, key=feature_key, fallback=False):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


_PROVIDER_PREFIX = {
    "google-business-profile": "gbp",
    "meta": "meta",
    "linkedin": "linkedin",
}


def provider_enabled_for_org(
    db: Session,
    org_id: uuid.UUID,
    provider: str,
    operation: str,
) -> bool:
    payload = get_org_settings_payload(db=db, org_id=org_id)
    if _safe_mode(payload.get("connector_mode"), settings.connector_mode) != "live":
        return False
    prefix = _PROVIDER_PREFIX.get(provider)
    if prefix is None:
        return False
    op = "publish" if operation == "publish" else "inbox"
    key = f"{prefix}_{op}_enabled"
    providers_enabled = payload.get("providers_enabled_json")
    if not isinstance(providers_enabled, dict):
        return False
    value = providers_enabled.get(key)
    return value is True
