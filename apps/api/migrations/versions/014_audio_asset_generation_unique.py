"""Prevent duplicate audio assets within a track generation.

Revision ID: 014
Revises: 013_release_scheduling
"""

from alembic import op

revision = "014"
down_revision = "013_release_scheduling"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_audio_asset_track_quality_version_source",
        "audio_assets",
        ["track_id", "quality", "version", "source_type"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_audio_asset_track_quality_version_source",
        "audio_assets",
        type_="unique",
    )
