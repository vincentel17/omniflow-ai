from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import Role


@pytest.mark.integration
async def test_phase3_campaign_to_schedule_flow(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        campaign_resp = await client.post(
            "/campaigns/plan",
            headers=seeded_context,
            json={
                "week_start_date": "2026-02-23",
                "channels": ["linkedin"],
                "objectives": ["Drive attributable revenue"],
            },
        )
        assert campaign_resp.status_code == 201
        campaign_id = campaign_resp.json()["id"]

        generated = await client.post(f"/campaigns/{campaign_id}/generate-content", headers=seeded_context)
        assert generated.status_code == 200
        assert generated.json()["items_created"] >= 1

        content_list = await client.get("/content", headers=seeded_context)
        assert content_list.status_code == 200
        content_rows = content_list.json()
        assert len(content_rows) >= 1
        content_id = content_rows[0]["id"]

        approve = await client.post(
            f"/content/{content_id}/approve",
            headers=seeded_context,
            json={"status": "approved", "notes": "approved in integration test"},
        )
        assert approve.status_code == 200

        scheduled = await client.post(
            f"/content/{content_id}/schedule",
            headers=seeded_context,
            json={"provider": "linkedin", "account_ref": "default", "schedule_at": "2026-02-23T12:00:00Z"},
        )
        assert scheduled.status_code == 201
        assert scheduled.json()["status"] == "queued"

        publish_jobs = await client.get("/publish/jobs", headers=seeded_context)
        assert publish_jobs.status_code == 200
        assert len(publish_jobs.json()) == 1

        audit_rows = await client.get("/audit", headers=seeded_context)
        actions = [item["action"] for item in audit_rows.json()]
        assert "ai.generate_plan" in actions
        assert "ai.generate_content" in actions
        assert "publish.job_scheduled" in actions


@pytest.mark.integration
async def test_phase3_org_isolation(seeded_context: dict[str, str]) -> None:
    other_headers = dict(seeded_context)
    other_headers["X-Omniflow-Org-Id"] = str(uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"))
    other_headers["X-Omniflow-Role"] = Role.OWNER.value

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        campaign_resp = await client.post(
            "/campaigns/plan",
            headers=seeded_context,
            json={"week_start_date": "2026-02-23", "channels": ["linkedin"], "objectives": ["Test"]},
        )
        assert campaign_resp.status_code == 201
        campaign_id = campaign_resp.json()["id"]

        own_campaigns = await client.get("/campaigns", headers=seeded_context)
        other_campaigns = await client.get("/campaigns", headers=other_headers)
        assert len(own_campaigns.json()) == 1
        assert other_campaigns.json() == []

        forbidden = await client.get(f"/campaigns/{campaign_id}", headers=other_headers)
        assert forbidden.status_code == 404


@pytest.mark.integration
async def test_phase3_schema_validation_422(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/campaigns/plan",
            headers=seeded_context,
            json={"channels": ["linkedin"], "objectives": ["Missing date"]},
        )
    assert response.status_code == 422
