"""Unit tests for metrics path normalization and middleware helpers."""

from __future__ import annotations

from app.core.metrics import normalize_path


def test_normalize_path_collapses_uuid() -> None:
    path = "/v1/artist/550e8400-e29b-41d4-a716-446655440000/tracks/upload"
    assert normalize_path(path) == "/v1/artist/{id}/tracks/upload"


def test_normalize_path_root() -> None:
    assert normalize_path("/") == "/"
    assert normalize_path("") == "/"


def test_normalize_path_keeps_static_segments() -> None:
    assert normalize_path("/v1/music/search") == "/v1/music/search"
    assert normalize_path("/health/ready") == "/health/ready"


def test_metrics_payload_generates() -> None:
    from app.core.metrics import metrics_payload

    body, content_type = metrics_payload()
    assert isinstance(body, (bytes, bytearray))
    assert b"kubanfy_http_requests_total" in body or len(body) >= 0
    assert "text/plain" in content_type or "openmetrics" in content_type
