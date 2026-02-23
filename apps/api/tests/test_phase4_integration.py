from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import Role


def _mock_ingest_payload(thread_suffix: str = "001") -> dict[str, object]:
    return {
        "thread": {
            "provider": "meta",
            "account_ref": "acct-main",
            "external_thread_id": f"thr-{thread_suffix}",
            "thread_type": "dm",
            "subject": "Inbound buyer lead",
            "participants_json": [{"id": "lead-1", "display": "Casey"}],
            "last_message_at": "2026-02-24T12:00:00Z",
        },
        "messages": [
            {
                "external_message_id": f"msg-{thread_suffix}-1",
                "direction": "inbound",
                "sender_ref": "lead-1",
                "sender_display": "Casey",
                "body_text": "Hi, I want to buy a home in Seattle ASAP. Email me at casey@example.com",
                "body_raw_json": {"raw": "sample"},
            }
        ],
    }


@pytest.mark.integration
async def test_phase4_ingest_to_route_flow(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ingest = await client.post("/inbox/ingest/mock", headers=seeded_context, json=_mock_ingest_payload("001"))
        assert ingest.status_code == 201
        thread_id = ingest.json()["thread_id"]
        assert ingest.json()["inserted_messages"] == 1

        threads = await client.get("/inbox/threads", headers=seeded_context)
        assert threads.status_code == 200
        assert len(threads.json()) == 1

        suggest = await client.post(f"/inbox/threads/{thread_id}/suggest-reply", headers=seeded_context)
        assert suggest.status_code == 200
        assert suggest.json()["intent"] in ("answer", "qualify", "escalate")
        assert "reply_text" in suggest.json()

        lead_create = await client.post(f"/leads/from-thread/{thread_id}", headers=seeded_context)
        assert lead_create.status_code == 201
        lead_id = lead_create.json()["id"]

        score = await client.post(f"/leads/{lead_id}/score", headers=seeded_context)
        assert score.status_code == 200
        assert score.json()["score_total"] >= 0

        route = await client.post(f"/leads/{lead_id}/route", headers=seeded_context)
        assert route.status_code == 200
        assert route.json()["assigned_to_user_id"]

        tasks = await client.get(f"/leads/{lead_id}/nurture/tasks", headers=seeded_context)
        assert tasks.status_code == 200
        assert len(tasks.json()) >= 1

        audit = await client.get("/audit", headers=seeded_context)
        actions = [row["action"] for row in audit.json()]
        assert "inbox.ingest_mock" in actions
        assert "ai.suggest_reply" in actions
        assert "lead.created_from_thread" in actions
        assert "lead.scored" in actions
        assert "lead.routed" in actions


@pytest.mark.integration
async def test_phase4_org_isolation_for_inbox_and_leads(seeded_context: dict[str, str]) -> None:
    other_headers = dict(seeded_context)
    other_headers["X-Omniflow-Org-Id"] = str(uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"))
    other_headers["X-Omniflow-Role"] = Role.OWNER.value

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ingest = await client.post("/inbox/ingest/mock", headers=seeded_context, json=_mock_ingest_payload("002"))
        thread_id = ingest.json()["thread_id"]
        lead_create = await client.post(f"/leads/from-thread/{thread_id}", headers=seeded_context)
        lead_id = lead_create.json()["id"]

        foreign_thread = await client.get(f"/inbox/threads/{thread_id}", headers=other_headers)
        assert foreign_thread.status_code == 404

        foreign_lead = await client.get(f"/leads/{lead_id}", headers=other_headers)
        assert foreign_lead.status_code == 404


@pytest.mark.integration
async def test_phase4_suggest_reply_writes_audit(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ingest = await client.post("/inbox/ingest/mock", headers=seeded_context, json=_mock_ingest_payload("003"))
        thread_id = ingest.json()["thread_id"]
        response = await client.post(f"/inbox/threads/{thread_id}/suggest-reply", headers=seeded_context)
        assert response.status_code == 200
        assert response.json()["risk_tier"].startswith("TIER_")

        audit = await client.get("/audit", headers=seeded_context)
        assert any(row["action"] == "ai.suggest_reply" for row in audit.json())
