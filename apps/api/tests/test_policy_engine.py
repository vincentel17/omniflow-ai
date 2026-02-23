from __future__ import annotations

from app.services.policy import load_policy_engine


def test_generic_policy_allows_content() -> None:
    engine = load_policy_engine("generic")
    result = engine.validate_content("Completely neutral listing copy")
    assert result.allowed is True
    assert result.reasons == []


def test_real_estate_policy_blocks_fair_housing_phrase() -> None:
    engine = load_policy_engine("real-estate")
    result = engine.validate_content("Great neighborhood, no children allowed")
    assert result.allowed is False
    assert "prohibited_content:no children" in result.reasons
