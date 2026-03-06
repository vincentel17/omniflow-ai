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
