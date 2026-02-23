from __future__ import annotations

from datetime import date

import pytest

from app.models import RiskTier
from app.services.ai import generate_campaign_plan, generate_content_items
from app.services.phase3 import should_auto_approve
from app.settings import settings


def test_ai_mock_mode_returns_valid_plan_and_content() -> None:
    original_mode = settings.ai_mode
    settings.ai_mode = "mock"
    try:
        plan = generate_campaign_plan(
            week_start_date=date(2026, 2, 23),
            channels=["linkedin"],
            objectives=["Drive attributable pipeline"],
        )
        assert plan.posts
        content_items = generate_content_items(plan)
        assert content_items
        assert content_items[0].caption
        assert content_items[0].channel == "linkedin"
    finally:
        settings.ai_mode = original_mode


@pytest.mark.parametrize(
    ("tier", "max_tier", "expected"),
    [
        (RiskTier.TIER_0, 1, True),
        (RiskTier.TIER_1, 1, True),
        (RiskTier.TIER_2, 1, False),
        (RiskTier.TIER_3, 3, True),
    ],
)
def test_auto_approval_tier_logic(tier: RiskTier, max_tier: int, expected: bool) -> None:
    assert should_auto_approve(risk_tier=tier, auto_approve_tiers_max=max_tier) is expected
