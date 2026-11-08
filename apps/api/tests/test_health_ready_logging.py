"""Health readiness: DB failures log full traceback server-side only."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_health_ready_logs_database_failure_without_leaking_details() -> None:
    """When the DB check raises, client gets type name only; logs get exception event."""
    from app.main import create_app

    app = create_app()

    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(side_effect=TypeError("simulated readiness failure"))
    mock_engine.connect = MagicMock(return_value=mock_conn)

    with (
        patch("app.core.database.engine", mock_engine),
        patch("app.main.logger") as mock_logger,
        patch("app.core.redis.get_redis") as mock_get_redis,
        patch("app.storage.get_storage") as mock_get_storage,
    ):
        redis = AsyncMock()
        redis.ping = AsyncMock(return_value=True)
        mock_get_redis.return_value = redis
        storage = AsyncMock()
        storage.health_check = AsyncMock(return_value=True)
        mock_get_storage.return_value = storage

        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["api"] == "ok"
    assert body["checks"]["database"] == "error: TypeError"
    # Client must not receive the exception message or any connection detail.
    assert "simulated" not in response.text
    assert "postgresql" not in response.text.lower()
    assert "password" not in response.text.lower()

    mock_logger.exception.assert_called()
    assert mock_logger.exception.call_args.args[0] == "database_readiness_check_failed"


def test_health_ready_source_contains_exception_log() -> None:
    """Static guard: the readiness DB except must log the structured event."""
    import inspect

    from app import main as main_mod

    source = inspect.getsource(main_mod.create_app)
    assert 'logger.exception("database_readiness_check_failed")' in source
    assert 'checks["database"] = f"error: {type(exc).__name__}"' in source



@pytest.mark.asyncio
async def test_health_ready_returns_503_and_logs_when_redis_times_out() -> None:
    """Redis is a readiness dependency: transient failures must fail readiness."""
    from app.main import create_app

    app = create_app()

    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(return_value=None)
    mock_engine.connect = MagicMock(return_value=mock_conn)

    with (
        patch("app.core.database.engine", mock_engine),
        patch("app.main.logger") as mock_logger,
        patch("app.core.redis.get_redis") as mock_get_redis,
        patch("app.storage.get_storage") as mock_get_storage,
    ):
        redis = AsyncMock()
        redis.ping = AsyncMock(side_effect=TimeoutError())
        mock_get_redis.return_value = redis
        storage = AsyncMock()
        storage.health_check = AsyncMock(return_value=True)
        mock_get_storage.return_value = storage

        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] == "error: TimeoutError"
    mock_logger.warning.assert_called_once_with(
        "redis_readiness_check_failed",
        error="TimeoutError",
    )

