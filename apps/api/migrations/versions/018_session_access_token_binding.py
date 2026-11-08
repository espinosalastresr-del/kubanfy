"""Bind access tokens to their persisted session.

Revision ID: 018
Revises: 017
"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("access_token_jti", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_sessions_access_token_jti",
        "sessions",
        ["access_token_jti"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_access_token_jti", table_name="sessions")
    op.drop_column("sessions", "access_token_jti")
