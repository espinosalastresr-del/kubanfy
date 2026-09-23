"""Add release publication scheduling.

Revision ID: 013_release_scheduling
Revises: 012_offline_licenses
"""

from alembic import op
import sqlalchemy as sa

revision = "013_release_scheduling"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("releases", sa.Column("scheduled_publish_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("releases", sa.Column("scheduled_unpublish_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_releases_scheduled_publish_at", "releases", ["scheduled_publish_at"])
    op.create_index("ix_releases_scheduled_unpublish_at", "releases", ["scheduled_unpublish_at"])
    op.execute("ALTER TYPE job_type ADD VALUE IF NOT EXISTS 'publication_schedule'")


def downgrade() -> None:
    op.drop_index("ix_releases_scheduled_unpublish_at", table_name="releases")
    op.drop_index("ix_releases_scheduled_publish_at", table_name="releases")
    op.drop_column("releases", "scheduled_unpublish_at")
    op.drop_column("releases", "scheduled_publish_at")
    # PostgreSQL does not support safely removing an enum value in-place.
