"""License records and artist members

Revision ID: 005
Revises: 004
Create Date: 2026-09-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    artist_member_role = sa.Enum(
        "owner", "manager", "editor", "analyst", name="artist_member_role"
    )
    license_status = sa.Enum("active", "revoked", "expired", name="license_status")

    op.create_table(
        "artist_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", artist_member_role, nullable=False, server_default="editor"),
        sa.Column("permissions", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artist_id", "user_id", name="uq_artist_member"),
    )
    op.create_index("ix_artist_members_artist_id", "artist_members", ["artist_id"])
    op.create_index("ix_artist_members_user_id", "artist_members", ["user_id"])

    op.create_table(
        "license_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("accepted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "processing_allowed", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "transcoding_allowed", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "streaming_allowed", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("artwork_allowed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "metadata_allowed", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("territory", sa.String(length=16), nullable=False, server_default="WW"),
        sa.Column("duration_note", sa.String(length=128), nullable=True),
        sa.Column("rights_scope", sa.String(length=64), nullable=False, server_default="full"),
        sa.Column("license_version", sa.String(length=32), nullable=False, server_default="1.0"),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", license_status, nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["accepted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_license_records_track_id", "license_records", ["track_id"])
    op.create_index("ix_license_records_release_id", "license_records", ["release_id"])
    op.create_index("ix_license_records_artist_id", "license_records", ["artist_id"])


def downgrade() -> None:
    op.drop_table("license_records")
    op.drop_table("artist_members")
    op.execute("DROP TYPE IF EXISTS license_status")
    op.execute("DROP TYPE IF EXISTS artist_member_role")
