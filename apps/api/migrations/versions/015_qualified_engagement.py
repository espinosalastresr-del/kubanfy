"""Add server-verified engagement state for anti-fraud metrics.

Revision ID: 015
Revises: 014
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "playback_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("device_id", sa.String(128), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("quality", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_position_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("listened_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspicious_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_playback_session_token_hash"),
    )
    op.create_index("ix_playback_sessions_token_hash", "playback_sessions", ["token_hash"])
    op.create_index("ix_playback_sessions_user_id", "playback_sessions", ["user_id"])
    op.create_index("ix_playback_sessions_device_id", "playback_sessions", ["device_id"])
    op.create_index("ix_playback_sessions_session_id", "playback_sessions", ["session_id"])
    op.create_index("ix_playback_sessions_track_id", "playback_sessions", ["track_id"])
    op.create_index("ix_playback_sessions_country", "playback_sessions", ["country"])

    op.create_table(
        "download_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_hash", sa.String(64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", sa.String(128), nullable=True),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("quality", sa.String(16), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_size", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("ticket_hash", name="uq_download_receipt_ticket_hash"),
    )
    op.create_index("ix_download_receipts_ticket_hash", "download_receipts", ["ticket_hash"])
    op.create_index("ix_download_receipts_user_id", "download_receipts", ["user_id"])
    op.create_index("ix_download_receipts_device_id", "download_receipts", ["device_id"])
    op.create_index("ix_download_receipts_track_id", "download_receipts", ["track_id"])

    op.create_table(
        "share_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("creator_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qualified_share", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["creator_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_share_link_token_hash"),
    )
    op.create_index("ix_share_links_token_hash", "share_links", ["token_hash"])
    op.create_index("ix_share_links_creator_user_id", "share_links", ["creator_user_id"])
    op.create_index("ix_share_links_track_id", "share_links", ["track_id"])
    op.create_index("ix_share_links_expires_at", "share_links", ["expires_at"])

    op.create_table(
        "share_opens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("share_link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_key", sa.String(128), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["share_link_id"], ["share_links.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("share_link_id", "recipient_key", name="uq_share_open_recipient"),
    )
    op.create_index("ix_share_opens_share_link_id", "share_opens", ["share_link_id"])


def downgrade() -> None:
    op.drop_table("share_opens")
    op.drop_table("share_links")
    op.drop_table("download_receipts")
    op.drop_table("playback_sessions")
