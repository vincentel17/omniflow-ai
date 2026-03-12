from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.routers import connectors as connectors_router
from app.models import AuditLog, ConnectorHealth, ConnectorWorkflowRun, Event, OAuthToken, Org, ReputationReview, ReputationSource, Role
from app.services.connector_manager import _breaker_state, get_publisher
from app.services.gbp_reviews import _mock_reviews_page, sync_gbp_reviews_page
from app.services.live_publishers import map_provider_error, missing_required_scopes
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



def _patch_worker_send_task(monkeypatch: pytest.MonkeyPatch):
    from omniflow_worker.main import app as worker_app

    def _send_task(_name: str, args=None, kwargs=None, **_):
        return {"args": args or [], "kwargs": kwargs or {}}

    monkeypatch.setattr(worker_app, "send_task", _send_task)
    return worker_app


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


def test_connector_manager_forces_mock_when_provider_live_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.connector_manager.provider_enabled_for_org", lambda **_kwargs: False)
    publisher = get_publisher(
        "meta",
        uuid.UUID("22222222-2222-2222-2222-222222222222"),
        "acct-disabled",
        db=object(),
    )
    result = publisher.publish_post({"channel": "meta", "text": "test"})
    assert result["status"] == "published"
    assert str(result["external_id"]).startswith("mock-")


def test_breaker_state_threshold_logic() -> None:
    assert _breaker_state(None, threshold=3) == "closed"

    class _Health:
        consecutive_failures = 2
        last_error_at = None

    assert _breaker_state(_Health(), threshold=3) == "closed"
    _Health.consecutive_failures = 3
    _Health.last_error_at = datetime.now(UTC)
    assert _breaker_state(_Health(), threshold=3) == "open"


def test_breaker_state_transitions_to_half_open_after_cooldown() -> None:
    class _Health:
        consecutive_failures = 3
        last_error_at = datetime.now(UTC) - timedelta(seconds=600)

    assert _breaker_state(_Health(), threshold=3) == "half_open"


def test_provider_error_taxonomy_mapping() -> None:
    assert map_provider_error(401).category == "auth"
    assert map_provider_error(429).category == "rate_limit"
    assert map_provider_error(400).category == "validation"
    assert map_provider_error(500).category == "network"
    assert map_provider_error(None).category == "unknown"


def test_missing_required_scopes_mapping() -> None:
    assert missing_required_scopes("google-business-profile", "publish", []) == ["business.manage"]
    assert missing_required_scopes("meta", "publish", ["pages_manage_posts"]) == []


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
async def test_connector_diagnostics_sanitized_fields(
    seeded_context: dict[str, str],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start = await client.post(
            "/connectors/meta/start",
            headers=seeded_context,
            json={"account_ref": "acct-diagnostics", "display_name": "Meta Diagnostics"},
        )
        state = start.json()["state"]
        callback = await client.post(
            "/connectors/meta/callback",
            headers=seeded_context,
            json={
                "state": state,
                "code": "mock",
                "account_ref": "acct-diagnostics",
                "display_name": "Meta Diagnostics",
            },
        )
        account_id = callback.json()["id"]

        diag = await client.get(f"/connectors/accounts/{account_id}/diagnostics", headers=seeded_context)
        assert diag.status_code == 200
        payload = diag.json()
        assert payload["provider"] == "meta"
        assert payload["account_ref"] == "acct-diagnostics"
        assert payload["mode_effective"] in {"mock", "live"}
        assert "token" not in json.dumps(payload).lower()


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







def test_gbp_mock_reviews_sync_is_deterministic(db_session: Session) -> None:
    org_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    account_ref = "locations/demo-location"
    db_session.add(Org(id=org_id, name="GBP Contract Org"))
    db_session.flush()
    run = ConnectorWorkflowRun(
        org_id=org_id,
        provider="google-business-profile",
        account_ref=account_ref,
        operation="reviews_sync",
        idempotency_key="gbp-sync-contract",
        status="pending",
        payload_json={},
        result_json={},
        max_attempts=3,
    )
    db_session.add(run)
    db_session.flush()

    expected = _mock_reviews_page(account_ref)
    result = sync_gbp_reviews_page(db_session, org_id=org_id, account_ref=account_ref, run=run, mode="mock")
    db_session.commit()

    reviews = db_session.scalars(
        select(ReputationReview).where(
            ReputationReview.org_id == org_id,
            ReputationReview.source == ReputationSource.GBP,
            ReputationReview.deleted_at.is_(None),
        )
    ).all()
    assert result.imported_count == len(expected)
    assert result.skipped_count == 0
    assert len(reviews) == len(expected)
    assert run.status == "completed"

@pytest.mark.integration
async def test_gbp_sync_pipeline_queues_and_processes_reviews(
    seeded_context: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker_app = _patch_worker_send_task(monkeypatch)
    admin_headers = dict(seeded_context)
    admin_headers["X-Omniflow-Role"] = Role.ADMIN.value
    org_id = uuid.UUID(admin_headers["X-Omniflow-Org-Id"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start = await client.post(
            "/connectors/google-business-profile/start",
            headers=admin_headers,
            json={"account_ref": "locations/demo-location", "display_name": "GBP Demo"},
        )
        assert start.status_code == 200
        state = start.json()["state"]

        callback = await client.post(
            "/connectors/google-business-profile/callback",
            headers=admin_headers,
            json={
                "state": state,
                "code": "mock",
                "account_ref": "locations/demo-location",
                "display_name": "GBP Demo",
            },
        )
        assert callback.status_code == 200
        account_id = callback.json()["id"]

        queued = await client.post(f"/connectors/accounts/{account_id}/sync", headers=admin_headers)
        assert queued.status_code == 200
        queued_payload = queued.json()
        assert queued_payload["status"] == "queued"

        result = worker_app.tasks["worker.connectors.gbp.sync_reviews"].run(account_id, queued_payload["idempotency_key"])
        assert result == "completed"

        diagnostics = await client.get(f"/connectors/accounts/{account_id}/diagnostics", headers=admin_headers)
        assert diagnostics.status_code == 200
        diagnostics_payload = diagnostics.json()
        assert diagnostics_payload["last_ok_at"] is not None
        assert diagnostics_payload["last_error_msg"] is None

    reviews = db_session.scalars(
        select(ReputationReview).where(
            ReputationReview.org_id == org_id,
            ReputationReview.source == ReputationSource.GBP,
            ReputationReview.deleted_at.is_(None),
        )
    ).all()
    assert len(reviews) == 2
    assert all(review.external_id for review in reviews)

    health = db_session.scalar(
        select(ConnectorHealth).where(
            ConnectorHealth.org_id == org_id,
            ConnectorHealth.provider == "google-business-profile",
            ConnectorHealth.account_ref == "locations/demo-location",
            ConnectorHealth.deleted_at.is_(None),
        )
    )
    assert health is not None
    assert health.last_ok_at is not None
    assert health.last_error_msg is None

    run = db_session.scalar(
        select(ConnectorWorkflowRun).where(
            ConnectorWorkflowRun.org_id == org_id,
            ConnectorWorkflowRun.idempotency_key == queued_payload["idempotency_key"],
            ConnectorWorkflowRun.deleted_at.is_(None),
        )
    )
    assert run is not None
    assert run.status == "completed"
    assert run.result_json["imported_count"] == 2

    audit_actions = db_session.scalars(
        select(AuditLog.action).where(
            AuditLog.org_id == org_id,
            AuditLog.action.in_(["connector.sync_requested", "connector.reviews_synced"]),
            AuditLog.deleted_at.is_(None),
        )
    ).all()
    assert "connector.sync_requested" in audit_actions
    assert "connector.reviews_synced" in audit_actions

    event_types = db_session.scalars(
        select(Event.type).where(
            Event.org_id == org_id,
            Event.type.in_(["CONNECTOR_SYNC_REQUESTED", "CONNECTOR_SYNC_SUCCESS"]),
            Event.deleted_at.is_(None),
        )
    ).all()
    assert "CONNECTOR_SYNC_REQUESTED" in event_types
    assert "CONNECTOR_SYNC_SUCCESS" in event_types


@pytest.mark.integration
@pytest.mark.parametrize(
    ("provider", "client_id_attr", "client_secret_attr", "expected_prefix"),
    [
        ("google-business-profile", "google_client_id", "google_client_secret", "https://accounts.google.com/o/oauth2/v2/auth"),
        ("meta", "meta_app_id", "meta_app_secret", "https://www.facebook.com/v19.0/dialog/oauth"),
        ("linkedin", "linkedin_client_id", "linkedin_client_secret", "https://www.linkedin.com/oauth/v2/authorization"),
    ],
)
async def test_live_oauth_start_uses_provider_authorize_url(
    provider: str,
    client_id_attr: str,
    client_secret_attr: str,
    expected_prefix: str,
    seeded_context: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(connectors_router, "connector_mode_for_org", lambda *_args, **_kwargs: "live")
    monkeypatch.setattr(connectors_router, "ensure_org_active", lambda **_kwargs: None)
    monkeypatch.setattr(settings, client_id_attr, "client-id")
    monkeypatch.setattr(settings, client_secret_attr, "client-secret")

    headers = dict(seeded_context)
    headers["X-Omniflow-Role"] = Role.ADMIN.value
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/connectors/{provider}/start",
            headers=headers,
            json={"account_ref": "pre-fill", "display_name": "Pre Fill"},
        )
    assert response.status_code == 200
    authorization_url = response.json()["authorization_url"]
    assert authorization_url.startswith(expected_prefix)
    assert "client_id=client-id" in authorization_url
    assert "redirect_uri=" in authorization_url
    assert "state=" in authorization_url


@pytest.mark.integration
@pytest.mark.parametrize(
    ("provider", "account_ref", "display_name"),
    [
        ("google-business-profile", "accounts/123", "GBP HQ"),
        ("meta", "987654321", "Meta Page"),
        ("linkedin", "linkedin-user-123", "LinkedIn User"),
    ],
)
async def test_live_oauth_callback_exchanges_tokens_and_links_account(
    provider: str,
    account_ref: str,
    display_name: str,
    seeded_context: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(connectors_router, "connector_mode_for_org", lambda *_args, **_kwargs: "live")
    monkeypatch.setattr(connectors_router, "ensure_org_active", lambda **_kwargs: None)
    if provider == "google-business-profile":
        monkeypatch.setattr(settings, "google_client_id", "client-id")
        monkeypatch.setattr(settings, "google_client_secret", "client-secret")
    elif provider == "meta":
        monkeypatch.setattr(settings, "meta_app_id", "client-id")
        monkeypatch.setattr(settings, "meta_app_secret", "client-secret")
    else:
        monkeypatch.setattr(settings, "linkedin_client_id", "client-id")
        monkeypatch.setattr(settings, "linkedin_client_secret", "client-secret")

    monkeypatch.setattr(
        connectors_router,
        "_exchange_live_oauth_code",
        lambda _provider, _code: {
            "access_token": f"live-access-{provider}",
            "refresh_token": f"live-refresh-{provider}",
            "scope": "business.manage pages_manage_posts pages_messaging w_member_social r_organization_social",
            "expires_in": 3600,
        },
    )
    monkeypatch.setattr(connectors_router, "_resolve_live_account", lambda _provider, _token: (account_ref, display_name))

    headers = dict(seeded_context)
    headers["X-Omniflow-Role"] = Role.ADMIN.value
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start = await client.post(
            f"/connectors/{provider}/start",
            headers=headers,
            json={"account_ref": "ignored", "display_name": "ignored"},
        )
        assert start.status_code == 200
        state = start.json()["state"]

        callback = await client.post(
            f"/connectors/{provider}/callback",
            headers=headers,
            json={"state": state, "code": "provider-code"},
        )
    assert callback.status_code == 200
    assert callback.json()["account_ref"] == account_ref
    assert callback.json()["display_name"] == display_name

    token = db_session.scalar(
        select(OAuthToken).where(
            OAuthToken.org_id == uuid.UUID(seeded_context["X-Omniflow-Org-Id"]),
            OAuthToken.provider == provider,
            OAuthToken.account_ref == account_ref,
            OAuthToken.deleted_at.is_(None),
        )
    )
    assert token is not None
    assert decrypt_token(token.access_token_enc) == f"live-access-{provider}"
