from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import Role


@pytest.mark.integration
async def test_phase6_tracked_link_redirect_writes_click_and_event(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/links",
            headers=seeded_context,
            json={
                "destination_url": "https://example.com/offer",
                "content_id": "content-abc",
                "campaign_plan_id": "campaign-xyz",
                "channel": "linkedin",
                "source": "social",
                "medium": "organic",
                "campaign": "q1-growth",
            },
        )
        assert created.status_code == 201
        short_code = created.json()["short_code"]

        redirected = await client.get(
            f"/r/{short_code}",
            headers={
                "user-agent": "phase6-test-agent",
                "referer": "https://example-referrer.com",
                "x-forwarded-for": "203.0.113.10",
            },
            follow_redirects=False,
        )
        assert redirected.status_code == 302
        assert redirected.headers["location"] == "https://example.com/offer"

        events = await client.get("/events", headers=seeded_context)
        assert events.status_code == 200
        event_types = [event["type"] for event in events.json()]
        assert "LINK_CLICKED" in event_types

        content = await client.get("/analytics/content", headers=seeded_context)
        assert content.status_code == 200
        clicks = {row["content_id"]: row["clicks"] for row in content.json()["clicks_by_content"]}
        assert clicks["content-abc"] == 1


@pytest.mark.integration
async def test_phase6_org_isolation_for_links_and_analytics(seeded_context: dict[str, str]) -> None:
    other_headers = dict(seeded_context)
    other_headers["X-Omniflow-Org-Id"] = str(uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"))
    other_headers["X-Omniflow-Role"] = Role.OWNER.value

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/links",
            headers=seeded_context,
            json={
                "destination_url": "https://example.com/private",
                "content_id": "private-content",
                "channel": "instagram",
            },
        )
        assert created.status_code == 201
        short_code = created.json()["short_code"]

        clicked = await client.get(f"/r/{short_code}", follow_redirects=False)
        assert clicked.status_code == 302

        foreign_links = await client.get("/links", headers=other_headers)
        assert foreign_links.status_code == 200
        assert foreign_links.json() == []

        foreign_content = await client.get("/analytics/content", headers=other_headers)
        assert foreign_content.status_code == 200
        assert foreign_content.json()["clicks_by_content"] == []
