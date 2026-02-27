from __future__ import annotations

import uuid
from datetime import date

from app.services.billing import StripeService, _month_bounds


def test_phase13_stripe_service_checkout_is_deterministic() -> None:
    service = StripeService()
    org_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    plan_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    session = service.create_checkout_session(org_id=org_id, plan_id=plan_id)
    assert session["id"].startswith("cs_test_")
    assert str(plan_id) in session["url"]


def test_phase13_month_bounds_for_mid_month() -> None:
    start, end = _month_bounds(date(2026, 2, 12))
    assert start.isoformat() == "2026-02-01"
    assert end.isoformat() == "2026-02-28"
