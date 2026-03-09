from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import Membership, Role, User


def _headers(user_id: uuid.UUID, org_id: uuid.UUID, role: Role) -> dict[str, str]:
    return {
        "X-Omniflow-User-Id": str(user_id),
        "X-Omniflow-Org-Id": str(org_id),
        "X-Omniflow-Role": role.value,
    }


@pytest.mark.integration
async def test_rbac_role_walk_privileged_routes(db_session, seeded_context: dict[str, str]) -> None:
    org_id = uuid.UUID(seeded_context["X-Omniflow-Org-Id"])
    owner_headers = seeded_context

    admin_id = uuid.uuid4()
    member_id = uuid.uuid4()
    db_session.add_all(
        [
            User(id=admin_id, email="rbac-admin@omniflow.local"),
            User(id=member_id, email="rbac-member@omniflow.local"),
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            Membership(org_id=org_id, user_id=admin_id, role=Role.ADMIN),
            Membership(org_id=org_id, user_id=member_id, role=Role.MEMBER),
        ]
    )
    db_session.commit()

    admin_headers = _headers(admin_id, org_id, Role.ADMIN)
    member_headers = _headers(member_id, org_id, Role.MEMBER)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner_ops = await client.get("/ops/settings", headers=owner_headers)
        admin_ops = await client.get("/ops/settings", headers=admin_headers)
        member_ops = await client.get("/ops/settings", headers=member_headers)
        assert owner_ops.status_code == 200
        assert admin_ops.status_code == 200
        assert member_ops.status_code == 403

        patch_payload = {"connector_mode": "mock"}
        owner_patch = await client.patch("/ops/settings", headers=owner_headers, json=patch_payload)
        admin_patch = await client.patch("/ops/settings", headers=admin_headers, json=patch_payload)
        member_patch = await client.patch("/ops/settings", headers=member_headers, json=patch_payload)
        assert owner_patch.status_code == 200
        assert admin_patch.status_code == 200
        assert member_patch.status_code == 403

        owner_agents = await client.get("/agents/definitions", headers=owner_headers)
        admin_agents = await client.get("/agents/definitions", headers=admin_headers)
        member_agents = await client.get("/agents/definitions", headers=member_headers)
        assert owner_agents.status_code == 200
        assert admin_agents.status_code == 200
        assert member_agents.status_code == 403

        owner_diagnostics = await client.get("/connectors/diagnostics/summary", headers=owner_headers)
        admin_diagnostics = await client.get("/connectors/diagnostics/summary", headers=admin_headers)
        member_diagnostics = await client.get("/connectors/diagnostics/summary", headers=member_headers)
        assert owner_diagnostics.status_code == 200
        assert admin_diagnostics.status_code == 200
        assert member_diagnostics.status_code == 200
