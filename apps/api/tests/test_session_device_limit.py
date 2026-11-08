"""Device-limit authentication error contract tests."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import ForbiddenError
from app.services.session import SessionService


@pytest.mark.asyncio
async def test_device_limit_uses_stable_error_code() -> None:
    user_id = uuid4()
    session = MagicMock()
    session.scalar = AsyncMock(
        side_effect=[
            SimpleNamespace(id=user_id),
            None,
            1,
            1,
        ]
    )
    session.scalars = AsyncMock(return_value=[])
    session.execute = AsyncMock(return_value=SimpleNamespace(rowcount=0))
    session.flush = AsyncMock()
    settings = Settings(
        environment="test",
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
        max_devices_per_user=1,
    )

    service = SessionService(session, settings)

    with pytest.raises(ForbiddenError) as error:
        await service.register_or_update_device(user_id, "new-device")

    assert error.value.status_code == 403
    assert error.value.code == "DEVICE_LIMIT_REACHED"
