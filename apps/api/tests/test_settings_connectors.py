from pydantic import ValidationError

from app.settings import Settings


def test_live_gbp_requires_required_env_settings() -> None:
    try:
        Settings(
            app_env="development",
            connector_mode="live",
            provider_enable_gbp=True,
            google_client_id=None,
            google_client_secret=None,
            oauth_redirect_uri="",
            token_encryption_key="",
        )
    except ValidationError as exc:
        message = str(exc)
        assert "Missing required settings for live GBP" in message
        assert "GOOGLE_CLIENT_ID" in message
        assert "GOOGLE_CLIENT_SECRET" in message
        assert "OAUTH_REDIRECT_URI" in message
        assert "TOKEN_ENCRYPTION_KEY" in message
    else:
        raise AssertionError("expected live GBP settings validation to fail")


def test_staging_requires_deployment_env_contract() -> None:
    try:
        Settings(
            app_env="staging",
            database_url="",
            redis_url="",
            token_encryption_key="",
            oauth_redirect_uri="",
            ai_mode="mock",
            connector_mode="mock",
            ads_mode="mock",
        )
    except ValidationError as exc:
        message = str(exc)
        assert "DATABASE_URL" in message
        assert "REDIS_URL" in message
        assert "TOKEN_ENCRYPTION_KEY" in message
    else:
        raise AssertionError("expected staging settings validation to fail")


def test_settings_reject_invalid_modes() -> None:
    try:
        Settings(app_env="development", ads_mode="invalid")
    except ValidationError as exc:
        assert "ADS_MODE must be one of: mock, live" in str(exc)
    else:
        raise AssertionError("expected mode validation to fail")


def test_production_requires_jwt_secret() -> None:
    try:
        Settings(app_env="production", jwt_secret=None, app_encryption_key="a" * 32, token_encryption_key="a" * 44)
    except ValidationError as exc:
        assert "JWT_SECRET" in str(exc)
    else:
        raise AssertionError("expected jwt secret validation to fail")
