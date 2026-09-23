"""Maintenance mode middleware (plan §118 / §37)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.config import get_settings

# Paths always allowed during maintenance
_ALLOW_PREFIXES = (
    "/health",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class MaintenanceMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        settings = get_settings()
        if not settings.feature_maintenance_mode:
            return await call_next(request)

        path = request.url.path
        if any(path == p or path.startswith(p + "/") for p in _ALLOW_PREFIXES):
            return await call_next(request)
        # Allow super-admin style login only is complex; block API broadly
        if path.startswith("/v1/auth/login") or path.startswith("/v1/auth/refresh"):
            return await call_next(request)

        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "maintenance",
                    "message": settings.maintenance_message,
                }
            },
            headers={"Retry-After": "300"},
        )
