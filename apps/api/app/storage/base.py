"""Storage provider abstraction.

Implementations must never expose permanent private R2 URLs.
Delivery uses short-lived signed URLs after authorization + entitlement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import BinaryIO


class StorageBucket(StrEnum):
    CACHE = "cache"
    PERMANENT = "permanent"


@dataclass(frozen=True)
class StoredObject:
    key: str
    bucket: StorageBucket
    size: int
    content_type: str | None = None
    etag: str | None = None


@dataclass(frozen=True)
class SignedUrl:
    url: str
    expires_in_seconds: int
    method: str = "GET"


class StorageProvider(ABC):
    """Abstract object storage interface."""

    @abstractmethod
    async def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        """Upload an object. Overwrites if key exists."""

    @abstractmethod
    async def get(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
    ) -> bytes:
        """Download full object body."""

    @abstractmethod
    async def stream(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
        chunk_size: int = 65536,
    ) -> AsyncIterator[bytes]:
        """Stream object in chunks."""

    @abstractmethod
    async def delete(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
    ) -> None:
        """Delete object. No-op if missing is acceptable."""

    @abstractmethod
    async def exists(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
    ) -> bool:
        """Return True if object exists."""

    @abstractmethod
    async def signed_url(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
        expires_in: int | None = None,
        method: str = "GET",
    ) -> SignedUrl:
        """Generate a short-lived signed URL for delivery."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if storage is reachable."""
