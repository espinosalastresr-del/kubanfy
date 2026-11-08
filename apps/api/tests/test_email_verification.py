"""Email verification token lifecycle tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest

from app.core.config import EmailProviderType, Settings
from app.models.email_verification import EmailVerificationToken
from app.models.user import UserStatus
from app.services.email_verification import EmailVerificationService


def build_service(*, user=None, delivery_error=None):
    session = MagicMock()
    session.scalar = AsyncMock(return_value=user)
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.get = AsyncMock()
    delivery = MagicMock()
    delivery.send = AsyncMock(side_effect=delivery_error)
    settings = Settings(
        environment="test",
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
        email_provider=EmailProviderType.RESEND,
        frontend_base_url="https://kubanfy.example",
        email_verification_token_expire_hours=48,
    )
    return EmailVerificationService(session, settings, delivery), session, delivery


@pytest.mark.asyncio
async def test_send_stores_only_digest_and_sends_fragment_link():
    user = SimpleNamespace(
        id=uuid4(), email="person@example.com",
        status=UserStatus.PENDING_VERIFICATION, email_verified=False,
    )
    service, session, delivery = build_service(user=user)

    await service.send_for_user(user)

    record = session.add.call_args.args[0]
    assert isinstance(record, EmailVerificationToken)
    assert len(record.token_hash) == 64
    assert record.expires_at > datetime.now(UTC)
    delivery.send.assert_awaited_once()
    text_body = delivery.send.await_args.args[2]
    link = next(part for part in text_body.split() if "verify_token=" in part)
    parsed = urlparse(link)
    raw_token = parse_qs(parsed.fragment)["verify_token"][0]
    assert parsed.scheme == "https"
    assert parsed.netloc == "kubanfy.example"
    assert service._digest(raw_token) == record.token_hash
    session.commit.assert_awaited_once()
    assert raw_token not in record.token_hash


@pytest.mark.asyncio
async def test_delivery_failure_invalidates_token():
    user = SimpleNamespace(
        id=uuid4(), email="person@example.com",
        status=UserStatus.PENDING_VERIFICATION, email_verified=False,
    )
    service, session, delivery = build_service(user=user, delivery_error=RuntimeError("offline"))

    await service.send_for_user(user)

    record = session.add.call_args.args[0]
    assert record.used_at is not None
    assert session.flush.await_count == 2
    delivery.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_consume_activates_pending_user_and_marks_token_used():
    user_id = uuid4()
    token = "x" * 40
    record = SimpleNamespace(
        id=uuid4(), user_id=user_id, token_hash=EmailVerificationService._digest(token),
        used_at=None, expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    user = SimpleNamespace(
        id=user_id, status=UserStatus.PENDING_VERIFICATION, email_verified=False,
    )
    service, session, _ = build_service()
    session.scalar.return_value = record
    session.get.return_value = user

    result = await service.consume(token)

    assert result is True
    assert user.email_verified is True
    assert user.status == UserStatus.ACTIVE
    assert record.used_at is not None
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_consume_rejects_expired_or_reused_token():
    token = "y" * 40
    record = SimpleNamespace(
        id=uuid4(), user_id=uuid4(), token_hash=EmailVerificationService._digest(token),
        used_at=datetime.now(UTC), expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    service, session, _ = build_service()
    session.scalar.return_value = record

    assert await service.consume(token) is False
    session.get.assert_not_awaited()
