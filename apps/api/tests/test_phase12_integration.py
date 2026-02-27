from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import (
    AuditLog,
    DataRetentionPolicy,
    InboxMessage,
    InboxMessageDirection,
    InboxThread,
    InboxThreadStatus,
    InboxThreadType,
    Lead,
    OrgSettings,
    RiskTier,
)
from omniflow_worker.main import retention_enforcer_tick


def _patch_worker_send_task(monkeypatch: pytest.MonkeyPatch):
    from omniflow_worker.main import app as worker_app

    def _send_task(_name: str, args=None, kwargs=None, **_):
        return {"args": args or [], "kwargs": kwargs or {}}

    monkeypatch.setattr(worker_app, "send_task", _send_task)


@pytest.mark.integration
async def test_phase12_dsar_access_export_contains_subject_records(
    seeded_context: dict[str, str], db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_worker_send_task(monkeypatch)

    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    thread = InboxThread(
        org_id=org_id,
        provider="meta",
        account_ref="acct-dsar-1",
        thread_type=InboxThreadType.EMAIL,
        external_thread_id="thr-dsar-1",
        subject="Need follow-up",
        status=InboxThreadStatus.OPEN,
        participants_json=[],
    )
    lead = Lead(
        org_id=org_id,
        source="web",
        status="new",
        name="Alice Example",
        email="alice@example.com",
        phone="+1 (415) 555-0188",
        tags_json=[],
        pii_flags_json={"contains_email": True},
        sensitive_level="medium",
    )
    db_session.add_all([thread, lead])
    db_session.flush()
    message = InboxMessage(
        org_id=org_id,
        thread_id=thread.id,
        external_message_id="msg-dsar-1",
        direction=InboxMessageDirection.INBOUND,
        sender_ref="alice@example.com",
        sender_display="alice@example.com",
        body_text="Please contact me",
        body_raw_json={},
        flags_json={"contains_email": True},
        pii_flags_json={"contains_email": True},
        sensitive_level="medium",
    )
    db_session.add(message)
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/compliance/dsar",
            headers=seeded_context,
            json={"request_type": "access", "subject_identifier": "alice@example.com"},
        )
        assert create_resp.status_code == 201
        dsar_id = create_resp.json()["id"]

        process_resp = await client.post(f"/compliance/dsar/{dsar_id}/process", headers=seeded_context)
        assert process_resp.status_code == 200
        assert process_resp.json()["status"] == "completed"

        listed = await client.get("/compliance/dsar", headers=seeded_context)
        assert listed.status_code == 200
        export_ref = listed.json()[0]["export_ref"]
        assert export_ref is not None
        assert "alice@example.com" not in export_ref


@pytest.mark.integration
async def test_phase12_dsar_delete_soft_deletes_subject_records(
    seeded_context: dict[str, str], db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_worker_send_task(monkeypatch)

    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    lead = Lead(
        org_id=org_id,
        source="web",
        status="new",
        name="Delete Me",
        email="delete.me@example.com",
        phone=None,
        tags_json=[],
        pii_flags_json={"contains_email": True},
        sensitive_level="medium",
    )
    db_session.add(lead)
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/compliance/dsar",
            headers=seeded_context,
            json={"request_type": "delete", "subject_identifier": "delete.me@example.com"},
        )
        assert create_resp.status_code == 201
        dsar_id = create_resp.json()["id"]

        process_resp = await client.post(f"/compliance/dsar/{dsar_id}/process", headers=seeded_context)
        assert process_resp.status_code == 200

    db_session.refresh(lead)
    assert lead.deleted_at is not None
    assert lead.deletion_reason == "dsar_delete"
    assert lead.email is None


@pytest.mark.integration
async def test_phase12_retention_job_soft_deletes_expired_data(
    seeded_context: dict[str, str], db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_worker_send_task(monkeypatch)

    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    old_time = datetime.now(timezone.utc) - timedelta(days=400)

    policy = DataRetentionPolicy(
        org_id=org_id,
        entity_type="lead",
        retention_days=365,
        hard_delete_after_days=395,
    )
    lead = Lead(
        org_id=org_id,
        source="web",
        status="new",
        name="Old Lead",
        email="old@example.com",
        phone=None,
        tags_json=[],
        pii_flags_json={},
        sensitive_level="low",
        created_at=old_time,
    )
    db_session.add_all([policy, lead])
    db_session.commit()

    result = retention_enforcer_tick()
    assert result >= 1

    db_session.refresh(lead)
    assert lead.deleted_at is not None
    assert lead.deletion_reason == "retention_policy"


@pytest.mark.integration
async def test_phase12_rbac_audit_flags_risky_configuration(
    seeded_context: dict[str, str], db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_worker_send_task(monkeypatch)

    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    settings = OrgSettings(
        org_id=org_id,
        settings_json={
            "enable_auto_posting": True,
            "max_auto_approve_tier": 4,
            "enable_ads_live": True,
            "ads_budget_caps_json": {"org_daily_cap_usd": 0},
            "default_autonomy_max_tier": 4,
        },
    )
    db_session.add(settings)
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/compliance/rbac-audit", headers=seeded_context)
        assert resp.status_code == 200
        body = resp.json()
        codes = {item["code"] for item in body["findings_json"]}
        assert "AUTO_POST_HIGH_TIER" in codes
        assert "ADS_LIVE_NO_CAPS" in codes
        assert "WORKFLOW_HIGH_AUTONOMY" in codes


@pytest.mark.integration
async def test_phase12_evidence_bundle_returns_expected_sections(
    seeded_context: dict[str, str], db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_worker_send_task(monkeypatch)

    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    db_session.add(
        AuditLog(
            org_id=org_id,
            actor_user_id=None,
            action="compliance.test",
            target_type="test",
            target_id="1",
            risk_tier=RiskTier.TIER_1,
            metadata_json={"email": "masked@example.com"},
        )
    )
    db_session.commit()

    today = date.today().isoformat()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/compliance/evidence-bundle?from_date={today}&to_date={today}&include_pii=false",
            headers=seeded_context,
        )
        assert resp.status_code == 200
        bundle = resp.json()["bundle_json"]
        assert "audit_logs" in bundle
        assert "workflow_runs" in bundle
        assert "ads_approvals" in bundle
        assert "retention_events" in bundle
        assert "rbac_audit_reports" in bundle
        assert "dsar_logs" in bundle


@pytest.mark.integration
async def test_phase12_home_care_blocks_draft_reply_on_health_related_thread(
    seeded_context: dict[str, str], db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_worker_send_task(monkeypatch)

    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    db_session.add(
        OrgSettings(
            org_id=org_id,
            settings_json={"compliance_mode": "home_care"},
        )
    )

    thread = InboxThread(
        org_id=org_id,
        provider="meta",
        account_ref="acct-home-care",
        thread_type=InboxThreadType.EMAIL,
        external_thread_id="thr-home-care-1",
        subject="Health follow up",
        status=InboxThreadStatus.OPEN,
        participants_json=[],
    )
    db_session.add(thread)
    db_session.flush()
    db_session.add(
        InboxMessage(
            org_id=org_id,
            thread_id=thread.id,
            external_message_id="msg-home-care-1",
            direction=InboxMessageDirection.INBOUND,
            sender_ref="patient@example.com",
            sender_display="patient@example.com",
            body_text="My diagnosis results are in",
            body_raw_json={},
            flags_json={"health_related": True},
            pii_flags_json={"contains_health": True},
            sensitive_level="high",
        )
    )
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/inbox/threads/{thread.id}/draft-reply",
            headers=seeded_context,
            json={"body_text": "Thanks for your update."},
        )
        assert resp.status_code == 409
        assert "home care compliance" in resp.json()["detail"]
