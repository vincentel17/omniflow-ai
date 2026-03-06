from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ConnectorHealth, ConnectorWorkflowRun, ReputationReview, ReputationSource
from ..services.live_publishers import ConnectorError, map_provider_error, missing_required_scopes
from ..services.phase5 import hash_review_text, mask_reviewer_name, score_review_sentiment
from ..services.token_vault import get_token_row, refresh_if_needed


@dataclass
class GBPReviewSyncResult:
    imported_count: int
    skipped_count: int
    external_ids: list[str]
    last_sync_at: datetime


def _sanitize_message(message: str) -> str:
    return " ".join(message.split())[:200]


def _load_health(db: Session, org_id: uuid.UUID, account_ref: str) -> ConnectorHealth:
    health = db.scalar(
        select(ConnectorHealth).where(
            ConnectorHealth.org_id == org_id,
            ConnectorHealth.provider == "google-business-profile",
            ConnectorHealth.account_ref == account_ref,
            ConnectorHealth.deleted_at.is_(None),
        )
    )
    if health is None:
        health = ConnectorHealth(org_id=org_id, provider="google-business-profile", account_ref=account_ref)
        db.add(health)
        db.flush()
    return health


def _mock_reviews_page(account_ref: str) -> list[dict[str, Any]]:
    suffix = account_ref.replace("/", "-")[:24] or "demo"
    return [
        {
            "name": f"reviews/{suffix}-1",
            "reviewer": {"displayName": "Pat Morgan"},
            "starRating": "FIVE",
            "comment": "Helpful team, fast response, and clear updates.",
            "createTime": "2026-01-20T15:00:00Z",
        },
        {
            "name": f"reviews/{suffix}-2",
            "reviewer": {"displayName": "Jamie Lee"},
            "starRating": "THREE",
            "comment": "Solid service overall, but there is room to improve follow-up.",
            "createTime": "2026-01-18T11:30:00Z",
        },
    ]


def _parse_star_rating(value: Any) -> int:
    if isinstance(value, int):
        return max(1, min(5, value))
    mapping = {
        "ONE": 1,
        "TWO": 2,
        "THREE": 3,
        "FOUR": 4,
        "FIVE": 5,
        "ONE_STAR": 1,
        "TWO_STAR": 2,
        "THREE_STAR": 3,
        "FOUR_STAR": 4,
        "FIVE_STAR": 5,
    }
    if isinstance(value, str):
        return mapping.get(value.strip().upper(), 3)
    return 3


def _normalize_review(item: dict[str, Any]) -> dict[str, Any]:
    external_id = str(item.get("reviewId") or item.get("name") or "")
    reviewer_raw = item.get("reviewer")
    reviewer: dict[str, Any] = reviewer_raw if isinstance(reviewer_raw, dict) else {}
    comment = str(item.get("comment") or item.get("commentText") or "")[:8000]
    return {
        "external_id": external_id or f"gbp-review-{hash_review_text(comment)[:16]}",
        "reviewer_name": str(reviewer.get("displayName") or item.get("reviewer_name") or "Anonymous"),
        "rating": _parse_star_rating(item.get("starRating") or item.get("rating")),
        "review_text": comment or "No review body provided.",
        "created_at": str(item.get("createTime") or item.get("updateTime") or ""),
    }


def _fetch_live_reviews_page(db: Session, org_id: uuid.UUID, account_ref: str) -> list[dict[str, Any]]:
    token = get_token_row(db=db, org_id=org_id, provider="google-business-profile", account_ref=account_ref)
    scopes = [str(scope) for scope in token.scopes_json] if token is not None and isinstance(token.scopes_json, list) else []
    missing_scopes = missing_required_scopes("google-business-profile", "inbox", scopes)
    if missing_scopes:
        raise ConnectorError("auth", f"missing scopes: {', '.join(missing_scopes)}", status_code=403)

    access_token = refresh_if_needed(db, org_id, "google-business-profile", account_ref)
    if not access_token:
        raise ConnectorError("reauth_required", "token refresh failed; re-auth required", status_code=401)

    url = f"https://mybusiness.googleapis.com/v4/{account_ref}/reviews"
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"pageSize": 10},
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        raise ConnectorError("network", "gbp request failed", status_code=503) from exc

    if response.status_code >= 400:
        raise map_provider_error(
            status_code=response.status_code,
            provider_code=None,
            message="gbp reviews sync failed",
        )
    payload = response.json()
    reviews = payload.get("reviews")
    if not isinstance(reviews, list):
        return []
    return [item for item in reviews if isinstance(item, dict)]


def sync_gbp_reviews_page(
    db: Session,
    *,
    org_id: uuid.UUID,
    account_ref: str,
    run: ConnectorWorkflowRun,
    mode: str,
) -> GBPReviewSyncResult:
    run.status = "in_progress"
    run.attempt_count = int(run.attempt_count or 0) + 1
    run.last_error = None
    health = _load_health(db=db, org_id=org_id, account_ref=account_ref)
    now = datetime.now(UTC)

    try:
        if mode == "live":
            items = _fetch_live_reviews_page(db=db, org_id=org_id, account_ref=account_ref)
        else:
            items = _mock_reviews_page(account_ref)

        imported_count = 0
        skipped_count = 0
        external_ids: list[str] = []
        for raw in items:
            normalized = _normalize_review(raw)
            existing = db.scalar(
                select(ReputationReview).where(
                    ReputationReview.org_id == org_id,
                    ReputationReview.source == ReputationSource.GBP,
                    ReputationReview.external_id == normalized["external_id"],
                    ReputationReview.deleted_at.is_(None),
                )
            )
            if existing is not None:
                skipped_count += 1
                external_ids.append(str(existing.external_id or ""))
                continue

            sentiment = score_review_sentiment(
                review_text=normalized["review_text"],
                rating=int(normalized["rating"]),
            )
            review = ReputationReview(
                org_id=org_id,
                source=ReputationSource.GBP,
                external_id=normalized["external_id"],
                reviewer_name_masked=mask_reviewer_name(normalized["reviewer_name"]),
                rating=int(normalized["rating"]),
                review_text=normalized["review_text"],
                review_text_hash=hash_review_text(normalized["review_text"]),
                sentiment_json=sentiment.model_dump(mode="json"),
                responded_at=None,
            )
            db.add(review)
            db.flush()
            imported_count += 1
            external_ids.append(normalized["external_id"])

        health.last_ok_at = now
        health.last_error_at = None
        health.last_error_msg = None
        health.last_http_status = None
        health.last_provider_error_code = None
        health.last_rate_limit_reset_at = None
        health.consecutive_failures = 0
        run.status = "completed"
        run.completed_at = now
        run.result_json = {
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "external_ids": external_ids,
            "mode": mode,
        }
        return GBPReviewSyncResult(
            imported_count=imported_count,
            skipped_count=skipped_count,
            external_ids=external_ids,
            last_sync_at=now,
        )
    except ConnectorError as exc:
        message = _sanitize_message(str(exc))
        health.last_error_at = now
        health.last_error_msg = message
        health.last_http_status = exc.status_code
        health.last_provider_error_code = exc.provider_code
        if exc.category == "rate_limit":
            health.last_rate_limit_reset_at = now
        run.status = "failed"
        run.last_error = message
        run.result_json = {
            "category": exc.category,
            "status_code": exc.status_code,
            "provider_code": exc.provider_code,
        }
        raise
