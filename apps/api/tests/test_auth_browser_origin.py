"""Exact Origin validation for browser refresh-cookie operations."""

from __future__ import annotations

import pytest

from app.core.auth_cookies import ensure_allowed_web_origin
from app.core.config import Settings
from app.core.exceptions import AuthError


WEB_ORIGIN = "https://kubanfy-web-staging.globumlatinmusic.workers.dev"


def settings() -> Settings:
    return Settings(environment="staging", cors_origins=WEB_ORIGIN)


def test_allowed_origin_matches_exact_configured_origin() -> None:
    ensure_allowed_web_origin(WEB_ORIGIN, settings())


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "",
        "https://evil.example",
        "https://kubanfy-web-staging.globumlatinmusic.workers.dev.evil.example",
        "https://kubanfy-web-staging.globumlatinmusic.workers.dev/",
        "null",
    ],
)
def test_missing_or_non_exact_origin_is_rejected(origin: str | None) -> None:
    with pytest.raises(AuthError):
        ensure_allowed_web_origin(origin, settings())
