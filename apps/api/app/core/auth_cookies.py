"""Browser refresh-cookie helpers.

The refresh credential is intentionally host-only and scoped to the auth API.
"""

from __future__ import annotations

from fastapi import Response

from app.core.config import Settings
from app.core.exceptions import AuthError

REFRESH_COOKIE_NAME = "kubanfy_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"
REFRESH_COOKIE_SAME_SITE = "lax"


def ensure_allowed_web_origin(origin: str | None, settings: Settings) -> None:
    """Reject absent or non-allowlisted browser origins without normalization."""
    if origin is None or origin not in settings.cors_origins_list:
        raise AuthError("Origin is not allowed for browser authentication")


def set_refresh_cookie(
    response: Response,
    refresh_token: str,
    settings: Settings,
) -> None:
    """Set the browser refresh token as a secure, HttpOnly host-only cookie."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite=REFRESH_COOKIE_SAME_SITE,
    )


def clear_refresh_cookie(response: Response) -> None:
    """Expire the browser refresh cookie using the exact same cookie scope."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite=REFRESH_COOKIE_SAME_SITE,
    )
