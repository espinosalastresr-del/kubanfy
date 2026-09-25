"""Unit tests for LocalStorage."""

from __future__ import annotations

import pytest

from app.core.exceptions import StorageError
from app.storage.base import StorageBucket
from app.storage.local import LocalStorage


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(root=tmp_path / "store")

@pytest.fixture
def signed_storage(tmp_path):
    return LocalStorage(
        root=tmp_path / "signed-store",
        public_base_url="https://staging.example.test",
        signing_secret="test-signing-secret",
    )

@pytest.mark.asyncio
async def test_put_get_delete(storage: LocalStorage) -> None:
    obj = await storage.put("tracks/abc/master.flac", b"audio-bytes", content_type="audio/flac")
    assert obj.key == "tracks/abc/master.flac"
    assert obj.size == len(b"audio-bytes")
    assert obj.bucket == StorageBucket.CACHE

    data = await storage.get("tracks/abc/master.flac")
    assert data == b"audio-bytes"
    assert await storage.exists("tracks/abc/master.flac") is True

    await storage.delete("tracks/abc/master.flac")
    assert await storage.exists("tracks/abc/master.flac") is False


@pytest.mark.asyncio
async def test_get_missing_raises(storage: LocalStorage) -> None:
    with pytest.raises(StorageError) as exc:
        await storage.get("missing/key")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_permanent_bucket(storage: LocalStorage) -> None:
    await storage.put(
        "artists/1/releases/2/master/audio.flac",
        b"master",
        bucket=StorageBucket.PERMANENT,
    )
    assert await storage.exists(
        "artists/1/releases/2/master/audio.flac",
        bucket=StorageBucket.PERMANENT,
    )
    assert not await storage.exists(
        "artists/1/releases/2/master/audio.flac",
        bucket=StorageBucket.CACHE,
    )


@pytest.mark.asyncio
async def test_stream(storage: LocalStorage) -> None:
    payload = b"x" * 1000
    await storage.put("big.bin", payload)
    chunks = [c async for c in storage.stream("big.bin", chunk_size=256)]
    assert b"".join(chunks) == payload


@pytest.mark.asyncio
async def test_size_and_range(storage: LocalStorage) -> None:
    payload = b"0123456789"
    await storage.put("range.bin", payload)

    assert await storage.size("range.bin") == 10
    assert await storage.get_range("range.bin", 2, 5) == b"2345"
    assert await storage.get_range("range.bin", 8, 9) == b"89"


@pytest.mark.asyncio
async def test_signed_url(storage: LocalStorage) -> None:
    await storage.put("a.mp3", b"data")
    signed = await storage.signed_url("a.mp3", expires_in=60)
    assert "a.mp3" in signed.url
    assert signed.expires_in_seconds == 60


@pytest.mark.asyncio
async def test_path_traversal_rejected(storage: LocalStorage) -> None:
    with pytest.raises(StorageError):
        await storage.put("../../etc/passwd", b"nope")

@pytest.mark.asyncio
async def test_signed_https_delivery_round_trip(signed_storage: LocalStorage) -> None:
    key = "tracks/demo/low/audio.kby"
    await signed_storage.put(key, b"KBY1fixture", bucket=StorageBucket.PERMANENT)
    signed = await signed_storage.signed_url(key, bucket=StorageBucket.PERMANENT, expires_in=60)
    assert signed.url.startswith("https://staging.example.test/v1/music/local-delivery/")
    token = signed.url.rsplit("/", 1)[-1]
    bucket, decoded_key, _ = signed_storage.verify_delivery_token(token)
    assert bucket == StorageBucket.PERMANENT
    assert decoded_key == key


@pytest.mark.asyncio
async def test_signed_https_delivery_rejects_tampering(signed_storage: LocalStorage) -> None:
    with pytest.raises(StorageError):
        signed_storage.verify_delivery_token("invalid.invalid")