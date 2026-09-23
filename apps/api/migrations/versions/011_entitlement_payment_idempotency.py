"""Add durable payment order reference to entitlements.

Revision ID: 011
Revises: 010
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "entitlements",
        sa.Column("payment_order_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_entitlements_payment_order_id",
        "entitlements",
        ["payment_order_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_entitlements_payment_order_id", table_name="entitlements")
    op.drop_column("entitlements", "payment_order_id")
