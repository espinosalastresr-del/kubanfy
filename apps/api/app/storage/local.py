"""Local filesystem storage for development and tests.

Mirrors the StorageProvider interface without requiring R2.
Not for production use.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

from app.core.exceptions import StorageError
from app.core.logging import get_logger
from app.storage.base import SignedUrl, StorageBucket, StoredObject, StorageProvider

logger = get_logger(__name__)


class LocalStorage(StorageProvider):
    def __init__(self, root: str | Path = "local_storage") -> None:
        self.root = Path(root)
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
            body = data
        else:
            body = data.read()
            if isinstance(body, str):
                body = body.encode()

        def _write() -> None:
            path.write_bytes(body)

        await asyncio.to_thread(_write)
        return StoredObject(
            key=key,
            bucket=bucket,
            size=len(body),
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

        def _read_chunks():
            with path.open("rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

        for chunk in await asyncio.to_thread(lambda: list(_read_chunks())):
            yield chunk

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

    async def signed_url(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
        expires_in: int | None = None,
        method: str = "GET",
    ) -> SignedUrl:
        # Local signed URL is a pseudo-URL for tests/dev only
        expires = expires_in or 3600
        encoded = quote(key, safe="/")
        url = f"file://local/{bucket.value}/{encoded}?expires={expires}"
        return SignedUrl(url=url, expires_in_seconds=expires, method=method.upper())

    async def health_check(self) -> bool:
        return self.root.is_dir()
