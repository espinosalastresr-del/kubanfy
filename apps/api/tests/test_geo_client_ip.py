"""Client IP resolution tests for Cloudflare and trusted proxies."""
from __future__ import annotations

from app.core.config import Settings
from app.services.geo import GeoService


def build_geo(*, trusted_proxy_ips: str = "") -> GeoService:
    return GeoService(
        Settings(
            environment="test",
            jwt_secret_key="test-secret-key-with-at-least-32-characters",
            trusted_proxy_ips=trusted_proxy_ips,
        )
    )


def test_cloudflare_connecting_ip_is_used_for_edge_requests() -> None:
    geo = build_geo()

    resolved = geo.resolve_client_ip(
        "10.0.0.8",
        cf_connecting_ip="203.0.113.42",
        forwarded_for="198.51.100.12",
    )

    assert resolved == "203.0.113.42"


def test_invalid_cloudflare_ip_falls_back_without_trusting_untrusted_forwarded_for() -> None:
    geo = build_geo()

    resolved = geo.resolve_client_ip(
        "10.0.0.8",
        cf_connecting_ip="not-an-ip",
        forwarded_for="203.0.113.42",
    )

    assert resolved == "10.0.0.8"


def test_forwarded_for_is_used_only_when_request_peer_is_trusted() -> None:
    geo = build_geo(trusted_proxy_ips="10.0.0.8")

    resolved = geo.resolve_client_ip(
        "10.0.0.8",
        forwarded_for="203.0.113.42, 198.51.100.12",
    )

    assert resolved == "203.0.113.42"


def test_invalid_forwarded_hops_are_skipped() -> None:
    geo = build_geo(trusted_proxy_ips="10.0.0.8")

    resolved = geo.resolve_client_ip(
        "10.0.0.8",
        forwarded_for="unknown, 2001:db8::1",
    )

    assert resolved == "2001:db8::1"
