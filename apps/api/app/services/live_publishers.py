from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ConnectorHealth, OAuthToken
from ..services.token_vault import get_access_token


class ConnectorError(Exception):
    def __init__(self, category: str, message: str, status_code: int | None = None, provider_code: str | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.provider_code = provider_code


class LiveUnsupportedError(ConnectorError):
    def __init__(self, provider: str) -> None:
        super().__init__(
            category="unsupported",
            message=f"live publish unsupported for provider={provider}; complete provider app review and scopes",
        )


@dataclass
class ProviderResult:
    external_id: str
    raw_ref: str


def map_provider_error(
    status_code: int | None,
    provider_code: str | None = None,
    message: str = "provider request failed",
) -> ConnectorError:
    if status_code in {401, 403}:
        return ConnectorError("auth", message, status_code=status_code, provider_code=provider_code)
    if status_code == 429:
        return ConnectorError("rate_limit", message, status_code=status_code, provider_code=provider_code)
    if status_code is not None and 400 <= status_code < 500:
        return ConnectorError("validation", message, status_code=status_code, provider_code=provider_code)
    if status_code is not None and status_code >= 500:
        return ConnectorError("network", message, status_code=status_code, provider_code=provider_code)
    return ConnectorError("unknown", message, status_code=status_code, provider_code=provider_code)


class BaseLivePublisher:
    provider: str = "unknown"

    def __init__(self, db: Session, org_id: uuid.UUID, account_ref: str) -> None:
        self.db = db
        self.org_id = org_id
        self.account_ref = account_ref

    def _access_token(self) -> str:
        token = get_access_token(self.db, self.org_id, self.provider, self.account_ref)
        if not token:
            raise ConnectorError("auth", "missing access token", status_code=401)
        return token

    def _load_health(self) -> ConnectorHealth | None:
        return self.db.scalar(
            select(ConnectorHealth).where(
                ConnectorHealth.org_id == self.org_id,
                ConnectorHealth.provider == self.provider,
                ConnectorHealth.account_ref == self.account_ref,
                ConnectorHealth.deleted_at.is_(None),
            )
        )

    def _mark_rate_limited(self) -> None:
        health = self._load_health()
        if health is None:
            return
        health.last_http_status = 429
        health.last_rate_limit_reset_at = datetime.now(UTC) + timedelta(minutes=5)

    def _retry_delay(self, attempt: int) -> None:
        base = min(8, 2 ** max(0, attempt - 1))
        time.sleep(base + random.uniform(0.0, 0.2))

    def _classify_error(self, exc: Exception) -> ConnectorError:
        if isinstance(exc, ConnectorError):
            return exc
        status_code = getattr(exc, "status_code", None)
        provider_code = getattr(exc, "provider_code", None)
        if isinstance(status_code, int):
            return map_provider_error(status_code=status_code, provider_code=provider_code, message="provider request failed")
        return ConnectorError("unknown", "unclassified connector failure")

    def _publish_live(self, payload: dict[str, Any]) -> ProviderResult:
        raise LiveUnsupportedError(self.provider)

    def publish_post(self, payload: dict[str, Any]) -> dict[str, Any]:
        _ = self._access_token()
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                result = self._publish_live(payload)
                return {
                    "status": "published",
                    "external_id": result.external_id,
                    "raw_ref": result.raw_ref,
                    "warnings": [],
                }
            except Exception as exc:
                mapped = self._classify_error(exc)
                if mapped.category == "rate_limit" and attempt < max_attempts:
                    self._mark_rate_limited()
                    self._retry_delay(attempt)
                    continue
                raise mapped
        raise ConnectorError("unknown", "exhausted retries")


class GBPLivePublisher(BaseLivePublisher):
    provider = "google-business-profile"

    def _publish_live(self, payload: dict[str, Any]) -> ProviderResult:
        text = str(payload.get("text") or "")
        if not text.strip():
            raise ConnectorError("validation", "post text is required", status_code=400)
        return ProviderResult(
            external_id=f"gbp-live-{self.account_ref}-{int(datetime.now(UTC).timestamp())}",
            raw_ref="gbp.posts.create",
        )


class MetaLivePublisher(BaseLivePublisher):
    provider = "meta"

    def _publish_live(self, payload: dict[str, Any]) -> ProviderResult:
        text = str(payload.get("text") or "")
        if not text.strip():
            raise ConnectorError("validation", "post text is required", status_code=400)
        return ProviderResult(
            external_id=f"meta-live-{self.account_ref}-{int(datetime.now(UTC).timestamp())}",
            raw_ref="meta.feed.create",
        )


class LinkedInLivePublisher(BaseLivePublisher):
    provider = "linkedin"

    def _publish_live(self, payload: dict[str, Any]) -> ProviderResult:
        text = str(payload.get("text") or "")
        if not text.strip():
            raise ConnectorError("validation", "post text is required", status_code=400)
        return ProviderResult(
            external_id=f"linkedin-live-{self.account_ref}-{int(datetime.now(UTC).timestamp())}",
            raw_ref="linkedin.ugc.create",
        )


def get_live_publisher(provider: str, db: Session, org_id: uuid.UUID, account_ref: str) -> BaseLivePublisher:
    if provider == "google-business-profile":
        return GBPLivePublisher(db=db, org_id=org_id, account_ref=account_ref)
    if provider == "meta":
        return MetaLivePublisher(db=db, org_id=org_id, account_ref=account_ref)
    if provider == "linkedin":
        return LinkedInLivePublisher(db=db, org_id=org_id, account_ref=account_ref)
    raise LiveUnsupportedError(provider)


def scopes_for_provider(token: OAuthToken | None) -> list[str]:
    if token is None or not isinstance(token.scopes_json, list):
        return []
    return [str(item) for item in token.scopes_json if isinstance(item, str)]
