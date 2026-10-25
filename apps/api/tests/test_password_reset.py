"""Password-reset workflow tests; no external database or email provider required."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import EmailProviderType, Settings
from app.models.device import SessionStatus
from app.models.password_reset import PasswordResetToken
from app.models.user import UserStatus
from app.services.password_reset import PasswordResetService


def build_service(*, user=None, email_side_effect=None):
    session = MagicMock()
    session.scalar = AsyncMock(return_value=user)
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.get = AsyncMock()
    delivery = MagicMock()
    delivery.send = AsyncMock(side_effect=email_side_effect)
    settings = Settings(
        environment="test",
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
        email_provider=EmailProviderType.RESEND,
        frontend_base_url="https://kubanfy.example",
        password_reset_token_expire_minutes=45,
    )
    return PasswordResetService(session, settings, delivery), session, delivery


@pytest.mark.asyncio
async def test_request_for_unknown_email_does_not_send_email() -> None:
    service, session, delivery = build_service(user=None)

    await service.request_reset("nobody@example.com")

    delivery.send.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_request_stores_only_digest_and_sends_fragment_token() -> None:
    user = SimpleNamespace(id=uuid4(), email="person@example.com", status=UserStatus.ACTIVE)
    service, session, delivery = build_service(user=user)

    await service.request_reset(" Person@Example.com ")

    record = session.add.call_args.args[0]
    assert isinstance(record, PasswordResetToken)
    assert record.user_id == user.id
    assert len(record.token_hash) == 64
    assert record.token_hash != record.token_hash.lower() or len(record.token_hash) == 64
    assert record.expires_at > datetime.now(UTC)
    delivery.send.assert_awaited_once()
    sent_body = delivery.send.await_args.args[2]
    reset_url = next(part for part in sent_body.split() if "reset_token=" in part)
    parsed = urlparse(reset_url)
    raw_token = parse_qs(parsed.fragment)["reset_token"][0]
    assert parsed.scheme == "https"
    assert parsed.netloc == "kubanfy.example"
    assert service._digest(raw_token) == record.token_hash
    assert raw_token not in record.token_hash
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_email_delivery_failure_invalidates_unsent_token() -> None:
    user = SimpleNamespace(id=uuid4(), email="person@example.com", status=UserStatus.ACTIVE)
    service, session, delivery = build_service(user=user, email_side_effect=RuntimeError("provider down"))

    await service.request_reset(user.email)

    record = session.add.call_args.args[0]
    assert record.used_at is not None
    assert session.flush.await_count == 2
    delivery.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_consume_rejects_expired_token_without_changing_password() -> None:
    record = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        token_hash=PasswordResetService._digest("a" * 40),
        used_at=None,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    service, session, _ = build_service()
    session.scalar.return_value = record

    changed = await service.consume("a" * 40, "StrongPassword123!")

    assert changed is False
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_consume_changes_password_and_revokes_sessions(monkeypatch) -> None:
    user_id = uuid4()
    record = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        token_hash=PasswordResetService._digest("b" * 40),
        used_at=None,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    user = SimpleNamespace(id=user_id, status=UserStatus.ACTIVE, password_hash="old-hash")
    service, session, _ = build_service()
    session.scalar.return_value = record
    session.get.return_value = user
    monkeypatch.setattr("app.services.password_reset.hash_password", lambda value: f"hashed:{value}")

    changed = await service.consume("b" * 40, "StrongPassword123!")

    assert changed is True
    assert user.password_hash == "hashed:StrongPassword123!"
    assert record.used_at is not None
    assert session.execute.await_count == 2
    session.flush.assert_awaited_once()
    assert SessionStatus.ACTIVE.value == "active"


@pytest.mark.asyncio
async def test_consume_rejects_reused_token() -> None:
    record = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        token_hash=PasswordResetService._digest("c" * 40),
        used_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    service, session, _ = build_service()
    session.scalar.return_value = record

    changed = await service.consume("c" * 40, "StrongPassword123!")

    assert changed is False
    session.get.assert_not_awaited()
