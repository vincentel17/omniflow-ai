from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.integration
async def test_create_org_and_membership(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/orgs", headers=seeded_context, json={"name": "Created Org"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Created Org"


@pytest.mark.integration
async def test_select_vertical_pack(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/verticals/select", headers=seeded_context, json={"pack_slug": "real-estate"})
        current = await client.get("/verticals/current", headers=seeded_context)

    assert response.status_code == 200
    assert current.status_code == 200
    assert current.json()["pack_slug"] == "real-estate"


@pytest.mark.integration
async def test_event_org_scoping(seeded_context: dict[str, str]) -> None:
    other_headers = dict(seeded_context)
    other_headers["X-Omniflow-Org-Id"] = str(uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"))
    payload = {"source": "social", "channel": "instagram", "type": "engagement", "payload_json": {"likes": 5}}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/events", headers=seeded_context, json=payload)
        own_events = await client.get("/events", headers=seeded_context)
        other_events = await client.get("/events", headers=other_headers)

    assert created.status_code == 201
    assert len(own_events.json()) == 1
    assert own_events.json()[0]["org_id"] == seeded_context["X-Omniflow-Org-Id"]
    assert other_events.status_code == 200
    assert other_events.json() == []


@pytest.mark.integration
async def test_audit_log_entries(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/verticals/select", headers=seeded_context, json={"pack_slug": "generic"})
        await client.post(
            "/events",
            headers=seeded_context,
            json={"source": "crm", "channel": "email", "type": "lead_created", "payload_json": {}},
        )
        audit = await client.get("/audit", headers=seeded_context)

    assert audit.status_code == 200
    actions = [entry["action"] for entry in audit.json()]
    assert "vertical_pack.selected" in actions
    assert "event.created" in actions
