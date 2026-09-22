"""Playlist and favorites services."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.playlist import (
    Favorite,
    FavoriteType,
    Playlist,
    PlaylistTrack,
    PlaylistVisibility,
)

logger = get_logger(__name__)


class PlaylistService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: UUID,
        name: str,
        *,
        description: str | None = None,
        visibility: PlaylistVisibility = PlaylistVisibility.PRIVATE,
    ) -> Playlist:
        pl = Playlist(
            user_id=user_id,
            name=name.strip()[:200],
            description=description,
            visibility=visibility,
        )
        self.session.add(pl)
        await self.session.flush()
        logger.info("playlist_created", playlist_id=str(pl.id), user_id=str(user_id))
        return pl

    async def get(self, playlist_id: UUID, user_id: UUID | None = None) -> Playlist:
        pl = await self.session.get(Playlist, playlist_id)
        if pl is None:
            raise NotFoundError("Playlist not found")
        if pl.visibility == PlaylistVisibility.PRIVATE:
            if user_id is None or pl.user_id != user_id:
                raise ForbiddenError("Playlist is private")
        return pl

    async def list_for_user(self, user_id: UUID) -> list[Playlist]:
        result = await self.session.execute(
            select(Playlist)
            .where(Playlist.user_id == user_id)
            .order_by(Playlist.updated_at.desc())
        )
        return list(result.scalars().all())

    async def rename(self, playlist_id: UUID, user_id: UUID, name: str) -> Playlist:
        pl = await self._owned(playlist_id, user_id)
        pl.name = name.strip()[:200]
        await self.session.flush()
        return pl

    async def delete(self, playlist_id: UUID, user_id: UUID) -> None:
        pl = await self._owned(playlist_id, user_id)
        await self.session.delete(pl)
        await self.session.flush()

    async def add_track(self, playlist_id: UUID, user_id: UUID, track_id: UUID) -> PlaylistTrack:
        pl = await self._owned(playlist_id, user_id)
        existing = await self.session.scalar(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == pl.id,
                PlaylistTrack.track_id == track_id,
            )
        )
        if existing:
            raise ConflictError("Track already in playlist")

        max_pos = await self.session.scalar(
            select(func.coalesce(func.max(PlaylistTrack.position), -1)).where(
                PlaylistTrack.playlist_id == pl.id
            )
        )
        pt = PlaylistTrack(
            playlist_id=pl.id,
            track_id=track_id,
            position=(max_pos or -1) + 1,
        )
        self.session.add(pt)
        await self.session.flush()
        return pt

    async def remove_track(self, playlist_id: UUID, user_id: UUID, track_id: UUID) -> None:
        pl = await self._owned(playlist_id, user_id)
        pt = await self.session.scalar(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == pl.id,
                PlaylistTrack.track_id == track_id,
            )
        )
        if pt is None:
            raise NotFoundError("Track not in playlist")
        await self.session.delete(pt)
        await self.session.flush()

    async def list_tracks(self, playlist_id: UUID, user_id: UUID | None = None) -> list[PlaylistTrack]:
        await self.get(playlist_id, user_id)
        result = await self.session.execute(
            select(PlaylistTrack)
            .where(PlaylistTrack.playlist_id == playlist_id)
            .order_by(PlaylistTrack.position.asc())
        )
        return list(result.scalars().all())

    async def _owned(self, playlist_id: UUID, user_id: UUID) -> Playlist:
        pl = await self.session.get(Playlist, playlist_id)
        if pl is None:
            raise NotFoundError("Playlist not found")
        if pl.user_id != user_id:
            raise ForbiddenError("Not the playlist owner")
        return pl


class FavoriteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self, user_id: UUID, target_type: FavoriteType, target_id: UUID
    ) -> Favorite:
        existing = await self.session.scalar(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.target_type == target_type,
                Favorite.target_id == target_id,
            )
        )
        if existing:
            return existing
        fav = Favorite(user_id=user_id, target_type=target_type, target_id=target_id)
        self.session.add(fav)
        await self.session.flush()
        return fav

    async def remove(
        self, user_id: UUID, target_type: FavoriteType, target_id: UUID
    ) -> None:
        fav = await self.session.scalar(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.target_type == target_type,
                Favorite.target_id == target_id,
            )
        )
        if fav is None:
            raise NotFoundError("Favorite not found")
        await self.session.delete(fav)
        await self.session.flush()

    async def list_for_user(
        self, user_id: UUID, *, target_type: FavoriteType | None = None
    ) -> list[Favorite]:
        q = select(Favorite).where(Favorite.user_id == user_id).order_by(Favorite.created_at.desc())
        if target_type:
            q = q.where(Favorite.target_type == target_type)
        result = await self.session.execute(q)
        return list(result.scalars().all())
