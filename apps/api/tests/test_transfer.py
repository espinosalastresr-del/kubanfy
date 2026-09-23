"""Unit tests for provider source transfer safety."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.exceptions import ProviderUnavailableError
from app.providers.base import ResolvedSource
from app.services.transfer import TransferManager


@pytest.mark.asyncio
async def test_transfer_rejects_non_https() -> None:
    source = ResolvedSource(url="http://example.com/audio.mp3")
    with pytest.raises(ProviderUnavailableError):
        await TransferManager().acquire(source)


@pytest.mark.asyncio
async def test_transfer_rejects_expired_source() -> None:
    source = ResolvedSource(
        url="https://example.com/audio.mp3",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(ProviderUnavailableError):
        await TransferManager().acquire(source)
