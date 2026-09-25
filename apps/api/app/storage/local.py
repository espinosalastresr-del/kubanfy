"""Local filesystem storage for development and tests.

Mirrors the StorageProvider interface without requiring R2.
Not for production use.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

from app.core.exceptions import StorageError
from app.core.logging import get_logger
from app.storage.base import SignedUrl, StorageBucket, StorageProvider, StoredObject

logger = get_logger(__name__)


class LocalStorage(StorageProvider):
    def __init__(
        self,
        root: str | Path = "local_storage",
        *,
        public_base_url: str = "",
        signing_secret: str = "",
    ) -> None:
        self.root = Path(root)
        self.public_base_url = public_base_url.rstrip("/")
        self.signing_secret = signing_secret
        self.root.mkdir(parents=True, exist_ok=True)
        for b in StorageBucket:
            (self.root / b.value).mkdir(parents=True, exist_ok=True)

    def _path(self, key: str, bucket: StorageBucket) -> Path:
        # Prevent path traversal
        safe_key = key.lstrip("/").replace("..", "")
        path = (self.root / bucket.value / safe_key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise StorageError("Invalid storage key")
        return path

    async def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        path = self._path(key, bucket)
        path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, bytes):
            size = len(data)
            def _write() -> None:
                path.write_bytes(data)
        else:
            if hasattr(data, "seek"):
                data.seek(0)
            def _write() -> None:
                with path.open("wb") as out:
                    while True:
                        chunk = data.read(1024 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
            try:
                current = data.tell()
                data.seek(0, 2)
                size = data.tell()
                data.seek(current)
            except (AttributeError, OSError):
                size = 0

        await asyncio.to_thread(_write)
        return StoredObject(
            key=key,
            bucket=bucket,
            size=size,
            content_type=content_type,
        )

    async def get(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
    ) -> bytes:
        path = self._path(key, bucket)
        if not path.is_file():
            raise StorageError("Object not found", status_code=404)

        def _read() -> bytes:
            return path.read_bytes()

        return await asyncio.to_thread(_read)

    async def stream(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
        chunk_size: int = 65536,
    ) -> AsyncIterator[bytes]:
        path = self._path(key, bucket)
        if not path.is_file():
            raise StorageError("Object not found", status_code=404)

        f = await asyncio.to_thread(path.open, "rb")
        try:
            while True:
                chunk = await asyncio.to_thread(f.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(f.close)

    async def delete(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
    ) -> None:
        path = self._path(key, bucket)
        if path.is_file():
            await asyncio.to_thread(path.unlink)

    async def get_range(
        self,
        key: str,
        start: int,
        end: int,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
    ) -> bytes:
        """Read inclusive byte range [start, end]."""
        path = self._path(key, bucket)
        if not path.is_file():
            raise StorageError("Object not found", status_code=404)

        def _read() -> bytes:
            size = path.stat().st_size
            if start < 0 or start >= size:
                raise StorageError("Invalid range", status_code=416)
            length = min(end, size - 1) - start + 1
            with path.open("rb") as f:
                f.seek(start)
                return f.read(length)

        return await asyncio.to_thread(_read)

    async def size(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
    ) -> int:
        path = self._path(key, bucket)
        if not path.is_file():
            raise StorageError("Object not found", status_code=404)
        return await asyncio.to_thread(lambda: path.stat().st_size)

    async def exists(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
    ) -> bool:
        return self._path(key, bucket).is_file()

    def _delivery_token(self, *, key: str, bucket: StorageBucket, expires_at: int) -> str:
        if not self.signing_secret:
            raise StorageError("Local delivery signing secret is not configured")
        payload = json.dumps(
            {"b": bucket.value, "k": key, "e": expires_at},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        encoded = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
        signature = hmac.new(
            self.signing_secret.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).digest()
        signed = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
        return f"{encoded}.{signed}"

    def verify_delivery_token(self, token: str) -> tuple[StorageBucket, str, int]:
        if not self.signing_secret:
            raise StorageError("Local delivery signing secret is not configured")
        try:
            encoded, provided_sig = token.split(".", 1)
            expected_sig = base64.urlsafe_b64encode(
                hmac.new(
                    self.signing_secret.encode("utf-8"),
                    encoded.encode("ascii"),
                    hashlib.sha256,
                ).digest()
            ).rstrip(b"=").decode("ascii")
            if not hmac.compare_digest(provided_sig, expected_sig):
                raise ValueError("invalid signature")
            padded = encoded + "=" * ((4 - len(encoded) % 4) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
            bucket = StorageBucket(payload["b"])
            key = payload["k"]
            expires_at = int(payload["e"])
        except (binascii.Error, ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise StorageError("Invalid storage delivery token", status_code=404) from exc
        if not key or not key.endswith(".kby") or expires_at < int(time.time()):
            raise StorageError("Storage delivery token expired or invalid", status_code=404)
        return bucket, key, expires_at

    async def signed_url(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
        expires_in: int | None = None,
        method: str = "GET",
    ) -> SignedUrl:
        expires = expires_in or 3600
        normalized_method = method.upper()
        if normalized_method != "GET":
            raise StorageError("Local storage only supports GET delivery URLs")
        if self.public_base_url:
            expires_at = int(time.time()) + expires
            token = self._delivery_token(key=key, bucket=bucket, expires_at=expires_at)
            url = f"{self.public_base_url}/v1/music/local-delivery/{token}"
            return SignedUrl(url=url, expires_in_seconds=expires, method=normalized_method)
        # Development/test-only fallback; staging requires public_base_url.
        encoded = quote(key, safe="/")
        url = f"file://local/{bucket.value}/{encoded}?expires={expires}"
        return SignedUrl(url=url, expires_in_seconds=expires, method=normalized_method)

    async def health_check(self) -> bool:
        return self.root.is_dir()
