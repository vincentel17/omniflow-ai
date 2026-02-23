from __future__ import annotations

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import AuditLog, OAuthToken, Role
from app.services.connector_manager import get_publisher
from app.services.oauth_state import consume_oauth_state, create_oauth_state
from app.services.token_vault import decrypt_token, encrypt_token
from app.settings import settings


class _FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def setex(self, key: str, ttl: int, value: str) -> bool:
        del ttl
        self.data[key] = value
        return True

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def delete(self, key: str) -> int:
        return 1 if self.data.pop(key, None) is not None else 0


def test_token_encryption_roundtrip() -> None:
    token = "sensitive-token-value"
    encrypted = encrypt_token(token)
    assert encrypted != token
    assert decrypt_token(encrypted) == token


def test_oauth_state_store_roundtrip() -> None:
    client = _FakeRedis()
    org_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    state = create_oauth_state(client, org_id, "linkedin")
    assert state
    payload = consume_oauth_state(client, state)
    assert payload is not None
    assert payload["org_id"] == str(org_id)
    assert payload["provider"] == "linkedin"
    assert consume_oauth_state(client, state) is None


def test_connector_manager_returns_mock_in_mock_mode() -> None:
    assert settings.connector_mode == "mock"
    publisher = get_publisher("linkedin", uuid.UUID("22222222-2222-2222-2222-222222222222"), "acct-1")
    result = publisher.publish_post({"channel": "linkedin", "text": "hello"})
    assert result["status"] == "published"
    assert "external_id" in result


@pytest.mark.integration
async def test_connector_link_stores_encrypted_token_and_lists_account(
    seeded_context: dict[str, str],
    db_session: Session,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start = await client.post(
            "/connectors/linkedin/start",
            headers=seeded_context,
            json={"account_ref": "acct-1", "display_name": "LinkedIn A"},
        )
        assert start.status_code == 200
        state = start.json()["state"]

        callback = await client.post(
            "/connectors/linkedin/callback",
            headers=seeded_context,
            json={
                "state": state,
                "code": "mock",
                "account_ref": "acct-1",
                "display_name": "LinkedIn A",
            },
        )
        assert callback.status_code == 200
        assert callback.json()["provider"] == "linkedin"

        listed = await client.get("/connectors/accounts", headers=seeded_context)
        assert listed.status_code == 200
        assert len(listed.json()) == 1

    token = db_session.scalar(
        select(OAuthToken).where(
            OAuthToken.org_id == uuid.UUID(seeded_context["X-Omniflow-Org-Id"]),
            OAuthToken.provider == "linkedin",
            OAuthToken.account_ref == "acct-1",
            OAuthToken.deleted_at.is_(None),
        )
    )
    assert token is not None
    assert "mock-access-linkedin-acct-1" not in token.access_token_enc
    assert decrypt_token(token.access_token_enc) == "mock-access-linkedin-acct-1"


@pytest.mark.integration
async def test_connector_org_isolation(seeded_context: dict[str, str]) -> None:
    other_headers = dict(seeded_context)
    other_headers["X-Omniflow-Org-Id"] = str(uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"))
    other_headers["X-Omniflow-Role"] = Role.OWNER.value

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start = await client.post(
            "/connectors/meta/start",
            headers=seeded_context,
            json={"account_ref": "acct-a", "display_name": "Meta A"},
        )
        state = start.json()["state"]
        callback = await client.post(
            "/connectors/meta/callback",
            headers=seeded_context,
            json={
                "state": state,
                "code": "mock",
                "account_ref": "acct-a",
                "display_name": "Meta A",
            },
        )
        assert callback.status_code == 200

        own_accounts = await client.get("/connectors/accounts", headers=seeded_context)
        assert len(own_accounts.json()) == 1

        other_accounts = await client.get("/connectors/accounts", headers=other_headers)
        assert other_accounts.status_code == 200
        assert other_accounts.json() == []


@pytest.mark.integration
async def test_disconnect_connector_soft_deletes_token_and_writes_audit(
    seeded_context: dict[str, str],
    db_session: Session,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start = await client.post(
            "/connectors/google-business-profile/start",
            headers=seeded_context,
            json={"account_ref": "gbp-1", "display_name": "GBP One"},
        )
        state = start.json()["state"]
        callback = await client.post(
            "/connectors/google-business-profile/callback",
            headers=seeded_context,
            json={
                "state": state,
                "code": "mock",
                "account_ref": "gbp-1",
                "display_name": "GBP One",
            },
        )
        account_id = callback.json()["id"]
        disconnect = await client.post(f"/connectors/accounts/{account_id}/disconnect", headers=seeded_context)
        assert disconnect.status_code == 200
        assert disconnect.json()["status"] == "disconnected"

    token = db_session.scalar(
        select(OAuthToken).where(
            OAuthToken.org_id == uuid.UUID(seeded_context["X-Omniflow-Org-Id"]),
            OAuthToken.provider == "google-business-profile",
            OAuthToken.account_ref == "gbp-1",
        )
    )
    assert token is not None
    assert token.deleted_at is not None

    audit = db_session.scalars(
        select(AuditLog).where(
            AuditLog.org_id == uuid.UUID(seeded_context["X-Omniflow-Org-Id"]),
            AuditLog.action == "connector.disconnected",
        )
    ).all()
    assert len(audit) == 1
    assert json.loads(json.dumps(audit[0].metadata_json))["provider"] == "google-business-profile"

