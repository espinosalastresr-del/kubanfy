"""Music domain models: artists, tracks, releases, provider tracks, audio assets, cache."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TrackStatus(str, enum.Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    PUBLISHED = "published"
    HIDDEN = "hidden"
    TAKEDOWN = "takedown"
    DELETED = "deleted"


class ReleaseType(str, enum.Enum):
    SINGLE = "single"
    EP = "ep"
    ALBUM = "album"
    COMPILATION = "compilation"


class AudioQuality(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    LOSSLESS = "lossless"


class QualityConfidence(str, enum.Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class SourceType(str, enum.Enum):
    ARTIST_UPLOAD = "artist_upload"
    PROVIDER = "provider"
    DERIVATIVE = "derivative"


class CacheEntryStatus(str, enum.Enum):
    READY = "ready"
    PROCESSING = "processing"
    EXPIRED = "expired"
    FAILED = "failed"


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cover: Mapped[str | None] = mapped_column(String(512), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="CU")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Release(Base):
    __tablename__ = "releases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[ReleaseType] = mapped_column(
        Enum(ReleaseType, name="release_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ReleaseType.SINGLE,
    )
    artwork_asset: Mapped[str | None] = mapped_column(String(512), nullable=True)
    release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[TrackStatus] = mapped_column(
        Enum(TrackStatus, name="track_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TrackStatus.DRAFT,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_publish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    scheduled_unpublish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    isrc: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    album_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("releases.id", ondelete="SET NULL"), nullable=True
    )
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("releases.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[TrackStatus] = mapped_column(
        Enum(
            TrackStatus,
            name="track_status",
            values_callable=lambda x: [e.value for e in x],
            create_constraint=False,
        ),
        nullable=False,
        default=TrackStatus.DRAFT,
        index=True,
    )
    explicit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    artwork_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TrackArtist(Base):
    __tablename__ = "track_artists"
    __table_args__ = (
        UniqueConstraint("track_id", "artist_id", "role", name="uq_track_artist_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="main"
    )  # main, featured, composer, producer, remixer
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProviderTrack(Base):
    __tablename__ = "provider_tracks"
    __table_args__ = (
        UniqueConstraint("provider_id", "provider_track_id", name="uq_provider_track"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    provider_track_id: Mapped[str] = mapped_column(String(255), nullable=False)
    track_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    metadata_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    last_resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class AudioAsset(Base):
    __tablename__ = "audio_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    codec: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bit_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    quality: Mapped[AudioQuality] = mapped_column(
        Enum(AudioQuality, name="audio_quality", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AudioQuality.MEDIUM,
    )
    quality_confidence: Mapped[QualityConfidence] = mapped_column(
        Enum(
            QualityConfidence,
            name="quality_confidence",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=QualityConfidence.UNVERIFIED,
    )
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SourceType.PROVIDER,
    )
    source_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_provider_track_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    track_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_track_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quality: Mapped[AudioQuality] = mapped_column(
        Enum(
            AudioQuality,
            name="audio_quality",
            values_callable=lambda x: [e.value for e in x],
            create_constraint=False,
        ),
        nullable=False,
        default=AudioQuality.MEDIUM,
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests_24h: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests_7d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[CacheEntryStatus] = mapped_column(
        Enum(
            CacheEntryStatus,
            name="cache_entry_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=CacheEntryStatus.READY,
    )
    retention_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
