from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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


def normalize_async_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    elif url.startswith("postgresql+psycopg://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql+psycopg://")

    parsed = urlsplit(url)
    query = [
        ("ssl" if key == "sslmode" else key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def normalize_sync_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql+asyncpg://")
    return url


settings = Settings()
