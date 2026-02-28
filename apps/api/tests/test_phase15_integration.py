from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import BillingSubscriptionStatus, GlobalAdmin, OrgSubscription, SubscriptionPlan, VerticalPackRegistry
from app.services.billing import seed_default_plans


@pytest.mark.integration
async def test_phase15_available_and_manifest_endpoints(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        available = await client.get("/verticals/available", headers=seeded_context)
        assert available.status_code == 200
        rows = available.json()
        assert any(row["slug"] == "generic" for row in rows)

        manifest = await client.get("/verticals/generic/manifest", headers=seeded_context)
        assert manifest.status_code == 200
        body = manifest.json()
        assert body["slug"] == "generic"
        assert body["version"]


@pytest.mark.integration
async def test_phase15_pack_activation_enforces_entitlement(
    db_session,
    seeded_context: dict[str, str],
) -> None:
    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    seed_default_plans(db_session)

    sub = db_session.query(OrgSubscription).filter(OrgSubscription.org_id == org_id).first()
    if sub is None:
        free = db_session.query(SubscriptionPlan).filter(SubscriptionPlan.name == "Free").first()
        assert free is not None
        sub = OrgSubscription(org_id=org_id, plan_id=free.id, status=BillingSubscriptionStatus.ACTIVE)
        db_session.add(sub)
    else:
        free = db_session.query(SubscriptionPlan).filter(SubscriptionPlan.name == "Free").first()
        assert free is not None
        sub.plan_id = free.id
        sub.status = BillingSubscriptionStatus.ACTIVE
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        blocked = await client.post("/verticals/select", headers=seeded_context, json={"pack_slug": "real-estate"})
        assert blocked.status_code == 403

        growth = db_session.query(SubscriptionPlan).filter(SubscriptionPlan.name == "Growth").first()
        assert growth is not None
        sub.plan_id = growth.id
        db_session.commit()

        allowed = await client.post("/verticals/select", headers=seeded_context, json={"pack_slug": "real-estate"})
        assert allowed.status_code == 200
        assert allowed.json()["pack_slug"] == "real-estate"

    registry_row = (
        db_session.query(VerticalPackRegistry)
        .filter(VerticalPackRegistry.slug == "real-estate", VerticalPackRegistry.deleted_at.is_(None))
        .first()
    )
    assert registry_row is not None


@pytest.mark.integration
async def test_phase15_admin_registry_and_performance(
    db_session,
    seeded_context: dict[str, str],
) -> None:
    user_id = uuid.UUID(seeded_context["X-Omniflow-User-Id"])
    db_session.add(GlobalAdmin(user_id=user_id, email="integration@omniflow.local", active=True))
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        registry = await client.get("/admin/verticals", headers=seeded_context)
        assert registry.status_code == 200

        performance = await client.get("/admin/vertical-performance", headers=seeded_context)
        assert performance.status_code == 200
        rows = performance.json()
        if rows:
            first = rows[0]
            assert "funnel_events" in first
            assert "revenue_events" in first
            assert "automation_events" in first
            assert "predictive_events" in first


