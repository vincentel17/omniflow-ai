from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://omniflow:omniflow@localhost:5432/omniflow"
    redis_url: str = "redis://localhost:6379/0"
    app_env: str = "dev"
    dev_auth_bypass: bool = False
    dev_user_id: str = "11111111-1111-1111-1111-111111111111"
    dev_org_id: str = "22222222-2222-2222-2222-222222222222"
    dev_role: str = "owner"


settings = Settings()
