from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

OTHER_ORG_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _patch_worker_send_task(monkeypatch: pytest.MonkeyPatch):
    from omniflow_worker.main import app as worker_app

    def _send_task(_name: str, args=None, kwargs=None, **_):
        # Keep dispatch deterministic in tests; execution is drained explicitly after commit.
        return {"args": args or [], "kwargs": kwargs or {}}

    monkeypatch.setattr(worker_app, "send_task", _send_task)
    return worker_app


async def _drain_queued_workflow_actions(client: AsyncClient, headers: dict[str, str], worker_app) -> None:
    actions_resp = await client.get("/workflows/actions?limit=100&offset=0", headers=headers)
    assert actions_resp.status_code == 200
    for row in actions_resp.json():
        if row.get("status") == "queued":
            worker_app.tasks["worker.workflow.action.execute"].run(row["id"])


@pytest.mark.integration
async def test_phase10_low_tier_action_auto_executes_and_writes_run(seeded_context: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    worker_app = _patch_worker_send_task(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/workflows",
            headers=seeded_context,
            json={
                "key": "it_low_tier_auto_exec",
                "name": "IT Low Tier Auto Exec",
                "enabled": True,
                "definition_json": {
                    "id": "it_low_tier_auto_exec",
                    "name": "IT Low Tier Auto Exec",
                    "enabled": True,
                    "trigger": {"type": "EVENT", "event_type": "INBOX_INGESTED"},
                    "conditions": [{"type": "event.type_equals", "value": "INBOX_INGESTED"}],
                    "actions": [{"type": "RUN_PRESENCE_AUDIT", "params_json": {}}],
                    "autonomy": {"max_auto_tier": 1, "require_approval_for_actions": []},
                },
            },
        )
        assert created.status_code == 201

        event_resp = await client.post(
            "/events",
            headers=seeded_context,
            json={
                "source": "integration-test",
                "channel": "inbox",
                "type": "INBOX_INGESTED",
                "payload_json": {"thread_id": "thread-1"},
            },
        )
        assert event_resp.status_code == 201
        event_id = event_resp.json()["id"]

        worker_app.tasks["worker.workflow.evaluate"].run(event_id)
        await _drain_queued_workflow_actions(client, seeded_context, worker_app)

        runs_resp = await client.get("/workflows/runs?limit=20&offset=0", headers=seeded_context)
        assert runs_resp.status_code == 200
        runs = runs_resp.json()
        assert len(runs) >= 1
        assert runs[0]["status"] in {"queued", "succeeded"}

        actions_resp = await client.get("/workflows/actions?limit=20&offset=0", headers=seeded_context)
        assert actions_resp.status_code == 200
        actions = actions_resp.json()
        assert len(actions) >= 1
        assert any(row["status"] == "succeeded" for row in actions)


@pytest.mark.integration
async def test_phase10_high_tier_action_requires_approval_then_executes(
    seeded_context: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    worker_app = _patch_worker_send_task(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/workflows",
            headers=seeded_context,
            json={
                "key": "it_high_tier_approval",
                "name": "IT High Tier Approval",
                "enabled": True,
                "definition_json": {
                    "id": "it_high_tier_approval",
                    "name": "IT High Tier Approval",
                    "enabled": True,
                    "trigger": {"type": "EVENT", "event_type": "LISTING_PACKAGE_APPROVED"},
                    "conditions": [{"type": "event.type_equals", "value": "LISTING_PACKAGE_APPROVED"}],
                    "actions": [{"type": "WEBHOOK", "params_json": {"url": "https://example.test/hook", "body": {"ok": True}}}],
                    "autonomy": {"max_auto_tier": 1, "require_approval_for_actions": []},
                },
            },
        )
        assert created.status_code == 201

        event_resp = await client.post(
            "/events",
            headers=seeded_context,
            json={
                "source": "integration-test",
                "channel": "content",
                "type": "LISTING_PACKAGE_APPROVED",
                "payload_json": {"listing_id": "listing-1"},
            },
        )
        assert event_resp.status_code == 201
        event_id = event_resp.json()["id"]

        worker_app.tasks["worker.workflow.evaluate"].run(event_id)

        actions_resp = await client.get("/workflows/actions?limit=20&offset=0", headers=seeded_context)
        assert actions_resp.status_code == 200
        pending_actions = [row for row in actions_resp.json() if row["status"] == "approval_pending"]
        assert len(pending_actions) == 1

        approvals_resp = await client.get("/approvals?status=pending&limit=20&offset=0", headers=seeded_context)
        assert approvals_resp.status_code == 200
        approvals = approvals_resp.json()
        assert len(approvals) == 1

        approve_resp = await client.post(
            f"/approvals/{approvals[0]['id']}/approve",
            headers=seeded_context,
            json={"status": "approved", "notes": "approved in integration test"},
        )
        assert approve_resp.status_code == 200

        await _drain_queued_workflow_actions(client, seeded_context, worker_app)

        refreshed_actions = await client.get("/workflows/actions?limit=20&offset=0", headers=seeded_context)
        assert refreshed_actions.status_code == 200
        assert any(row["status"] == "succeeded" for row in refreshed_actions.json())


@pytest.mark.integration
async def test_phase10_loop_guard_blocks_recursion_depth(seeded_context: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    worker_app = _patch_worker_send_task(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/workflows",
            headers=seeded_context,
            json={
                "key": "it_loop_guard",
                "name": "IT Loop Guard",
                "enabled": True,
                "definition_json": {
                    "id": "it_loop_guard",
                    "name": "IT Loop Guard",
                    "enabled": True,
                    "trigger": {"type": "EVENT", "event_type": "LEAD_CREATED"},
                    "conditions": [{"type": "event.type_equals", "value": "LEAD_CREATED"}],
                    "actions": [{"type": "RUN_PRESENCE_AUDIT", "params_json": {}}],
                },
            },
        )
        assert created.status_code == 201

        event_resp = await client.post(
            "/events",
            headers=seeded_context,
            json={
                "source": "integration-test",
                "channel": "leads",
                "type": "LEAD_CREATED",
                "payload_json": {"workflow_origin": {"workflow_run_id": "x", "depth": 3}},
            },
        )
        assert event_resp.status_code == 201
        event_id = event_resp.json()["id"]

        result = worker_app.tasks["worker.workflow.evaluate"].run(event_id)
        assert result == "max_depth_reached"

        runs_resp = await client.get("/workflows/runs?limit=20&offset=0", headers=seeded_context)
        assert runs_resp.status_code == 200
        assert runs_resp.json() == []


@pytest.mark.integration
async def test_phase10_workflow_org_isolation(seeded_context: dict[str, str]) -> None:
    other_headers = dict(seeded_context)
    other_headers["X-Omniflow-Org-Id"] = str(OTHER_ORG_ID)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/workflows",
            headers=seeded_context,
            json={
                "key": "it_org_isolation",
                "name": "IT Org Isolation",
                "enabled": True,
                "definition_json": {
                    "id": "it_org_isolation",
                    "name": "IT Org Isolation",
                    "enabled": True,
                    "trigger": {"type": "EVENT", "event_type": "INBOX_INGESTED"},
                    "conditions": [{"type": "event.type_equals", "value": "INBOX_INGESTED"}],
                    "actions": [{"type": "RUN_PRESENCE_AUDIT", "params_json": {}}],
                },
            },
        )
        assert created.status_code == 201
        workflow_id = created.json()["id"]

        list_other = await client.get("/workflows?limit=20&offset=0", headers=other_headers)
        assert list_other.status_code == 200
        assert list_other.json() == []

        get_other = await client.get(f"/workflows/{workflow_id}", headers=other_headers)
        assert get_other.status_code == 404
