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
    r2_signed_url_expiry_seconds: int = 3600

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------
    jwt_secret_key: str = Field(
        default="dev-only-change-me-in-production-use-a-long-random-string",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    # Offline licenses use a separate asymmetric keypair. The private key is
    # server-only; the public key may be embedded in the mobile client.
    offline_license_algorithm: str = "RS256"
    offline_license_private_key: str = ""
    offline_license_public_key: str = ""
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    password_reset_token_expire_minutes: int = 60
    email_verification_token_expire_hours: int = 48

    # -------------------------------------------------------------------------
    # Sessions / Devices
    # -------------------------------------------------------------------------
    max_devices_per_user: int = 5
    max_concurrent_sessions: int = 3
    session_idle_timeout_minutes: int = 60
    offline_license_expire_hours: int = 72

    # -------------------------------------------------------------------------
    # Cache / TTL (hours)
    # -------------------------------------------------------------------------
    cache_ttl_low_demand_hours: int = 36
    cache_ttl_medium_demand_hours: int = 72
    cache_ttl_high_demand_hours: int = 168
    cache_single_flight_timeout_seconds: int = 120

    # -------------------------------------------------------------------------
    # Audio / Quality
    # -------------------------------------------------------------------------
    audio_low_bitrate_kbps: int = 128
    audio_medium_bitrate_kbps: int = 256
    qualified_play_seconds: int = 30
    max_upload_size_mb: int = 100
    allowed_audio_extensions: str = "mp3,flac,wav,m4a,aac,ogg"

    # -------------------------------------------------------------------------
    # Rate limits (requests per minute)
    # -------------------------------------------------------------------------
    rate_limit_login: int = 10
    rate_limit_register: int = 5
    rate_limit_search: int = 60
    rate_limit_download: int = 20
    rate_limit_preview: int = 30
    rate_limit_upload: int = 10

    # -------------------------------------------------------------------------
    # Geo
    # -------------------------------------------------------------------------
    default_country: str = "CU"
    geoip_db_path: str = ""
    trusted_proxy_ips: str = ""

    # -------------------------------------------------------------------------
    # Feature flags
    # -------------------------------------------------------------------------
    feature_artist_publishing: bool = True
    feature_monetization: bool = False
    feature_google_play: bool = False
    feature_maintenance_mode: bool = False
    feature_provider_youtube: bool = False
    maintenance_message: str = "KubanFy está en mantenimiento. Volvemos pronto."

    # -------------------------------------------------------------------------
    # Email
    # -------------------------------------------------------------------------
    email_provider: EmailProviderType = EmailProviderType.CONSOLE
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@kubanfy.local"
    resend_api_key: str = ""
    brevo_api_key: str = ""

    # -------------------------------------------------------------------------
    # Observability
    # -------------------------------------------------------------------------
    log_level: str = "INFO"
    log_format: str = "json"  # json | console
    sentry_dsn: str = ""

    # -------------------------------------------------------------------------
    # Admin bootstrap
    # -------------------------------------------------------------------------
    super_admin_email: str = "admin@kubanfy.local"
    super_admin_password: str = "change-me-immediately"

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    allowed_hosts: str = Field(default="*", description="Comma-separated hosts or *")
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:8081"

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------
    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str, info: Any) -> str:
        # In production we require a strong secret; in other envs we only warn
        # via logging later if needed.
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v

    @model_validator(mode="after")
    def production_guards(self) -> Settings:
        if self.environment == Environment.PRODUCTION:
            if self.debug:
                raise ValueError("DEBUG must be false in production")
            if (
                "change-me" in self.jwt_secret_key.lower()
                or "dev-only" in self.jwt_secret_key.lower()
            ):
                raise ValueError("JWT_SECRET_KEY must be changed for production")
            if "change-me" in self.super_admin_password.lower():
                raise ValueError("SUPER_ADMIN_PASSWORD must be changed for production")
            if self.offline_license_algorithm != "RS256":
                raise ValueError("OFFLINE_LICENSE_ALGORITHM must be RS256")
            if not self.offline_license_private_key or not self.offline_license_public_key:
                raise ValueError(
                    "OFFLINE_LICENSE_PRIVATE_KEY and OFFLINE_LICENSE_PUBLIC_KEY are required"
                )
            if not self.r2_configured:
                raise ValueError("R2_ENDPOINT, R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY are required in production")
            if self.allowed_hosts.strip() == "*":
                raise ValueError("ALLOWED_HOSTS must not be '*' in production")
            if not self.cors_origins_list:
                raise ValueError("CORS_ORIGINS must contain at least one explicit origin in production")
            if not self.trusted_proxy_ip_list:
                raise ValueError("TRUSTED_PROXY_IPS must be configured in production")
        return self

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_test(self) -> bool:
        return self.environment == Environment.TEST

    @property
    def allowed_audio_ext_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_audio_extensions.split(",") if e.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

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
