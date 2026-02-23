from __future__ import annotations

import uuid

import pytest

from app.services.org_settings import DEFAULT_ORG_SETTINGS, normalize_settings
from app.services.rate_limit import enforce_org_rate_limit


def test_phase8_org_settings_normalization_defaults() -> None:
    payload = normalize_settings({})
    assert payload["enable_auto_posting"] is False
    assert payload["enable_auto_lead_routing"] is True
    assert payload["connector_mode"] in {"mock", "live"}
    assert payload["max_auto_approve_tier"] == DEFAULT_ORG_SETTINGS["max_auto_approve_tier"]


def test_phase8_org_settings_normalization_clamps_tier() -> None:
    payload = normalize_settings({"max_auto_approve_tier": 99, "connector_mode": "invalid"})
    assert payload["max_auto_approve_tier"] == 4
    assert payload["connector_mode"] in {"mock", "live"}


def test_phase8_rate_limiter_returns_429_deterministically(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeRedis:
        def __init__(self) -> None:
            self.calls: dict[str, int] = {}

        def incr(self, key: str) -> int:
            self.calls[key] = self.calls.get(key, 0) + 1
            return self.calls[key]

        def expire(self, key: str, ttl: int) -> bool:
            return True

    fake = _FakeRedis()
    monkeypatch.setattr("app.services.rate_limit.get_redis_client", lambda: fake)

    org_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    enforce_org_rate_limit(org_id=org_id, bucket_name="unit_limit", max_requests=1, window_seconds=60)
    with pytest.raises(Exception) as exc_info:  # HTTPException
        enforce_org_rate_limit(org_id=org_id, bucket_name="unit_limit", max_requests=1, window_seconds=60)
    assert "rate limit exceeded" in str(exc_info.value)
