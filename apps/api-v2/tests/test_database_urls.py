from app.core.config import normalize_async_database_url, normalize_sync_database_url


def test_async_neon_url_normalizes_driver_and_ssl_parameter():
    result = normalize_async_database_url(
        "postgresql://user:pass@ep-example.neon.tech/neondb?sslmode=require&channel_binding=require"
    )
    assert result == "postgresql+asyncpg://user:pass@ep-example.neon.tech/neondb?ssl=require"


def test_sync_neon_url_uses_psycopg_driver():
    result = normalize_sync_database_url(
        "postgresql://user:pass@ep-example.neon.tech/neondb?sslmode=require"
    )
    assert result == "postgresql+psycopg://user:pass@ep-example.neon.tech/neondb?sslmode=require"


def test_sync_url_converts_asyncpg_driver():
    result = normalize_sync_database_url(
        "postgresql+asyncpg://user:pass@localhost/neondb"
    )
    assert result == "postgresql+psycopg://user:pass@localhost/neondb"
