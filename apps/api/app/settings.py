from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_postgres_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://omniflow:omniflow@localhost:5432/omniflow"
    redis_url: str = "redis://localhost:6379/0"
    app_env: Literal["development", "staging", "production"] = "development"
    dev_auth_bypass: bool = False
    dev_user_id: str = "11111111-1111-1111-1111-111111111111"
    dev_org_id: str = "22222222-2222-2222-2222-222222222222"
    dev_role: str = "owner"
    ai_mode: str = "mock"
    openai_api_key: str | None = None
    connector_mode: str = "mock"
    connector_circuit_breaker_threshold: int = 3
    connector_circuit_breaker_cooldown_seconds: int = 300
    app_encryption_key: str | None = None
    token_encryption_key: str = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
    oauth_redirect_uri: str = "http://localhost:3000/api/auth/callback"
    allowed_oauth_redirect_uris: str = "http://localhost:3000/api/auth/callback"
    meta_app_id: str | None = None
    meta_app_secret: str | None = None
    linkedin_client_id: str | None = None
    linkedin_client_secret: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    provider_enable_gbp: bool = False

    def oauth_redirect_allowed(self, redirect_uri: str) -> bool:
        allowed = [item.strip() for item in self.allowed_oauth_redirect_uris.split(",") if item.strip()]
        if not allowed:
            return redirect_uri == self.oauth_redirect_uri
        return redirect_uri in allowed

    @model_validator(mode="after")
    def validate_non_dev_requirements(self) -> "Settings":
        self.database_url = _normalize_postgres_url(self.database_url)
        missing: list[str] = []
        if self.connector_mode == "live" and self.provider_enable_gbp:
            if not self.google_client_id:
                missing.append("GOOGLE_CLIENT_ID")
            if not self.google_client_secret:
                missing.append("GOOGLE_CLIENT_SECRET")
            if not self.oauth_redirect_uri:
                missing.append("OAUTH_REDIRECT_URI")
            if not self.token_encryption_key:
                missing.append("TOKEN_ENCRYPTION_KEY")
        if self.app_env == "development":
            if missing:
                joined = ", ".join(missing)
                raise ValueError(f"Missing required settings for live GBP: {joined}")
            return self
        if self.app_env == "production" and not self.app_encryption_key:
            missing.append("APP_ENCRYPTION_KEY")
        if not self.token_encryption_key:
            missing.append("TOKEN_ENCRYPTION_KEY")
        if self.connector_mode == "live" and not self.oauth_redirect_uri:
            missing.append("OAUTH_REDIRECT_URI")
        if self.ai_mode == "live" and not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required settings for {self.app_env}: {joined}")
        return self


settings = Settings()
