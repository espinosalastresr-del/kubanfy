"""Anti-fraud tests for authoritative engagement events."""

from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.services.analytics import PROTECTED_EVENT_TYPES, AnalyticsService


class _NoopSession:
    async def scalar(self, _query):
        return None

    def add(self, _value):
        return None

    async def flush(self):
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", sorted(PROTECTED_EVENT_TYPES))
async def test_client_cannot_ingest_authoritative_engagement(event_type: str) -> None:
    service = AnalyticsService(_NoopSession())  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        await service.ingest(event_type)
