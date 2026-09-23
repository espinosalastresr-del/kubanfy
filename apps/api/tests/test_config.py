"""Unit tests for configuration."""

from __future__ import annotations

from app.core.config import Environment, Settings, get_settings


def test_default_settings(monkeypatch) -> None:
    """Settings defaults remain independent from the CI process environment."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    get_settings.cache_clear()
    s = get_settings()
    assert s.environment == Environment.DEVELOPMENT
    assert s.default_country == "CU"
    assert s.api_prefix == "/v1"
    assert len(s.jwt_secret_key) >= 32


def test_explicit_test_environment(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")
    s = Settings()
    assert s.environment == Environment.TEST


def test_allowed_audio_extensions() -> None:
    s = Settings(allowed_audio_extensions="mp3, flac, wav")
    assert s.allowed_audio_ext_list == ["mp3", "flac", "wav"]


def test_cors_origins_list() -> None:
    s = Settings(cors_origins="http://a.com, http://b.com")
    assert s.cors_origins_list == ["http://a.com", "http://b.com"]
