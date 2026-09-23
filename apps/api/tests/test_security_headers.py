"""Security headers middleware presence."""

from app.core.middleware import SecurityHeadersMiddleware


def test_security_headers_middleware_exists() -> None:
    assert SecurityHeadersMiddleware is not None
