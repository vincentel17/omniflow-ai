from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import GlobalAdmin, UsageMetricType
from app.services.billing import assert_usage_allowed, increment_usage


@pytest.mark.integration
async def test_phase13_checkout_webhook_activates_subscription(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        plans_resp = await client.get("/billing/plans", headers=seeded_context)
        assert plans_resp.status_code == 200
        plans = plans_resp.json()
        assert len(plans) >= 1
        target_plan_id = plans[0]["id"]

        checkout_resp = await client.post(
            "/billing/checkout",
            headers=seeded_context,
            json={"plan_id": target_plan_id},
        )
        assert checkout_resp.status_code == 200
        assert checkout_resp.json()["checkout_session_id"].startswith("cs_test_")

        webhook_resp = await client.post(
            "/billing/webhook",
            json={
                "event_type": "checkout.session.completed",
                "data": {
                    "org_id": seeded_context["X-Omniflow-Org-Id"],
                    "plan_id": target_plan_id,
                },
            },
        )
        assert webhook_resp.status_code == 200
        assert webhook_resp.json()["processed"] is True

        sub_resp = await client.get("/billing/subscription", headers=seeded_context)
        assert sub_resp.status_code == 200
        assert sub_resp.json()["status"] == "active"


@pytest.mark.integration
def test_phase13_usage_enforcement_blocks_when_limit_exceeded(
    db_session,
    seeded_context: dict[str, str],
) -> None:
    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])

    increment_usage(db=db_session, org_id=org_id, metric_type=UsageMetricType.POST_CREATED, count=20)

    with pytest.raises(HTTPException) as exc_info:
        assert_usage_allowed(db=db_session, org_id=org_id, metric_type=UsageMetricType.POST_CREATED, increment=1)

    assert "USAGE_LIMIT_EXCEEDED" in str(exc_info.value)


@pytest.mark.integration
async def test_phase13_global_admin_impersonate_and_suspend(
    db_session,
    seeded_context: dict[str, str],
) -> None:
    user_id = uuid.UUID(seeded_context["X-Omniflow-User-Id"])
    org_id = seeded_context["X-Omniflow-Org-Id"]

    db_session.add(GlobalAdmin(user_id=user_id, email="integration@omniflow.local", active=True))
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        orgs_resp = await client.get("/admin/orgs?limit=20&offset=0", headers=seeded_context)
        assert orgs_resp.status_code == 200
        assert any(row["id"] == org_id for row in orgs_resp.json())

        imp_resp = await client.post(f"/admin/orgs/{org_id}/impersonate", headers=seeded_context)
        assert imp_resp.status_code == 200
        assert imp_resp.json()["impersonation_token"].startswith("imp_")

        suspend_resp = await client.post(f"/admin/orgs/{org_id}/suspend", headers=seeded_context)
        assert suspend_resp.status_code == 200
        assert suspend_resp.json()["org_status"] == "suspended"
