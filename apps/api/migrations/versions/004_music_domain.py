"""Music domain: artists, tracks, releases, providers, assets, cache

Revision ID: 004
Revises: 003
Create Date: 2026-09-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "artists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar", sa.String(length=512), nullable=True),
        sa.Column("cover", sa.String(length=512), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=False, server_default="CU"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_artists_slug", "artists", ["slug"], unique=True)

    track_status = sa.Enum(
        "draft", "processing", "published", "hidden", "takedown", "deleted",
        name="track_status",
    )
    release_type = sa.Enum("single", "ep", "album", "compilation", name="release_type")
    audio_quality = sa.Enum("low", "medium", "lossless", name="audio_quality")
    quality_confidence = sa.Enum("verified", "unverified", name="quality_confidence")
    source_type = sa.Enum("artist_upload", "provider", "derivative", name="source_type")
    cache_entry_status = sa.Enum(
        "ready", "processing", "expired", "failed", name="cache_entry_status"
    )

    op.create_table(
        "releases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("type", release_type, nullable=False, server_default="single"),
        sa.Column("artwork_asset", sa.String(length=512), nullable=True),
        sa.Column("release_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", track_status, nullable=False, server_default="draft"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_releases_artist_id", "releases", ["artist_id"])

    op.create_table(
        "tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("isrc", sa.String(length=16), nullable=True),
        sa.Column("album_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", track_status, nullable=False, server_default="draft"),
        sa.Column("explicit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column("release_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("artwork_url", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["album_id"], ["releases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tracks_slug", "tracks", ["slug"])
    op.create_index("ix_tracks_isrc", "tracks", ["isrc"])
    op.create_index("ix_tracks_status", "tracks", ["status"])

    op.create_table(
        "track_artists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="main"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("track_id", "artist_id", "role", name="uq_track_artist_role"),
    )
    op.create_index("ix_track_artists_track_id", "track_artists", ["track_id"])
    op.create_index("ix_track_artists_artist_id", "track_artists", ["artist_id"])

    op.create_table(
        "providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_providers_name", "providers", ["name"], unique=True)

    op.create_table(
        "provider_tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_track_id", sa.String(length=255), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", "provider_track_id", name="uq_provider_track"),
    )
    op.create_index("ix_provider_tracks_track_id", "provider_tracks", ["track_id"])

    op.create_table(
        "audio_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("codec", sa.String(length=32), nullable=True),
        sa.Column("bitrate", sa.Integer(), nullable=True),
        sa.Column("bit_depth", sa.Integer(), nullable=True),
        sa.Column("sample_rate", sa.Integer(), nullable=True),
        sa.Column("channels", sa.Integer(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column("quality", audio_quality, nullable=False, server_default="medium"),
        sa.Column("quality_confidence", quality_confidence, nullable=False, server_default="unverified"),
        sa.Column("source_type", source_type, nullable=False, server_default="provider"),
        sa.Column("source_provider", sa.String(length=64), nullable=True),
        sa.Column("source_provider_track_id", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audio_assets_track_id", "audio_assets", ["track_id"])
    op.create_index("ix_audio_assets_content_hash", "audio_assets", ["content_hash"])

    op.create_table(
        "cache_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("provider_track_id", sa.String(length=255), nullable=True),
        sa.Column("quality", audio_quality, nullable=False, server_default="medium"),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requests_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requests_7d", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_cost", sa.Float(), nullable=True),
        sa.Column("status", cache_entry_status, nullable=False, server_default="ready"),
        sa.Column("retention_score", sa.Float(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cache_entries_content_hash", "cache_entries", ["content_hash"])
    op.create_index("ix_cache_entries_track_id", "cache_entries", ["track_id"])
    op.create_index("ix_cache_entries_last_accessed_at", "cache_entries", ["last_accessed_at"])
    op.create_index("ix_cache_entries_expires_at", "cache_entries", ["expires_at"])


def downgrade() -> None:
    op.drop_table("cache_entries")
    op.drop_table("audio_assets")
    op.drop_table("provider_tracks")
    op.drop_table("providers")
    op.drop_table("track_artists")
    op.drop_table("tracks")
    op.drop_table("releases")
    op.drop_table("artists")
    op.execute("DROP TYPE IF EXISTS cache_entry_status")
    op.execute("DROP TYPE IF EXISTS source_type")
    op.execute("DROP TYPE IF EXISTS quality_confidence")
    op.execute("DROP TYPE IF EXISTS audio_quality")
    op.execute("DROP TYPE IF EXISTS release_type")
    op.execute("DROP TYPE IF EXISTS track_status")
