from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import (
    AdAccount,
    AdCampaign,
    AdProvider,
    Approval,
    ApprovalEntityType,
    ApprovalStatus,
    Lead,
    LeadStatus,
    OrgSettings,
    REChecklistItem,
    REDeal,
    REDealType,
    ReputationReview,
    ReputationSource,
    VerticalPack,
    Workflow,
    WorkflowActionRun,
    WorkflowRun,
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


@pytest.mark.integration
async def test_phase16_worker_executes_ads_draft_action(seeded_context: dict[str, str], db_session) -> None:
    from omniflow_worker.main import _execute_workflow_action

    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    user_id = uuid.UUID(seeded_context["X-Omniflow-User-Id"])
    _upsert_agent_settings(db_session, org_id, max_auto_tier=2)

    settings = db_session.query(OrgSettings).filter(OrgSettings.org_id == org_id).first()
    assert settings is not None
    payload = dict(settings.settings_json or {})
    payload.update({"enable_ads_automation": True})
    settings.settings_json = payload

    account = AdAccount(
        org_id=org_id,
        provider=AdProvider.META,
        account_ref="phase16-meta-acct",
        display_name="Phase16 Meta",
    )
    workflow = Workflow(org_id=org_id, key="phase16-ads-draft", name="Phase16 Ads Draft", definition_json={})
    db_session.add_all([account, workflow])
    db_session.commit()
    db_session.refresh(account)
    db_session.refresh(workflow)

    run = WorkflowRun(org_id=org_id, workflow_id=workflow.id, summary_json={})
    db_session.add(run)
    db_session.flush()

    action_run = WorkflowActionRun(
        org_id=org_id,
        workflow_run_id=run.id,
        action_type="ADS_CREATE_CAMPAIGN_DRAFT",
        idempotency_key=f"phase16-ads-{uuid.uuid4()}",
        input_json={
            "params_json": {
                "provider": "meta",
                "ad_account_id": str(account.id),
                "name": "Phase16 Agent Campaign",
                "objective": "traffic",
                "daily_budget_usd": 5,
            }
        },
        output_json={},
        error_json={},
    )
    db_session.add(action_run)
    db_session.commit()

    result = _execute_workflow_action(db=db_session, action_run_id=action_run.id)
    db_session.commit()

    campaign = db_session.query(AdCampaign).filter(AdCampaign.id == uuid.UUID(result["ad_campaign_id"])).one()
    assert campaign.org_id == org_id
    assert campaign.name == "Phase16 Agent Campaign"
    assert campaign.created_by == user_id


@pytest.mark.integration
async def test_phase16_worker_executes_real_estate_checklist_action(seeded_context: dict[str, str], db_session) -> None:
    from omniflow_worker.main import _execute_workflow_action

    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    _upsert_agent_settings(db_session, org_id, max_auto_tier=2)
    existing_pack = db_session.query(VerticalPack).filter(VerticalPack.org_id == org_id).first()
    if existing_pack is None:
        db_session.add(VerticalPack(org_id=org_id, pack_slug="real-estate"))
    else:
        existing_pack.pack_slug = "real-estate"
    deal = REDeal(org_id=org_id, deal_type=REDealType.BUYER, pipeline_stage="lead")
    workflow = Workflow(org_id=org_id, key="phase16-re-item", name="Phase16 RE", definition_json={})
    db_session.add_all([deal, workflow])
    db_session.commit()
    db_session.refresh(deal)
    db_session.refresh(workflow)

    run = WorkflowRun(org_id=org_id, workflow_id=workflow.id, summary_json={})
    db_session.add(run)
    db_session.flush()

    action_run = WorkflowActionRun(
        org_id=org_id,
        workflow_run_id=run.id,
        action_type="RE_CREATE_CHECKLIST_ITEM",
        idempotency_key=f"phase16-re-{uuid.uuid4()}",
        input_json={"params_json": {"deal_id": str(deal.id), "title": "Agent follow-up"}},
        output_json={},
        error_json={},
    )
    db_session.add(action_run)
    db_session.commit()

    result = _execute_workflow_action(db=db_session, action_run_id=action_run.id)
    db_session.commit()

    checklist = db_session.query(REChecklistItem).filter(REChecklistItem.org_id == org_id, REChecklistItem.deal_id == deal.id).first()
    assert checklist is not None
    assert checklist.title == "Agent follow-up"
    assert result["re_checklist_item_id"] == str(checklist.id)
