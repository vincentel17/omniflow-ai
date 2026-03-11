from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import AuthCredential, Membership, User
from app.settings import settings


async def test_register_login_and_reset_password_flow(db_session: Session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post(
            "/auth/register",
            json={
                "email": "owner@enterprise.test",
                "password": "InitialPass123!",
                "full_name": "Owner User",
                "org_name": "Enterprise Org",
            },
        )
        assert register.status_code == 201
        payload = register.json()
        assert payload["role"] == "owner"

        login = await client.post(
            "/auth/session",
            json={"email": "owner@enterprise.test", "password": "InitialPass123!"},
        )
        assert login.status_code == 200
        assert "set-cookie" in login.headers

        org_options = await client.post(
            "/auth/org-options",
            json={"email": "owner@enterprise.test", "password": "InitialPass123!"},
        )
        assert org_options.status_code == 200
        options_payload = org_options.json()
        assert options_payload["items"]
        assert options_payload["items"][0]["role"] == "owner"

        invalid_login = await client.post(
            "/auth/session",
            json={"email": "owner@enterprise.test", "password": "WrongPass123!"},
        )
        assert invalid_login.status_code == 401

        request_reset = await client.post(
            "/auth/password-reset/request",
            json={"email": "owner@enterprise.test"},
        )
        assert request_reset.status_code == 200
        token = request_reset.json()["reset_token_preview"]
        assert token

        confirm_reset = await client.post(
            "/auth/password-reset/confirm",
            json={"token": token, "new_password": "UpdatedPass456!"},
        )
        assert confirm_reset.status_code == 200
        assert confirm_reset.json()["reset"] is True

        stale_login = await client.post(
            "/auth/session",
            json={"email": "owner@enterprise.test", "password": "InitialPass123!"},
        )
        assert stale_login.status_code == 401

        refreshed_login = await client.post(
            "/auth/session",
            json={"email": "owner@enterprise.test", "password": "UpdatedPass456!"},
        )
        assert refreshed_login.status_code == 200

    user = db_session.scalar(select(User).where(User.email == "owner@enterprise.test"))
    assert user is not None
    membership = db_session.scalar(select(Membership).where(Membership.user_id == user.id))
    assert membership is not None
    credential = db_session.scalar(select(AuthCredential).where(AuthCredential.user_id == user.id))
    assert credential is not None


async def test_password_reset_request_is_generic_for_unknown_users(db_session: Session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/password-reset/request", json={"email": "missing@enterprise.test"})
    assert response.status_code == 200
    assert response.json() == {"accepted": True, "reset_token_preview": None}


async def test_password_reset_request_hides_preview_by_default_in_production(db_session: Session, monkeypatch) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post(
            "/auth/register",
            json={
                "email": "prod-owner@enterprise.test",
                "password": "InitialPass123!",
                "full_name": "Prod Owner",
                "org_name": "Prod Org",
            },
        )
        assert register.status_code == 201

        monkeypatch.setattr(settings, "app_env", "production")
        monkeypatch.setattr(settings, "password_reset_preview_in_production", False)
        response = await client.post("/auth/password-reset/request", json={"email": "prod-owner@enterprise.test"})
        assert response.status_code == 200
        assert response.json() == {"accepted": True, "reset_token_preview": None}


async def test_password_reset_request_can_preview_with_explicit_production_toggle(db_session: Session, monkeypatch) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post(
            "/auth/register",
            json={
                "email": "fallback-owner@enterprise.test",
                "password": "InitialPass123!",
                "full_name": "Fallback Owner",
                "org_name": "Fallback Org",
            },
        )
        assert register.status_code == 201

        monkeypatch.setattr(settings, "app_env", "production")
        monkeypatch.setattr(settings, "password_reset_preview_in_production", True)
        response = await client.post("/auth/password-reset/request", json={"email": "fallback-owner@enterprise.test"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["accepted"] is True
        assert payload["reset_token_preview"]
