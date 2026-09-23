"""KubanFy API entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Request, Response as StarletteResponse, status

from app import __version__
from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.core.exceptions import KubanFyError
from app.core.logging import get_logger, setup_logging
from app.core.redis import close_redis, init_redis

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    settings = get_settings()
    setup_logging(settings)
    logger.info(
        "starting_kubanfy_api",
        version=__version__,
        environment=settings.environment.value,
    )

    init_db(settings)
    try:
        await init_redis(settings)
        logger.info("redis_connected")
    except Exception as exc:
        # In early bootstrap we allow Redis to be optional for basic health,
        # but production readiness will require it.
        logger.warning("redis_init_failed", error=str(exc))

    yield

    await close_redis()
    await close_db()
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    # CORS — strict origins from config
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Correlation-ID"],
    )

    # Request ID + metrics (order: last added = outermost for BaseHTTPMiddleware)
    from app.core.maintenance import MaintenanceMiddleware
    from app.core.middleware import (
        RequestContextMiddleware,
        RequestIdHeaderMiddleware,
        SecurityHeadersMiddleware,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MaintenanceMiddleware)
    app.add_middleware(RequestIdHeaderMiddleware)
    app.add_middleware(RequestContextMiddleware)

    # Exception handlers
    @app.exception_handler(KubanFyError)
    async def kubanfy_error_handler(request: Request, exc: KubanFyError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "HTTP_ERROR",
                    "message": exc.detail if isinstance(exc.detail, str) else "HTTP error",
                    "details": {},
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", path=str(request.url.path))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        )

    # Health endpoints (no /v1 prefix — operational)
    @app.get("/health/live", tags=["health"])
    async def health_live() -> dict[str, str]:
        """Liveness — does not depend on external services."""
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def health_ready() -> dict[str, Any]:
        """Readiness — checks critical dependencies."""
        from app.core.metrics import DB_UP, REDIS_UP

        checks: dict[str, str] = {"api": "ok"}
        overall = "ok"

        # DB check
        try:
            from sqlalchemy import text

            from app.core.database import engine

            if engine is None:
                checks["database"] = "not_initialized"
                overall = "degraded"
                DB_UP.set(0)
            else:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                checks["database"] = "ok"
                DB_UP.set(1)
        except Exception as exc:
            checks["database"] = f"error: {type(exc).__name__}"
            overall = "not_ready"
            DB_UP.set(0)

        # Redis check
        try:
            from app.core.redis import get_redis

            r = get_redis()
            await r.ping()
            checks["redis"] = "ok"
            REDIS_UP.set(1)
        except Exception as exc:
            checks["redis"] = f"error: {type(exc).__name__}"
            REDIS_UP.set(0)
            if overall == "ok":
                overall = "degraded"

        # Storage health (non-fatal)
        try:
            from app.storage import get_storage

            ok = await get_storage().health_check()
            checks["storage"] = "ok" if ok else "degraded"
        except Exception as exc:
            checks["storage"] = f"error: {type(exc).__name__}"

        status_code = 200 if overall in ("ok", "degraded") else 503
        return JSONResponse(
            status_code=status_code,
            content={"status": overall, "checks": checks},
        )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, Any]:
        settings = get_settings()
        return {
            "status": "ok",
            "version": settings.app_version,
            "environment": settings.environment.value,
        }

    @app.get("/metrics", tags=["ops"], include_in_schema=False)
    async def metrics() -> StarletteResponse:
        from app.core.metrics import metrics_payload

        body, content_type = metrics_payload()
        return StarletteResponse(content=body, media_type=content_type)

    # Mount versioned API
    from app.api.router import api_router

    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()
