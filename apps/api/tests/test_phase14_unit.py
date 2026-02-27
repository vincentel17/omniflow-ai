from __future__ import annotations

from packages.optimization.engine import (
    build_ad_budget_recommendation,
    compute_posting_optimization,
    compute_predictive_score,
    extract_features,
)


def test_phase14_feature_extraction_is_deterministic() -> None:
    payloads = [
        {"event_type": "INBOX_INGESTED", "response_minutes": 15, "clicks": 2, "tags": ["hot", "buyer"]},
        {"event_type": "INBOX_INGESTED", "response_minutes": 30, "clicks": 1, "tags": ["repeat"]},
    ]
    vec_a = extract_features(org_id="org-1", lead_id="lead-1", payloads=payloads)
    vec_b = extract_features(org_id="org-1", lead_id="lead-1", payloads=payloads)
    assert vec_a.feature_json == vec_b.feature_json


def test_phase14_predictive_scoring_is_deterministic() -> None:
    vector = extract_features(
        org_id="org-1",
        lead_id="lead-1",
        payloads=[{"event_type": "INBOX_INGESTED", "response_minutes": 20, "clicks": 3, "tags": ["qualified"]}],
    )
    score_a = compute_predictive_score(vector)
    score_b = compute_predictive_score(vector)
    assert score_a.score_probability == score_b.score_probability
    assert score_a.explanation


def test_phase14_post_timing_selects_best_hour() -> None:
    samples = [
        {"day_of_week": 2, "hour": 10, "conversion_rate": 0.2},
        {"day_of_week": 2, "hour": 10, "conversion_rate": 0.18},
        {"day_of_week": 3, "hour": 17, "conversion_rate": 0.05},
    ]
    result = compute_posting_optimization(channel="meta", samples=samples)
    assert result.best_day_of_week == 2
    assert result.best_hour == 10


def test_phase14_budget_recommendation_respects_cap() -> None:
    recommendation = build_ad_budget_recommendation(
        current_daily_budget=120.0,
        cpl=1.5,
        benchmark_cpl=3.0,
        campaign_cap=130.0,
    )
    assert recommendation.recommended_daily_budget <= 130.0
    assert recommendation.projected_cpl >= 0.01
