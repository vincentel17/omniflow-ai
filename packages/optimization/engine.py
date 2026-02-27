from __future__ import annotations

from collections import defaultdict
from statistics import mean

from .schema import (
    AdBudgetRecommendationResult,
    FeatureVector,
    NextBestActionResult,
    NurtureRecommendationResult,
    PostingOptimizationResult,
    PredictiveLeadScoreResult,
)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def extract_features(*, org_id: str, lead_id: str | None, payloads: list[dict[str, object]]) -> FeatureVector:
    message_count = 0
    response_minutes: list[float] = []
    clicks = 0
    tags_count = 0

    for payload in payloads:
        if payload.get("event_type") == "INBOX_INGESTED":
            message_count += 1

        response_value = payload.get("response_minutes")
        if isinstance(response_value, (int, float)) and not isinstance(response_value, bool):
            response_minutes.append(float(response_value))

        clicks_value = payload.get("clicks")
        if isinstance(clicks_value, (int, float)) and not isinstance(clicks_value, bool):
            clicks += int(clicks_value)

        tags = payload.get("tags")
        if isinstance(tags, list):
            tags_count += len(tags)

    avg_response = mean(response_minutes) if response_minutes else 0.0
    features = {
        "message_count": float(message_count),
        "avg_response_minutes": float(avg_response),
        "link_clicks": float(clicks),
        "tags_count": float(tags_count),
    }
    return FeatureVector(org_id=org_id, lead_id=lead_id, feature_json=features)


def compute_predictive_score(feature_vector: FeatureVector) -> PredictiveLeadScoreResult:
    features = feature_vector.feature_json
    message_count = features.get("message_count", 0.0)
    avg_response = features.get("avg_response_minutes", 0.0)
    clicks = features.get("link_clicks", 0.0)
    tags_count = features.get("tags_count", 0.0)

    raw = (message_count * 0.2) + (clicks * 0.25) + (tags_count * 0.1) - (avg_response / 180.0)
    probability = _clamp(0.5 + raw, 0.01, 0.99)

    feature_importance = {
        "message_count": 0.2,
        "link_clicks": 0.25,
        "tags_count": 0.1,
        "avg_response_minutes": -0.15,
    }
    stage_probs = {
        "qualified": round(probability, 4),
        "closed": round(_clamp(probability * 0.55, 0.0, 1.0), 4),
    }
    return PredictiveLeadScoreResult(
        score_probability=round(probability, 4),
        feature_importance_json=feature_importance,
        predicted_stage_probability_json=stage_probs,
        explanation="Deterministic weighted blend of engagement, click-through, and response latency.",
    )


def combine_lead_score(*, rule_score: int, predictive_score: float, rule_weight: float = 0.6, predictive_weight: float = 0.4) -> int:
    normalized_rule = _clamp(rule_score / 100.0, 0.0, 1.0)
    combined = (normalized_rule * rule_weight) + (predictive_score * predictive_weight)
    return int(round(_clamp(combined * 100.0, 0.0, 100.0)))


def compute_posting_optimization(*, channel: str, samples: list[dict[str, object]]) -> PostingOptimizationResult:
    buckets: dict[tuple[int, int], list[float]] = defaultdict(list)
    for row in samples:
        day = row.get("day_of_week")
        hour = row.get("hour")
        value = row.get("conversion_rate")
        if isinstance(day, int) and isinstance(hour, int) and isinstance(value, (int, float)):
            buckets[(day, hour)].append(float(value))

    if not buckets:
        return PostingOptimizationResult(
            channel=channel,
            best_day_of_week=2,
            best_hour=10,
            confidence_score=0.2,
            explanation="Insufficient samples; fallback weekday morning baseline used.",
        )

    best_key = max(buckets.keys(), key=lambda key: mean(buckets[key]))
    best_value = mean(buckets[best_key])
    overall = mean([mean(values) for values in buckets.values()])
    confidence = _clamp(0.5 + (best_value - overall), 0.05, 0.99)
    return PostingOptimizationResult(
        channel=channel,
        best_day_of_week=best_key[0],
        best_hour=best_key[1],
        confidence_score=round(confidence, 4),
        explanation="Selected highest observed conversion window by weekday/hour cohort.",
    )


def build_nurture_recommendation(*, touch_intervals_minutes: list[int], stage_progress_rate: float) -> NurtureRecommendationResult:
    base = 120
    if touch_intervals_minutes:
        base = int(round(mean(touch_intervals_minutes)))
    modifier = 0.85 if stage_progress_rate >= 0.4 else 1.2
    first = max(15, int(base * modifier))
    sequence = [first, int(first * 2), int(first * 4)]
    return NurtureRecommendationResult(
        recommended_delays_minutes=sequence,
        explanation="Cadence adapts to observed stage progression velocity and historical touch intervals.",
    )


def build_ad_budget_recommendation(*, current_daily_budget: float, cpl: float, benchmark_cpl: float, campaign_cap: float) -> AdBudgetRecommendationResult:
    efficiency = 0.0 if benchmark_cpl <= 0 else (benchmark_cpl - cpl) / benchmark_cpl
    proposed = current_daily_budget * (1.0 + (efficiency * 0.25))
    recommended = _clamp(proposed, 1.0, campaign_cap)
    projected_cpl = max(0.01, cpl * (1.0 - (efficiency * 0.1)))
    return AdBudgetRecommendationResult(
        recommended_daily_budget=round(recommended, 2),
        projected_cpl=round(projected_cpl, 2),
        reasoning_json={
            "current_daily_budget": round(current_daily_budget, 2),
            "current_cpl": round(cpl, 2),
            "benchmark_cpl": round(benchmark_cpl, 2),
            "efficiency_delta": round(efficiency, 4),
        },
        explanation="Budget recommendation is constrained by org caps and relative CPL efficiency.",
    )


def workflow_recommendations(*, workflow_stats: list[dict[str, object]]) -> list[dict[str, object]]:
    suggestions: list[dict[str, object]] = []
    for row in workflow_stats:
        key = str(row.get("workflow_key") or "workflow")
        success_rate = _to_float(row.get("success_rate"), 0.0)
        approval_latency = _to_float(row.get("approval_latency_minutes"), 0.0)
        if success_rate < 0.7:
            suggestions.append(
                {
                    "workflow_key": key,
                    "suggestion": "Review failing action sequence and add retry-safe guard conditions.",
                    "priority": "high",
                }
            )
        if approval_latency > 120:
            suggestions.append(
                {
                    "workflow_key": key,
                    "suggestion": "Approval queue latency is high; split high-risk actions from low-risk drafts.",
                    "priority": "medium",
                }
            )
    return suggestions


def build_next_best_action(*, entity_type: str, inactivity_hours: float, predictive_score: float, stage: str | None = None) -> NextBestActionResult:
    if entity_type == "lead" and predictive_score >= 0.7 and inactivity_hours >= 24:
        return NextBestActionResult(
            action_type="call",
            rationale="High-conversion lead is inactive; direct outreach is likely to recover momentum.",
            expected_uplift=0.18,
            confidence_score=0.79,
        )
    if entity_type == "deal" and stage in {"under_contract", "inspection"}:
        return NextBestActionResult(
            action_type="create_checklist_task",
            rationale="Deal stage indicates compliance-sensitive handoff; checklist action reduces slippage.",
            expected_uplift=0.12,
            confidence_score=0.73,
        )
    return NextBestActionResult(
        action_type="send_message",
        rationale="No high-risk trigger detected; gentle follow-up is the default reversible action.",
        expected_uplift=0.07,
        confidence_score=0.62,
    )


def detect_model_drift(*, baseline_metric: float, recent_metric: float, threshold: float = 0.1) -> tuple[bool, str]:
    if baseline_metric <= 0:
        return False, "baseline unavailable"
    drop = (baseline_metric - recent_metric) / baseline_metric
    if drop > threshold:
        return True, f"metric dropped by {drop:.2%} (threshold {threshold:.0%})"
    return False, f"metric stable ({drop:.2%} change)"
