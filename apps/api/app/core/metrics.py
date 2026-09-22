"""Prometheus metrics for KubanFy API.

Exposed at GET /metrics (operational, not under /v1).
"""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# HTTP
HTTP_REQUESTS = Counter(
    "kubanfy_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "kubanfy_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Domain
PROVIDER_CALLS = Counter(
    "kubanfy_provider_calls_total",
    "External provider calls",
    ["provider", "operation", "status"],
)
CACHE_OPS = Counter(
    "kubanfy_cache_ops_total",
    "Cache lookups",
    ["result"],  # hit | miss
)
JOBS = Counter(
    "kubanfy_jobs_total",
    "Background jobs by type and status",
    ["type", "status"],
)
DOWNLOADS = Counter(
    "kubanfy_downloads_total",
    "Download requests",
    ["quality", "from_cache"],
)

# Gauges for readiness
DB_UP = Gauge("kubanfy_db_up", "1 if database is reachable")
REDIS_UP = Gauge("kubanfy_redis_up", "1 if redis is reachable")


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def normalize_path(path: str) -> str:
    """Collapse UUID path segments to reduce cardinality."""
    parts = []
    for part in path.split("/"):
        if not part:
            continue
        # UUID-like
        if len(part) == 36 and part.count("-") == 4:
            parts.append("{id}")
        else:
            parts.append(part)
    return "/" + "/".join(parts) if parts else "/"
