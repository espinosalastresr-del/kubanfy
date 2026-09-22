"""ASGI middleware: request ID, correlation, timing, Prometheus."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.logging import get_logger
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS, normalize_path

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach X-Request-ID / X-Correlation-ID and record metrics."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        correlation_id = request.headers.get("x-correlation-id") or request_id

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start
            path = normalize_path(request.url.path)
            method = request.method
            # Skip high-cardinality noise for metrics endpoint itself
            if not path.startswith("/metrics"):
                HTTP_REQUESTS.labels(method=method, path=path, status=str(status_code)).inc()
                HTTP_LATENCY.labels(method=method, path=path).observe(duration)

            # Always try to set headers on successful response
            # (on exception FastAPI error handlers build a new response)


class RequestIdHeaderMiddleware(BaseHTTPMiddleware):
    """Ensure response includes request/correlation IDs."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
        correlation_id = getattr(request.state, "correlation_id", None) or request_id
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        return response
