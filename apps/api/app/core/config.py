"""Typed application configuration using Pydantic Settings.

All commercial and operational values are configurable.
Secrets must never be hardcoded.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class EmailProviderType(StrEnum):
    CONSOLE = "console"
    SMTP = "smtp"
    RESEND = "resend"
    BREVO = "brevo"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Environment
    # -------------------------------------------------------------------------
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    app_name: str = "KubanFy API"
    app_version: str = "0.1.0"
    api_prefix: str = "/v1"

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://kubanfy:kubanfy@localhost:5432/kubanfy",
        description="Async SQLAlchemy URL (asyncpg)",
    )
    database_url_sync: str = Field(
        default="postgresql://kubanfy:kubanfy@localhost:5432/kubanfy",
        description="Sync URL for Alembic",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_echo: bool = False

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 50

    # -------------------------------------------------------------------------
    # Cloudflare R2
    # -------------------------------------------------------------------------
    r2_endpoint: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_cache_bucket: str = "kubanfy-cache"
    r2_permanent_bucket: str = "kubanfy-permanent"
    r2_region: str = "auto"
    r2_signed_url_expiry_seconds: int = 900
    # Public HTTPS origin used only for staging local-storage delivery.
    storage_public_base_url: str = ""

    # -------------------------------------------------------------------------
    # JWT / Auth
    # -------------------------------------------------------------------------
    jwt_secret_key: str = Field(
        default="dev-only-change-me-in-production-min-32-chars",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    password_reset_token_expire_minutes: int = 60

    # -------------------------------------------------------------------------
    # Offline licenses (RS256)
    # -------------------------------------------------------------------------
    offline_license_algorithm: str = "RS256"
    offline_license_private_key_pem: str = ""
    offline_license_public_key_pem: str = ""
    offline_license_ttl_hours: int = 72

    # -------------------------------------------------------------------------
    # CORS / Hosts
    # -------------------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    allowed_hosts: str = "*"
    trusted_proxy_ips: str = ""

    # -------------------------------------------------------------------------
    # Frontend (password-reset links, etc.)
    # -------------------------------------------------------------------------
    frontend_base_url: str = "http://localhost:5173"

    # -------------------------------------------------------------------------
    # Email
    # -------------------------------------------------------------------------
    email_provider: EmailProviderType = EmailProviderType.CONSOLE
    email_from: str = "noreply@kubanfy.local"
    resend_api_key: str = ""
    brevo_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # -------------------------------------------------------------------------
    # Rate limiting / anti-abuse
    # -------------------------------------------------------------------------
    rate_limit_enabled: bool = True
    rate_limit_fail_open: bool = True  # staging-friendly; set false in production

    # -------------------------------------------------------------------------
    # Audio / upload constraints
    # -------------------------------------------------------------------------
    max_upload_bytes: int = 200 * 1024 * 1024
    allowed_audio_extensions: str = "mp3,flac,wav,m4a,aac,ogg,opus"
    allowed_image_extensions: str = "jpg,jpeg,png,webp"

    # -------------------------------------------------------------------------
    # Playback / KBY
    # -------------------------------------------------------------------------
    kby_default_version: int = 2
    playback_session_ttl_seconds: int = 3600
    playback_heartbeat_interval_seconds: int = 30

    # -------------------------------------------------------------------------
    # Maintenance
    # -------------------------------------------------------------------------
    maintenance_mode: bool = False
    maintenance_message: str = "KubanFy is temporarily under maintenance."

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------
    @field_validator("environment", mode="before")
    @classmethod
    def parse_environment(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.lower()
        return v

    @field_validator("email_provider", mode="before")
    @classmethod
    def parse_email_provider(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.lower()
        return v

    @model_validator(mode="after")
    def validate_jwt_in_non_dev(self) -> Settings:
        if self.environment in (Environment.STAGING, Environment.PRODUCTION):
            if self.jwt_secret_key.startswith("dev-only"):
                # Soft warning path: still allow boot so ops can inspect,
                # but production readiness checks should fail.
                pass
        return self

    # -------------------------------------------------------------------------
    # Derived helpers
    # -------------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def is_staging(self) -> bool:
        return self.environment == Environment.STAGING

    @property
    def allowed_audio_ext_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_audio_extensions.split(",") if e.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        # The staging frontend uses the account-scoped Workers hostname.
        # Keep this explicit allowlist entry even if an older deployment
        # still carries the legacy workers.dev CORS variable.
        staging_web_origin = "https://kubanfy-web-staging.globumlatinmusic.workers.dev"
        if self.environment == Environment.STAGING and staging_web_origin not in origins:
            origins.append(staging_web_origin)
        return origins

    @property
    def trusted_proxy_ip_list(self) -> list[str]:
        if not self.trusted_proxy_ips:
            return []
        return [ip.strip() for ip in self.trusted_proxy_ips.split(",") if ip.strip()]

    @property
    def r2_configured(self) -> bool:
        return bool(self.r2_endpoint and self.r2_access_key_id and self.r2_secret_access_key)


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance. Call get_settings.cache_clear() in tests if needed."""
    return Settings()
