"""Add durable payment order reference to entitlements.

Revision ID: 011_entitlement_payment_idempotency
Revises: 010_rights_royalties
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "011_entitlement_payment_idempotency"
down_revision = "010_rights_royalties"
branch_labels = None
depends_on = None


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
