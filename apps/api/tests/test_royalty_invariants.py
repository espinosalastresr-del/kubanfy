"""Unit coverage for royalty settlement invariants."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.exceptions import ValidationError
from app.services.rights_royalty import RightsRoyaltyService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("gross_cents", "net_cents"),
    [(-1, 0), (100, -1), (100, 101)],
)
async def test_settlement_rejects_invalid_amounts(gross_cents: int, net_cents: int) -> None:
    service = RightsRoyaltyService(object())
    start = datetime.now(UTC)
    with pytest.raises(ValidationError, match="Invalid settlement period or amounts"):
        await service.create_settlement(
            artist_id=uuid4(),
            period_start=start,
            period_end=start + timedelta(days=1),
            gross_cents=gross_cents,
            net_cents=net_cents,
            idempotency_key=str(uuid4()),
        )


@pytest.mark.asyncio
async def test_settlement_rejects_reversed_period() -> None:
    service = RightsRoyaltyService(object())
    start = datetime.now(UTC)
    with pytest.raises(ValidationError, match="Invalid settlement period or amounts"):
        await service.create_settlement(
            artist_id=uuid4(),
            period_start=start,
            period_end=start,
            gross_cents=100,
            net_cents=90,
            idempotency_key=str(uuid4()),
        )
