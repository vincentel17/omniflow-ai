from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _seed_thread(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post(
        "/inbox/ingest/mock",
        headers=headers,
        json={
            "thread": {
                "provider": "meta",
                "account_ref": "acct-1",
                "external_thread_id": "thread-001",
                "thread_type": "dm",
                "subject": "Lead inquiry",
                "participants_json": [],
            },
            "messages": [
                {
                    "external_message_id": "msg-001",
                    "direction": "inbound",
                    "sender_ref": "lead-1",
                    "sender_display": "Lead One",
                    "body_text": "I need help buying a home ASAP in Raleigh",
                    "body_raw_json": {},
                }
            ],
        },
    )
    assert response.status_code == 201
    return response.json()["thread_id"]


@pytest.mark.integration
async def test_phase8_ops_settings_get_patch_and_enforcement(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        initial = await client.get("/ops/settings", headers=seeded_context)
        assert initial.status_code == 200
        assert "enable_auto_posting" in initial.json()

        patched = await client.patch(
            "/ops/settings",
            headers=seeded_context,
            json={
                "enable_auto_reply": False,
                "enable_auto_lead_routing": False,
                "enable_auto_nurture_apply": False,
            },
        )
        assert patched.status_code == 200
        assert patched.json()["enable_auto_lead_routing"] is False

        thread_id = await _seed_thread(client, seeded_context)

        reply = await client.post(f"/inbox/threads/{thread_id}/suggest-reply", headers=seeded_context)
        assert reply.status_code == 200

        lead_resp = await client.post(f"/leads/from-thread/{thread_id}", headers=seeded_context)
        assert lead_resp.status_code == 201
        lead_id = lead_resp.json()["id"]

        route_resp = await client.post(f"/leads/{lead_id}/route", headers=seeded_context)
        assert route_resp.status_code == 409
        assert "disabled" in route_resp.json()["detail"]

        nurture_resp = await client.post(
            f"/leads/{lead_id}/nurture/apply",
            headers=seeded_context,
            json={
                "tasks": [
                    {
                        "type": "task",
                        "due_in_minutes": 30,
                        "message_template_key": "first_touch",
                        "message_body": "Follow up with lead",
                    }
                ]
            },
        )
        assert nurture_resp.status_code == 409
        assert "disabled" in nurture_resp.json()["detail"]


@pytest.mark.integration
async def test_phase8_onboarding_progress_flow(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        started = await client.post("/onboarding/start", headers=seeded_context)
        assert started.status_code == 200
        session_id = started.json()["id"]
        assert started.json()["status"] == "in_progress"

        step = await client.post("/onboarding/step/select_vertical_pack/complete", headers=seeded_context, json={"completed": True})
        assert step.status_code == 200
        assert step.json()["id"] == session_id
        assert step.json()["steps_json"]["select_vertical_pack"] is True

        status_resp = await client.get("/onboarding/status", headers=seeded_context)
        assert status_resp.status_code == 200
        assert status_resp.json()["id"] == session_id

