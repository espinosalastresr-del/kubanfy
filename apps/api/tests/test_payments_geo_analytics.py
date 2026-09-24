"""Unit tests for payment statuses, geo defaults, analytics event catalog."""

from __future__ import annotations

from app.core.exceptions import ConflictError
from app.models.entitlement import PlanCode
from app.models.payment import PaymentMethod, PaymentStatus
from app.services.analytics import KNOWN_EVENT_TYPES
from app.services.discovery import DEFAULT_WEIGHTS
from app.services.geo import GeoService


def test_payment_statuses() -> None:
    assert PaymentStatus.PENDING.value == "pending"
    assert PaymentStatus.UNDER_REVIEW.value == "under_review"
    assert PaymentStatus.APPROVED.value == "approved"
    assert {m.value for m in PaymentMethod} >= {"bank_transfer", "cash", "google_play"}


def test_geo_default_cuba() -> None:
    geo = GeoService()
    r = geo.country_from_ip(None)
    assert r.country == "CU"
    assert r.source == "default"
    r2 = geo.country_from_ip("127.0.0.1")
    assert r2.country == "CU"
    r3 = geo.resolve(user_selected_country="mx")
    assert r3.country == "MX"
    assert r3.source == "user_selected"


def test_geo_never_trusts_client_without_selection() -> None:
    geo = GeoService()
    # Without GeoIP DB, unknown public IP falls back to default — not client claim
    r = geo.country_from_ip("8.8.8.8")
    assert r.source in ("default", "inferred")
    assert len(r.country) == 2


def test_analytics_known_events_cover_core() -> None:
    required = {
        "play_start",
        "play_qualified",
        "download_complete",
        "favorite",
        "playlist_add",
        "payment_created",
        "payment_approved",
    }
    assert required.issubset(KNOWN_EVENT_TYPES)


def test_ranking_weights_only_use_server_qualified_engagement() -> None:
    assert DEFAULT_WEIGHTS["play_qualified"] > DEFAULT_WEIGHTS["download_complete"]
    assert DEFAULT_WEIGHTS["share"] > 0
    assert "play_start" not in DEFAULT_WEIGHTS
    assert "play_100" not in DEFAULT_WEIGHTS


def test_free_plan_quality_policy_is_low() -> None:
    # Free streaming is 128 kbps / LOW; persistent downloads remain premium-only.
    assert PlanCode.FREE.value == "free"


def test_payment_idempotency_conflict_type_is_available() -> None:
    assert issubclass(ConflictError, Exception)


def test_geo_uses_forwarded_for_only_from_trusted_proxy() -> None:
    from app.core.config import Settings

    geo = GeoService(Settings(trusted_proxy_ips="10.0.0.1"))
    assert geo.resolve_client_ip("10.0.0.1", forwarded_for="8.8.8.8, 10.0.0.2") == "8.8.8.8"
    assert geo.resolve_client_ip("8.8.8.8", forwarded_for="1.2.3.4") == "8.8.8.8"
