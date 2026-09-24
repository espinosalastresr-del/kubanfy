"""Versioned audio assets for atomic first-party replacement.

Revision ID: 009
Revises: 008
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audio_assets",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "audio_assets",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_audio_assets_is_active", "audio_assets", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_audio_assets_is_active", table_name="audio_assets")
    op.drop_column("audio_assets", "is_active")
    op.drop_column("audio_assets", "version")
