from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "KubanFy 2 Auth API"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://kubanfy:change-me@localhost:5432/kubanfy_auth_v2"
    database_url_sync: str = "postgresql+psycopg://kubanfy:change-me@localhost:5432/kubanfy_auth_v2"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    cookie_secure: bool = True
    cookie_name: str = "kubanfy_session"
    session_remember_days: int = 30
    session_short_hours: int = 12
    trust_cloudflare_headers: bool = False
    terms_version: str = "draft-pending-v1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
