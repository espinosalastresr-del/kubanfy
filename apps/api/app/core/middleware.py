"""ASGI middleware: request ID, correlation, timing, Prometheus and structured request logs."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

import structlog

from app.core.logging import get_logger
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS, normalize_path

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request context, record metrics and emit one start/end trace per request."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        correlation_id = request.headers.get("x-correlation-id") or request_id

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            correlation_id=correlation_id,
        )

        start = time.perf_counter()
        status_code = 500
        response: Response | None = None
        failed = False

        path = normalize_path(request.url.path)
        method = request.method

        logger.info(
            "request_started",
            category="http.request",
            request_id=request_id,
            correlation_id=correlation_id,
            method=method,
            path=path,
            query_keys=sorted(request.query_params.keys()),
            user_agent=(request.headers.get("user-agent") or "")[:160],
            content_length=request.headers.get("content-length"),
        )

        try:
            response = await call_next(request)
            status_code = response.status_code

            # StreamingResponse returns control before the body is consumed.
            # Wrap its iterator so Render also receives first-byte, progress,
            # completion and cancellation/failure diagnostics.
            body_iterator = getattr(response, "body_iterator", None)
            if body_iterator is not None:
                async def logged_body() -> AsyncIterator[bytes]:
                    stream_started = time.perf_counter()
                    bytes_sent = 0
                    chunks = 0
                    first_byte_ms: float | None = None
                    try:
                        async for chunk in body_iterator:
                            chunks += 1
                            chunk_bytes = len(chunk)
                            bytes_sent += chunk_bytes
                            if first_byte_ms is None:
                                first_byte_ms = round(
                                    (time.perf_counter() - stream_started) * 1000,
                                    2,
                                )
                                logger.info(
                                    "stream_first_byte",
                                    category="http.stream",
                                    request_id=request_id,
                                    correlation_id=correlation_id,
                                    method=method,
                                    path=path,
                                    status_code=status_code,
                                    chunk_bytes=chunk_bytes,
                                    bytes_sent=bytes_sent,
                                    first_byte_ms=first_byte_ms,
                                )
                            yield chunk
                    except asyncio.CancelledError:
                        logger.warning(
                            "stream_cancelled",
                            category="http.stream",
                            request_id=request_id,
                            correlation_id=correlation_id,
                            method=method,
                            path=path,
                            status_code=status_code,
                            chunks=chunks,
                            bytes_sent=bytes_sent,
                            first_byte_ms=first_byte_ms,
                            elapsed_ms=round(
                                (time.perf_counter() - stream_started) * 1000,
                                2,
                            ),
                        )
                        raise
                    except Exception as exc:
                        logger.exception(
                            "stream_failed",
                            category="http.stream",
                            request_id=request_id,
                            correlation_id=correlation_id,
                            method=method,
                            path=path,
                            status_code=status_code,
                            chunks=chunks,
                            bytes_sent=bytes_sent,
                            first_byte_ms=first_byte_ms,
                            elapsed_ms=round(
                                (time.perf_counter() - stream_started) * 1000,
                                2,
                            ),
                            error_type=type(exc).__name__,
                            error=str(exc)[:500],
                        )
                        raise
                    else:
                        logger.info(
                            "stream_completed",
                            category="http.stream",
                            request_id=request_id,
                            correlation_id=correlation_id,
                            method=method,
                            path=path,
                            status_code=status_code,
                            chunks=chunks,
                            bytes_sent=bytes_sent,
                            first_byte_ms=first_byte_ms,
                            elapsed_ms=round(
                                (time.perf_counter() - stream_started) * 1000,
                                2,
                            ),
                        )

                response.body_iterator = logged_body()

            return response
        except Exception as exc:
            failed = True
            status_code = 500
            logger.exception(
                "request_failed",
                category="http.request",
                request_id=request_id,
                correlation_id=correlation_id,
                method=method,
                path=path,
                error_type=type(exc).__name__,
                error=str(exc)[:500],
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)

            if not path.startswith("/metrics"):
                HTTP_REQUESTS.labels(method=method, path=path, status=str(status_code)).inc()
                HTTP_LATENCY.labels(method=method, path=path).observe(duration_ms / 1000)

            response_is_streaming = bool(
                response is not None and getattr(response, "body_iterator", None) is not None
            )
            response_event = "response_ready" if response_is_streaming else "request_completed"
            log_method = logger.error if status_code >= 500 else (
                logger.warning if status_code >= 400 else logger.info
            )
            log_method(
                response_event,
                category="http.response",
                request_id=request_id,
                correlation_id=correlation_id,
                method=method,
                path=path,
                status_code=status_code,
                elapsed_ms=duration_ms,
                response_bytes=(
                    response.headers.get("content-length")
                    if response is not None
                    else None
                ),
                content_type=(
                    response.headers.get("content-type")
                    if response is not None
                    else None
                ),
                streaming=response_is_streaming,
                failed=failed,
            )
            structlog.contextvars.clear_contextvars()


class RequestIdHeaderMiddleware(BaseHTTPMiddleware):
    """Ensure response includes request/correlation IDs."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
        correlation_id = getattr(request.state, "correlation_id", None) or request_id
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Baseline HTTP security headers (plan: security hardening)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response
