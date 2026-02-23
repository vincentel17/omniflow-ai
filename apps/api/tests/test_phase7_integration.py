from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import Role


async def _select_real_estate_pack(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.post("/verticals/select", headers=headers, json={"pack_slug": "real-estate"})
    assert response.status_code == 200


@pytest.mark.integration
async def test_phase7_create_deal_apply_checklist_and_complete(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _select_real_estate_pack(client, seeded_context)
        created = await client.post(
            "/re/deals",
            headers=seeded_context,
            json={
                "deal_type": "buyer",
                "pipeline_stage": "under-contract",
                "property_address_json": {"address": "123 Main St, Charlotte NC"},
                "important_dates_json": {"contract_date": "2026-03-01T12:00:00+00:00", "closing_date": "2026-03-28T12:00:00+00:00"},
            },
        )
        assert created.status_code == 201
        deal_id = created.json()["id"]

        applied = await client.post(
            f"/re/deals/{deal_id}/checklists/apply-template",
            headers=seeded_context,
            json={"template_name": "under_contract_core"},
        )
        assert applied.status_code == 200
        assert len(applied.json()) >= 1
        item_id = applied.json()[0]["id"]

        completed = await client.post(f"/re/deals/{deal_id}/checklist-items/{item_id}/complete", headers=seeded_context)
        assert completed.status_code == 200
        assert completed.json()["status"] == "done"


@pytest.mark.integration
async def test_phase7_cma_generate_and_export_contains_disclaimer(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _select_real_estate_pack(client, seeded_context)
        created = await client.post(
            "/re/cma/reports",
            headers=seeded_context,
            json={"subject_property_json": {"address": "99 Oak Ave, Raleigh NC", "beds": 3, "baths": 2, "sqft": 1850}},
        )
        assert created.status_code == 201
        report_id = created.json()["id"]

        imported = await client.post(
            f"/re/cma/reports/{report_id}/comps/import",
            headers=seeded_context,
            json={
                "comparables": [
                    {"address": "1 Comp St", "status": "sold", "sold_price": 420000, "sqft": 1900},
                    {"address": "2 Comp St", "status": "sold", "sold_price": 410000, "sqft": 1850},
                    {"address": "3 Comp St", "status": "active", "list_price": 430000, "sqft": 2000},
                ]
            },
        )
        assert imported.status_code == 200
        assert imported.json()["inserted"] == 3

        generated = await client.post(f"/re/cma/reports/{report_id}/generate", headers=seeded_context)
        assert generated.status_code == 200
        assert "Equal Housing Opportunity." in generated.json()["narrative_text"]

        exported = await client.get(f"/re/cma/reports/{report_id}/export", headers=seeded_context)
        assert exported.status_code == 200
        assert "text/html" in exported.headers["content-type"]
        assert "CMA Report" in exported.text


@pytest.mark.integration
async def test_phase7_listing_package_pushes_to_content_queue(seeded_context: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _select_real_estate_pack(client, seeded_context)
        created = await client.post(
            "/re/listings/packages",
            headers=seeded_context,
            json={
                "property_address_json": {"address": "500 Lake View Dr, Orlando FL", "beds": 4, "baths": 3, "sqft": 2400},
                "key_features_json": ["Lake view", "Updated kitchen", "Large backyard"],
            },
        )
        assert created.status_code == 201
        listing_id = created.json()["id"]

        generated = await client.post(f"/re/listings/packages/{listing_id}/generate", headers=seeded_context)
        assert generated.status_code == 200
        assert "short" in generated.json()["description_variants_json"]

        approved = await client.post(
            f"/re/listings/packages/{listing_id}/approve",
            headers=seeded_context,
            json={"status": "approved"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        pushed = await client.post(f"/re/listings/packages/{listing_id}/push-to-content-queue", headers=seeded_context)
        assert pushed.status_code == 200
        assert pushed.json()["content_items_created"] >= 1

        content = await client.get("/content", headers=seeded_context)
        assert content.status_code == 200
        assert len(content.json()) >= 1


@pytest.mark.integration
async def test_phase7_org_isolation_for_re_endpoints(seeded_context: dict[str, str]) -> None:
    other_headers = dict(seeded_context)
    other_headers["X-Omniflow-Org-Id"] = str(uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"))
    other_headers["X-Omniflow-Role"] = Role.OWNER.value

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _select_real_estate_pack(client, seeded_context)
        await _select_real_estate_pack(client, other_headers)
        created = await client.post(
            "/re/deals",
            headers=seeded_context,
            json={
                "deal_type": "seller",
                "pipeline_stage": "lead",
                "property_address_json": {"address": "777 Private Ct"},
                "important_dates_json": {},
            },
        )
        assert created.status_code == 201
        deal_id = created.json()["id"]

        foreign = await client.get(f"/re/deals/{deal_id}", headers=other_headers)
        assert foreign.status_code == 404
