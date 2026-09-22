"""Unit tests for playlist/favorite/entitlement enumerations and plan codes."""

from __future__ import annotations

from app.models.entitlement import (
    EntitlementScope,
    EntitlementSource,
    EntitlementStatus,
    PlanCode,
)
from app.models.playlist import FavoriteType, PlaylistVisibility


def test_playlist_visibility() -> None:
    assert PlaylistVisibility.PRIVATE.value == "private"
    assert PlaylistVisibility.PUBLIC.value == "public"


def test_favorite_types() -> None:
    assert {t.value for t in FavoriteType} == {"track", "artist", "release"}


def test_entitlement_scopes_match_plan() -> None:
    required = {
        "user_premium",
        "track",
        "release",
        "artist_catalog",
        "artist_subscription",
    }
    assert required == {s.value for s in EntitlementScope}


def test_plan_codes() -> None:
    assert {c.value for c in PlanCode} == {"free", "premium", "family", "student"}


def test_entitlement_sources_include_google_play_isolated() -> None:
    assert EntitlementSource.GOOGLE_PLAY.value == "google_play"
    assert EntitlementStatus.ACTIVE.value == "active"
