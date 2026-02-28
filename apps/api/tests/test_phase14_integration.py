from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import (
    AdAccount,
    AdCampaign,
    AdProvider,
    Event,
    Lead,
    LeadStatus,
    ModelMetadata,
    ModelStatus,
    OrgOptimizationSettings,
    OrgSettings,
)


def _enable_optimization_settings(db_session, org_id: uuid.UUID) -> None:
    settings = db_session.query(OrgOptimizationSettings).filter(OrgOptimizationSettings.org_id == org_id).first()
    if settings is None:
        settings = OrgOptimizationSettings(org_id=org_id)
        db_session.add(settings)
    settings.enable_predictive_scoring = True
    settings.enable_post_timing_optimization = True
    settings.enable_nurture_optimization = True
    settings.enable_ad_budget_recommendations = True
    db_session.commit()


@pytest.mark.integration
async def test_phase14_score_lead_and_store(seeded_context: dict[str, str], db_session) -> None:
    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    _enable_optimization_settings(db_session, org_id)
    lead = Lead(org_id=org_id, source="manual", status=LeadStatus.NEW, name="Phase14 Lead")
    db_session.add(lead)
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/optimization/lead-score/{lead.id}", headers=seeded_context)
        assert resp.status_code == 200
        body = resp.json()
        assert body["lead_id"] == str(lead.id)
        assert 0.0 <= body["score_probability"] <= 1.0
        assert "explanation" in body


@pytest.mark.integration
async def test_phase14_post_timing_and_next_best_action(seeded_context: dict[str, str], db_session) -> None:
    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    _enable_optimization_settings(db_session, org_id)
    lead = Lead(org_id=org_id, source="manual", status=LeadStatus.NEW, name="Timing Lead")
    db_session.add(lead)
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        timing = await client.get("/optimization/campaigns?channel=meta", headers=seeded_context)
        assert timing.status_code == 200
        rows = timing.json()
        assert len(rows) == 1
        assert rows[0]["channel"] == "meta"

        nba = await client.get(f"/optimization/next-best-action/lead/{lead.id}", headers=seeded_context)
        assert nba.status_code == 200
        payload = nba.json()
        assert payload["action_type"] in {"call", "send_message", "create_checklist_task", "request_review"}
        assert payload["confidence_score"] >= 0


@pytest.mark.integration
async def test_phase14_budget_recommendation_creates_approval(seeded_context: dict[str, str], db_session) -> None:
    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    user_id = uuid.UUID(seeded_context["X-Omniflow-User-Id"])
    _enable_optimization_settings(db_session, org_id)

    settings = db_session.query(OrgSettings).filter(OrgSettings.org_id == org_id).first()
    if settings is None:
        settings = OrgSettings(org_id=org_id)
        db_session.add(settings)

    ad_account = AdAccount(
        org_id=org_id,
        provider=AdProvider.META,
        account_ref="acct-1",
        display_name="Meta Test",
    )
    db_session.add(ad_account)
    db_session.flush()

    campaign = AdCampaign(
        org_id=org_id,
        provider=AdProvider.META,
        ad_account_id=ad_account.id,
        name="Phase14 Campaign",
        objective="traffic",
        daily_budget_usd=25,
        created_by=user_id,
    )
    db_session.add(campaign)
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/optimization/ads?limit=10", headers=seeded_context)
        assert resp.status_code == 200
        recs = resp.json()
        assert len(recs) >= 1
        assert recs[0]["campaign_id"] == str(campaign.id)
        assert "explanation" in recs[0]

    reasoning = recs[0].get("reasoning_json", {})
    assert str(reasoning.get("approval_required", "")).lower() == "true"
    assert reasoning.get("workflow_action_suggestion") == "ADS_REQUEST_ACTIVATION"


@pytest.mark.integration
async def test_phase14_models_and_activation(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        models_resp = await client.get("/optimization/models", headers=seeded_context)
        assert models_resp.status_code == 200
        models = models_resp.json()
        assert len(models) >= 1

        first = models[0]
        activate_resp = await client.post(
            f"/optimization/models/{first['name']}/activate",
            headers=seeded_context,
            json={"version": first["version"]},
        )
        assert activate_resp.status_code == 200
        assert activate_resp.json()["status"] == "active"


@pytest.mark.integration
async def test_phase14_model_drift_triggers_rollback_event(seeded_context: dict[str, str], db_session) -> None:
    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    active = ModelMetadata(
        org_id=org_id,
        name="post_timing_model",
        version="v-current",
        training_window="90d",
        metrics_json={"uplift": 0.4, "recent_metric": 0.2},
        status=ModelStatus.ACTIVE,
    )
    fallback = ModelMetadata(
        org_id=org_id,
        name="post_timing_model",
        version="v-prev",
        training_window="90d",
        metrics_json={"uplift": 0.35, "recent_metric": 0.34},
        status=ModelStatus.INACTIVE,
    )
    db_session.add(active)
    db_session.add(fallback)
    db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/optimization/models", headers=seeded_context)
        assert resp.status_code == 200

    db_session.refresh(active)
    db_session.refresh(fallback)
    assert active.status == ModelStatus.DEGRADED
    assert fallback.status == ModelStatus.ACTIVE

    rollback_events = (
        db_session.query(Event)
        .filter(
            Event.org_id == org_id,
            Event.type == "MODEL_ROLLBACK",
        )
        .all()
    )
    assert len(rollback_events) >= 1





