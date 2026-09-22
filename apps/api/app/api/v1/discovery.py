"""Discovery endpoints: home, local artists, top 50, new releases."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from app.api.deps import DbSession, OptionalUser
from app.services.discovery import DiscoveryService
from app.services.geo import GeoService

router = APIRouter(prefix="/discovery", tags=["discovery"])


def _country_from_request(request: Request, override: str | None) -> str:
    if override and len(override) == 2:
        return override.upper()
    geo = GeoService()
    ip = request.client.host if request.client else None
    fwd = request.headers.get("x-forwarded-for")
    real_ip = geo.resolve_client_ip(ip, forwarded_for=fwd)
    return geo.resolve(ip=real_ip).country


@router.get("/home")
async def discovery_home(
    request: Request,
    session: DbSession,
    user: OptionalUser,
    country: str | None = Query(default=None, min_length=2, max_length=2),
) -> dict[str, Any]:
    c = _country_from_request(request, country)
    return await DiscoveryService(session).home(country=c)


@router.get("/local-artists")
async def local_artists(
    request: Request,
    session: DbSession,
    country: str | None = Query(default=None, min_length=2, max_length=2),
    limit: int = Query(20, ge=1, le=50),
) -> list[dict[str, Any]]:
    c = _country_from_request(request, country)
    artists = await DiscoveryService(session).local_artists(c, limit=limit)
    return [
        {"id": a.id, "name": a.name, "slug": a.slug, "country": a.country, "verified": a.verified}
        for a in artists
    ]


@router.get("/top50")
async def top50(
    request: Request,
    session: DbSession,
    country: str | None = Query(default=None, min_length=2, max_length=2),
    global_scope: bool = Query(False, alias="global"),
    limit: int = Query(50, ge=1, le=50),
) -> list[dict[str, Any]]:
    c = None if global_scope else _country_from_request(request, country)
    return await DiscoveryService(session).top_tracks(country=c, limit=limit)


@router.get("/new-releases")
async def new_releases(
    session: DbSession,
    limit: int = Query(20, ge=1, le=50),
) -> list[dict[str, Any]]:
    tracks = await DiscoveryService(session).new_releases(limit=limit)
    return [{"id": t.id, "title": t.title, "duration": t.duration, "status": t.status.value} for t in tracks]
