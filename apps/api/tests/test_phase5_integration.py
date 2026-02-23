from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import Role


@pytest.mark.integration
async def test_phase5_presence_audit_persists_findings(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run = await client.post(
            "/presence/audits/run",
            headers=seeded_context,
            json={
                "providers_to_audit": ["gbp", "meta", "website"],
                "account_refs": {"gbp": ["acct-main"]},
                "website_url": "https://example.com",
                "run_mode": "manual",
            },
        )
        assert run.status_code == 201
        assert run.json()["status"] == "succeeded"

        findings = await client.get("/presence/findings", headers=seeded_context)
        assert findings.status_code == 200
        assert len(findings.json()) >= 1


@pytest.mark.integration
async def test_phase5_seo_plan_workitem_generate_and_approve(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        plan = await client.post("/seo/plan", headers=seeded_context, json={"target_locations": ["seattle"]})
        assert plan.status_code == 200
        assert len(plan.json()["service_pages"]) >= 1

        create = await client.post(
            "/seo/work-items",
            headers=seeded_context,
            json={
                "type": "service_page",
                "target_keyword": "seattle home buying",
                "target_location": "Seattle",
                "url_slug": "seattle-home-buying",
                "content_json": {"title": "Seattle Home Buying Guide"},
            },
        )
        assert create.status_code == 201
        work_item_id = create.json()["id"]

        generated = await client.post(f"/seo/work-items/{work_item_id}/generate", headers=seeded_context)
        assert generated.status_code == 200
        assert generated.json()["rendered_markdown"]

        approved = await client.post(
            f"/seo/work-items/{work_item_id}/approve",
            headers=seeded_context,
            json={"status": "approved"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"


@pytest.mark.integration
async def test_phase5_reputation_import_sentiment_and_draft(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        imported = await client.post(
            "/reputation/reviews/import",
            headers=seeded_context,
            json={
                "reviews": [
                    {
                        "source": "manual_import",
                        "reviewer_name": "Casey",
                        "rating": 1,
                        "review_text": "Very slow and disappointing support.",
                    }
                ]
            },
        )
        assert imported.status_code == 201
        review_id = imported.json()[0]["id"]
        assert imported.json()[0]["sentiment_json"]["urgency"] == "high"

        draft = await client.post(f"/reputation/reviews/{review_id}/draft-response", headers=seeded_context)
        assert draft.status_code == 200
        assert draft.json()["response_text"]


@pytest.mark.integration
async def test_phase5_org_isolation_for_presence_seo_reputation(seeded_context: dict[str, str]) -> None:
    other_headers = dict(seeded_context)
    other_headers["X-Omniflow-Org-Id"] = str(uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"))
    other_headers["X-Omniflow-Role"] = Role.OWNER.value

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/seo/work-items",
            headers=seeded_context,
            json={
                "type": "service_page",
                "target_keyword": "local service",
                "target_location": "Seattle",
                "url_slug": "local-service",
                "content_json": {"title": "Local Service"},
            },
        )
        work_item_id = create.json()["id"]
        foreign = await client.get(f"/seo/work-items/{work_item_id}", headers=other_headers)
        assert foreign.status_code == 404

        audit = await client.post("/presence/audits/run", headers=seeded_context, json={"run_mode": "manual"})
        assert audit.status_code == 201
        foreign_findings = await client.get("/presence/findings", headers=other_headers)
        assert foreign_findings.status_code == 200
        assert foreign_findings.json() == []

        review = await client.post(
            "/reputation/reviews/import",
            headers=seeded_context,
            json={"reviews": [{"source": "manual_import", "reviewer_name": "A", "rating": 5, "review_text": "Great"}]},
        )
        review_id = review.json()[0]["id"]
        foreign_review_draft = await client.post(f"/reputation/reviews/{review_id}/draft-response", headers=other_headers)
        assert foreign_review_draft.status_code == 404
