from __future__ import annotations

import time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from app.main import app
from app.settings import settings
import app.services.auth_security as auth_security


class _FakeRedis:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def incr(self, key: str) -> int:
        next_value = self._counts.get(key, 0) + 1
        self._counts[key] = next_value
        return next_value

    def expire(self, key: str, ttl: int) -> None:
        _ = (key, ttl)


@pytest.fixture(autouse=True)
def _security_test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = _FakeRedis()
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_cookie_secure", False)
    monkeypatch.setattr(auth_security, "get_redis_client", lambda: fake_redis)


async def _register_user(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": "InitialPass123!", "full_name": "Security User", "org_name": "Security Org"},
    )
    assert response.status_code == 201


def _csrf_header(client: AsyncClient) -> dict[str, str]:
    token = client.cookies.get(settings.auth_csrf_cookie_name)
    assert token
    return {"x-csrf-token": token}


async def test_login_rate_limit_triggers(db_session: Session, monkeypatch) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register_user(client, "rate-limit@enterprise.test")
        for _ in range(5):
            bad_login = await client.post(
                "/auth/session",
                json={"email": "rate-limit@enterprise.test", "password": "WrongPass123!"},
            )
            assert bad_login.status_code == 401

        blocked = await client.post(
            "/auth/session",
            json={"email": "rate-limit@enterprise.test", "password": "WrongPass123!"},
        )
        assert blocked.status_code == 429


async def test_session_expiry_returns_401(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "session_ttl_minutes", 1)
    monkeypatch.setattr(settings, "auth_session_ttl_seconds", 1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register_user(client, "ttl@enterprise.test")
        login = await client.post(
            "/auth/session",
            json={"email": "ttl@enterprise.test", "password": "InitialPass123!"},
        )
        assert login.status_code == 200
        token = client.cookies.get(settings.auth_cookie_name)
        assert token
        time.sleep(2)
        client.cookies.set(settings.auth_cookie_name, token)
        expired = await client.get("/auth/session")
        assert expired.status_code == 401


async def test_logout_invalidates_session_token(db_session: Session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register_user(client, "logout@enterprise.test")
        login = await client.post(
            "/auth/session",
            json={"email": "logout@enterprise.test", "password": "InitialPass123!"},
        )
        assert login.status_code == 200
        token = client.cookies.get(settings.auth_cookie_name)
        assert token
        logout = await client.post("/auth/logout", headers=_csrf_header(client))
        assert logout.status_code == 200
        client.cookies.set(settings.auth_cookie_name, token)
        replay = await client.get("/auth/session")
        assert replay.status_code in {401, 200}
        if replay.status_code == 200:
            assert replay.json()["authenticated"] is False


async def test_csrf_token_rotates_on_login_and_logout(db_session: Session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register_user(client, "csrf@enterprise.test")
        login = await client.post(
            "/auth/session",
            json={"email": "csrf@enterprise.test", "password": "InitialPass123!"},
        )
        assert login.status_code == 200
        first = client.cookies.get(settings.auth_csrf_cookie_name)
        assert first
        logout = await client.post("/auth/logout", headers=_csrf_header(client))
        assert logout.status_code == 200
        second = client.cookies.get(settings.auth_csrf_cookie_name)
        assert second
        assert first != second


async def test_security_headers_present(db_session: Session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert "content-security-policy" in response.headers
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["x-content-type-options"] == "nosniff"
