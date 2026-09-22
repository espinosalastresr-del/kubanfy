"""Playlists, favorites, and entitlements endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.models.playlist import FavoriteType, PlaylistVisibility
from app.schemas.library import (
    EntitlementResponse,
    FavoriteRequest,
    FavoriteResponse,
    PlaylistCreateRequest,
    PlaylistRenameRequest,
    PlaylistResponse,
    PlaylistTrackResponse,
)
from app.services.entitlement import EntitlementService
from app.services.playlist import FavoriteService, PlaylistService

router = APIRouter(tags=["library"])


# --- Playlists ---


@router.post("/playlists", response_model=PlaylistResponse, status_code=201)
async def create_playlist(
    body: PlaylistCreateRequest,
    user: CurrentUser,
    session: DbSession,
) -> PlaylistResponse:
    vis = PlaylistVisibility(body.visibility)
    pl = await PlaylistService(session).create(
        user.id, body.name, description=body.description, visibility=vis
    )
    return PlaylistResponse.model_validate(pl)


@router.get("/playlists", response_model=list[PlaylistResponse])
async def list_playlists(user: CurrentUser, session: DbSession) -> list[PlaylistResponse]:
    items = await PlaylistService(session).list_for_user(user.id)
    return [PlaylistResponse.model_validate(p) for p in items]


@router.get("/playlists/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(
    playlist_id: UUID, user: CurrentUser, session: DbSession
) -> PlaylistResponse:
    pl = await PlaylistService(session).get(playlist_id, user.id)
    return PlaylistResponse.model_validate(pl)


@router.patch("/playlists/{playlist_id}", response_model=PlaylistResponse)
async def rename_playlist(
    playlist_id: UUID,
    body: PlaylistRenameRequest,
    user: CurrentUser,
    session: DbSession,
) -> PlaylistResponse:
    pl = await PlaylistService(session).rename(playlist_id, user.id, body.name)
    return PlaylistResponse.model_validate(pl)


@router.delete("/playlists/{playlist_id}", status_code=204)
async def delete_playlist(
    playlist_id: UUID, user: CurrentUser, session: DbSession
) -> None:
    await PlaylistService(session).delete(playlist_id, user.id)


@router.post("/playlists/{playlist_id}/tracks/{track_id}", status_code=201)
async def add_to_playlist(
    playlist_id: UUID,
    track_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> PlaylistTrackResponse:
    pt = await PlaylistService(session).add_track(playlist_id, user.id, track_id)
    return PlaylistTrackResponse(
        track_id=pt.track_id, position=pt.position, added_at=pt.added_at
    )


@router.delete("/playlists/{playlist_id}/tracks/{track_id}", status_code=204)
async def remove_from_playlist(
    playlist_id: UUID,
    track_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> None:
    await PlaylistService(session).remove_track(playlist_id, user.id, track_id)


@router.get("/playlists/{playlist_id}/tracks", response_model=list[PlaylistTrackResponse])
async def list_playlist_tracks(
    playlist_id: UUID, user: CurrentUser, session: DbSession
) -> list[PlaylistTrackResponse]:
    tracks = await PlaylistService(session).list_tracks(playlist_id, user.id)
    return [
        PlaylistTrackResponse(track_id=t.track_id, position=t.position, added_at=t.added_at)
        for t in tracks
    ]


# --- Favorites ---


@router.post("/favorites", response_model=FavoriteResponse, status_code=201)
async def add_favorite(
    body: FavoriteRequest, user: CurrentUser, session: DbSession
) -> FavoriteResponse:
    fav = await FavoriteService(session).add(
        user.id, FavoriteType(body.target_type), body.target_id
    )
    return FavoriteResponse.model_validate(fav)


@router.delete("/favorites/{target_type}/{target_id}", status_code=204)
async def remove_favorite(
    target_type: str,
    target_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> None:
    await FavoriteService(session).remove(user.id, FavoriteType(target_type), target_id)


@router.get("/favorites", response_model=list[FavoriteResponse])
async def list_favorites(user: CurrentUser, session: DbSession) -> list[FavoriteResponse]:
    items = await FavoriteService(session).list_for_user(user.id)
    return [FavoriteResponse.model_validate(f) for f in items]


# --- Entitlements ---


@router.get("/entitlements", response_model=list[EntitlementResponse])
async def list_entitlements(
    user: CurrentUser, session: DbSession
) -> list[EntitlementResponse]:
    items = await EntitlementService(session).list_active(user.id)
    return [EntitlementResponse.model_validate(e) for e in items]
