"""Unit tests for admin enums and anti-abuse defaults."""

from __future__ import annotations

from app.models.admin import ModerationReportType, ModerationStatus
from app.services.admin import DEFAULT_FLAGS
from app.services.anti_abuse import AntiAbuseService, RateLimitResult
import pytest


def test_moderation_types() -> None:
    assert "copyright" in {t.value for t in ModerationReportType}
    assert ModerationStatus.OPEN.value == "open"


def test_default_flags_match_plan() -> None:
    assert "artist_publishing" in DEFAULT_FLAGS
    assert "google_play" in DEFAULT_FLAGS
    assert DEFAULT_FLAGS["google_play"] is False
    assert DEFAULT_FLAGS["maintenance_mode"] is False


def test_rate_limit_result() -> None:
    r = RateLimitResult(allowed=True, remaining=5, reset_seconds=60)
    assert r.allowed is True


def test_anti_abuse_service_constructs() -> None:
    svc = AntiAbuseService()
    assert svc.settings.rate_limit_login > 0
    assert svc.settings.rate_limit_download > 0


@pytest.mark.asyncio
async def test_rate_limit_fails_closed_when_redis_is_unavailable(monkeypatch) -> None:
    from app.core.config import Environment, Settings

    def unavailable():
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr("app.services.anti_abuse.get_redis", unavailable)
    settings = Settings(environment=Environment.PRODUCTION)
    svc = AntiAbuseService(settings)

    result = await svc.check_rate_limit("test", limit=5)
    assert result.allowed is False
    assert result.remaining == 0
