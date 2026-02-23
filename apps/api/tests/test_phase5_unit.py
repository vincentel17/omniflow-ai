from __future__ import annotations

import uuid

from packages.policy import PolicyEngine
from packages.schemas import PresenceAuditInputJSON

from app.models import ReputationReview, ReputationSource
from app.services.phase5 import (
    build_presence_report,
    build_review_response_draft,
    build_seo_content,
    fetch_website_snapshot,
    score_review_sentiment,
)


def test_website_auditor_respects_robots_disallow(monkeypatch) -> None:
    monkeypatch.setattr("app.services.phase5._robots_allows_homepage", lambda url, timeout_seconds=2.5: False)
    result = fetch_website_snapshot("https://example.com")
    assert result["allowed"] is False
    assert result["reason"] == "robots_disallow"


def test_presence_scoring_is_stable() -> None:
    report = build_presence_report(
        audit_input=PresenceAuditInputJSON(
            providers_to_audit=["gbp"],
            account_refs={},
            run_mode="manual",
        ),
        snapshots=[
            {
                "provider": "gbp",
                "account_ref": "default",
                "categories_present": False,
                "posts_last_30_days": 0,
                "services_count": 3,
                "hours_present": True,
            }
        ],
    )
    assert report.overall_score == 70
    assert report.category_scores["profile"] == 85
    assert len(report.findings) >= 2


def test_sentiment_scoring_mock_is_deterministic() -> None:
    negative = score_review_sentiment("Never again, slow response and bad pricing.", 1)
    assert negative.urgency == "high"
    assert "timeliness" in negative.labels

    positive = score_review_sentiment("Great staff and fast service.", 5)
    assert positive.urgency == "low"
    assert "staff" in positive.labels


def test_policy_applies_to_seo_and_review_draft() -> None:
    policy = PolicyEngine(
        pack_slug="test",
        rules={
            "content": {"prohibited_words": ["consultation"]},
            "risk": {"overrides": {"seo_generate": "TIER_2", "review_response_draft": "TIER_3"}},
            "actions": {"blocked": []},
        },
    )
    seo_content, warnings, risk_tier = build_seo_content(
        title="Sample Title",
        slug="sample-title",
        keyword="sample service",
        location="seattle",
        policy=policy,
    )
    assert "consultation" in seo_content.body_markdown.lower()
    assert warnings
    assert risk_tier.value == "TIER_2"

    review = ReputationReview(
        org_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        source=ReputationSource.MANUAL_IMPORT,
        external_id=None,
        reviewer_name_masked="A***e",
        rating=1,
        review_text="slow and disappointing",
        review_text_hash="x",
        sentiment_json={},
        responded_at=None,
    )
    draft = build_review_response_draft(review=review, policy=policy)
    assert draft.risk_tier == "TIER_3"
