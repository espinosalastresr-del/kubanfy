"""Tests for async PostgreSQL URL normalization."""

from urllib.parse import parse_qs, urlparse

from app.core.database import normalize_asyncpg_url


def test_normalize_neon_libpq_options_for_asyncpg() -> None:
    source = (
        "postgresql://user:password@host.example/neondb"
        "?sslmode=require&channel_binding=require"
    )

    normalized = normalize_asyncpg_url(source)
    parsed = urlparse(normalized)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "postgresql+asyncpg"
    assert query["ssl"] == ["require"]
    assert "sslmode" not in query
    assert "channel_binding" not in query


def test_normalize_preserves_explicit_asyncpg_ssl_and_other_options() -> None:
    source = (
        "postgresql+asyncpg://user:password@host.example/neondb"
        "?ssl=verify-full&sslmode=require&timeout=15&application_name=kubanfy"
    )

    normalized = normalize_asyncpg_url(source)
    query = parse_qs(urlparse(normalized).query)

    assert query["ssl"] == ["verify-full"]
    assert query["timeout"] == ["15"]
    assert query["application_name"] == ["kubanfy"]
    assert "sslmode" not in query


def test_normalize_does_not_mutate_input_url() -> None:
    source = "postgres://user:password@host.example/neondb?channel_binding=require"

    normalize_asyncpg_url(source)

    assert source.endswith("?channel_binding=require")
