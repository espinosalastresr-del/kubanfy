"""Unit tests for asyncpg URL normalization (sslmode → ssl)."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from app.core.database import normalize_asyncpg_url


def test_sslmode_require_converted_to_ssl() -> None:
    raw = "postgresql://user:pass@host.example/db?sslmode=require"
    out = normalize_asyncpg_url(raw)
    parsed = urlparse(out)
    assert parsed.scheme == "postgresql+asyncpg"
    qs = parse_qs(parsed.query)
    assert qs.get("ssl") == ["require"]
    assert "sslmode" not in qs
    # credentials and host preserved
    assert parsed.hostname == "host.example"
    assert parsed.username == "user"
    assert parsed.password == "pass"
    assert parsed.path == "/db"


def test_url_without_ssl_params_unchanged_aside_from_scheme() -> None:
    raw = "postgresql://user:pass@localhost:5432/kubanfy"
    out = normalize_asyncpg_url(raw)
    assert out == "postgresql+asyncpg://user:pass@localhost:5432/kubanfy"
    qs = parse_qs(urlparse(out).query)
    assert "ssl" not in qs
    assert "sslmode" not in qs


def test_existing_ssl_param_preserved_sslmode_dropped() -> None:
    raw = "postgresql://u:p@h/db?ssl=require&application_name=kubanfy"
    out = normalize_asyncpg_url(raw)
    qs = parse_qs(urlparse(out).query)
    assert qs.get("ssl") == ["require"]
    assert "sslmode" not in qs
    assert qs.get("application_name") == ["kubanfy"]


def test_sslmode_and_ssl_both_present_keeps_ssl_drops_sslmode() -> None:
    raw = "postgresql://u:p@h/db?sslmode=require&ssl=true"
    out = normalize_asyncpg_url(raw)
    qs = parse_qs(urlparse(out).query)
    assert qs.get("ssl") == ["true"]
    assert "sslmode" not in qs


def test_other_query_params_preserved() -> None:
    raw = (
        "postgresql://u:p@ep-example.neon.tech/neondb"
        "?sslmode=require&channel_binding=require&options=-c%20search_path%3Dpublic"
    )
    out = normalize_asyncpg_url(raw)
    qs = parse_qs(urlparse(out).query)
    assert qs.get("ssl") == ["require"]
    assert "sslmode" not in qs
    assert "channel_binding" not in qs
    assert qs.get("options") == ["-c search_path=public"]


def test_postgres_scheme_rewritten() -> None:
    raw = "postgres://u:p@h/db?sslmode=require"
    out = normalize_asyncpg_url(raw)
    assert out.startswith("postgresql+asyncpg://")
    assert parse_qs(urlparse(out).query).get("ssl") == ["require"]


def test_already_asyncpg_scheme_sslmode_converted() -> None:
    raw = "postgresql+asyncpg://u:p@h/db?sslmode=verify-full"
    out = normalize_asyncpg_url(raw)
    assert out.startswith("postgresql+asyncpg://")
    qs = parse_qs(urlparse(out).query)
    assert qs.get("ssl") == ["verify-full"]
    assert "sslmode" not in qs


def test_sync_url_not_passed_through_helper_keeps_sslmode() -> None:
    """DATABASE_URL_SYNC must keep libpq sslmode for psycopg/Alembic sync use.

    This test documents the contract: callers must NOT run sync URLs through
    normalize_asyncpg_url. The setting value itself is never mutated.
    """
    sync_url = "postgresql://u:p@h/db?sslmode=require"
    # Simulate what sync consumers should do: use the URL as-is.
    assert "sslmode=require" in sync_url
    assert "ssl=" not in sync_url or "sslmode" in sync_url
    # After async normalization of a *copy*, the original string is unchanged.
    _ = normalize_asyncpg_url(sync_url)
    assert sync_url == "postgresql://u:p@h/db?sslmode=require"


def test_normalize_does_not_log_or_embed_secrets_in_return_structure() -> None:
    """Returned URL may contain credentials (needed to connect) but helper
    must not raise or attach side-channel data. Logging is the caller's job;
    we only assert the pure function returns a plain str.
    """
    raw = "postgresql://secret_user:secret_pass@host/db?sslmode=require"
    out = normalize_asyncpg_url(raw)
    assert isinstance(out, str)
    assert out.startswith("postgresql+asyncpg://")
