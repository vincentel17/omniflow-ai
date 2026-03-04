from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import (
    Approval,
    ApprovalEntityType,
    ApprovalStatus,
    Lead,
    LeadStatus,
    OrgSettings,
    ReputationReview,
    ReputationSource,
)

OTHER_ORG_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _upsert_agent_settings(db_session, org_id: uuid.UUID, *, max_auto_tier: int = 1) -> None:
    settings = db_session.query(OrgSettings).filter(OrgSettings.org_id == org_id).first()
    if settings is None:
        settings = OrgSettings(org_id=org_id)
        db_session.add(settings)
        db_session.flush()
    payload = dict(settings.settings_json or {})
    payload.update(
        {
            "enable_agents": True,
            "agent_autonomy_max_tier": max_auto_tier,
            "agent_max_plans_per_day": 10,
            "agent_max_steps_per_plan": 10,
            "agent_cooldown_minutes": 0,
            "agent_allowed_action_types_json": [],
            "agent_disallowed_targets_json": [],
            "ai_mode": "mock",
            "connector_mode": "mock",
        }
    )
    settings.settings_json = payload
    db_session.commit()


@pytest.mark.integration
async def test_phase16_create_agent_run_stores_plan(seeded_context: dict[str, str], db_session) -> None:
    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    _upsert_agent_settings(db_session, org_id, max_auto_tier=2)

    db_session.add(Lead(org_id=org_id, source="manual", status=LeadStatus.NEW, name="Agent Lead"))
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/agents/run", headers=seeded_context, json={"trigger_type": "manual"})
        assert resp.status_code == 201
        payload = resp.json()
        assert payload["agent_name"] in {"GrowthAgent", "InboxAgent", "PresenceAgent", "SEOAgent", "ReputationAgent"}
        assert payload["trigger_type"] == "manual"
        assert isinstance(payload["plan_json"], dict)
        assert len(payload["plan_json"].get("steps", [])) >= 1


@pytest.mark.integration
async def test_phase16_high_risk_plan_creates_approval(seeded_context: dict[str, str], db_session) -> None:
    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    _upsert_agent_settings(db_session, org_id, max_auto_tier=0)

    db_session.add(
        ReputationReview(
            org_id=org_id,
            source=ReputationSource.MANUAL_IMPORT,
            external_id="rev-1",
            reviewer_name_masked="A***",
            rating=1,
            review_text="Very poor experience",
            review_text_hash="hash-rev-1",
            sentiment_json={"label": "negative"},
        )
    )
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/agents/run", headers=seeded_context, json={"trigger_type": "manual"})
        assert resp.status_code == 201

    approvals = (
        db_session.query(Approval)
        .filter(
            Approval.org_id == org_id,
            Approval.entity_type == ApprovalEntityType.AGENT_RUN,
            Approval.status == ApprovalStatus.PENDING,
        )
        .all()
    )
    assert len(approvals) >= 1


@pytest.mark.integration
async def test_phase16_org_isolation_for_agent_runs(seeded_context: dict[str, str], db_session) -> None:
    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    _upsert_agent_settings(db_session, org_id, max_auto_tier=2)
    db_session.add(Lead(org_id=org_id, source="manual", status=LeadStatus.NEW, name="Isolation Lead"))
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/agents/run", headers=seeded_context, json={"trigger_type": "manual"})
        assert created.status_code == 201
        run_id = created.json()["id"]

        other_context = dict(seeded_context)
        other_context["X-Omniflow-Org-Id"] = str(OTHER_ORG_ID)
        hidden = await client.get(f"/agents/runs/{run_id}", headers=other_context)
        assert hidden.status_code == 404
