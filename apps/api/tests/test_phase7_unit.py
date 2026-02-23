from __future__ import annotations

from datetime import UTC, datetime

from app.services.phase7 import append_disclaimers, calculate_cma_pricing, compute_due_at
from packages.policy import PolicyEngine, RiskTier


class _Comp:
    def __init__(self, sold_price: int | None, list_price: int | None, sqft: int | None) -> None:
        self.sold_price = sold_price
        self.list_price = list_price
        self.sqft = sqft


def test_phase7_cma_pricing_stable_range() -> None:
    comps = [
        _Comp(sold_price=410000, list_price=None, sqft=2000),
        _Comp(sold_price=425000, list_price=None, sqft=2100),
        _Comp(sold_price=None, list_price=405000, sqft=1950),
    ]
    pricing = calculate_cma_pricing(comps)  # type: ignore[arg-type]
    assert pricing["suggested_range_low"] == 393600
    assert pricing["suggested_price"] == 410000
    assert pricing["suggested_range_high"] == 426400


def test_phase7_checklist_offset_due_date() -> None:
    due = compute_due_at({"contract_date": "2026-03-01T15:00:00+00:00"}, "contract_date", 5)
    assert due == datetime(2026, 3, 6, 15, 0, tzinfo=UTC)


def test_phase7_disclaimer_injection_and_high_risk_words() -> None:
    text = append_disclaimers("Listing draft", ["Equal Housing Opportunity."])
    assert "Equal Housing Opportunity." in text

    policy = PolicyEngine(
        "real-estate",
        {"content": {"prohibited_words": ["whites only"]}, "risk": {"overrides": {"listing_package_generate": "TIER_2"}}},
    )
    assert policy.risk_tier("listing_package_generate", {"content": "whites only offer"}) == RiskTier.TIER_4
