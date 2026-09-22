"""Cloudflare R2 storage adapter (S3-compatible via aioboto3).

Requires R2 credentials in settings. If not configured, callers should
use LocalStorage or mark storage as unavailable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, BinaryIO

import aioboto3
from botocore.config import Config

from app.core.config import Settings, get_settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger
from app.storage.base import SignedUrl, StorageBucket, StoredObject, StorageProvider

logger = get_logger(__name__)


class R2Storage(StorageProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.r2_configured:
            raise StorageError(
                "R2 is not configured (missing endpoint or credentials)",
                code="STORAGE_ERROR",
            )
        self._session = aioboto3.Session()
        self._bucket_map = {
            StorageBucket.CACHE: self.settings.r2_cache_bucket,
            StorageBucket.PERMANENT: self.settings.r2_permanent_bucket,
        }

    def _bucket_name(self, bucket: StorageBucket) -> str:
        return self._bucket_map[bucket]

    @asynccontextmanager
    async def _client(self):  # type: ignore[no-untyped-def]
        async with self._session.client(
            "s3",
            endpoint_url=self.settings.r2_endpoint,
            aws_access_key_id=self.settings.r2_access_key_id,
            aws_secret_access_key=self.settings.r2_secret_access_key,
            region_name=self.settings.r2_region,
            config=Config(signature_version="s3v4"),
        ) as client:
            yield client

    async def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        body: bytes
        if isinstance(data, bytes):
            body = data
        else:
            body = data.read()
            if isinstance(body, str):
                body = body.encode()

        extra: dict[str, Any] = {}
        if content_type:
            extra["ContentType"] = content_type
        if metadata:
            extra["Metadata"] = metadata

        try:
            async with self._client() as client:
                resp = await client.put_object(
                    Bucket=self._bucket_name(bucket),
                    Key=key,
                    Body=body,
                    **extra,
                )
            return StoredObject(
                key=key,
                bucket=bucket,
                size=len(body),
                content_type=content_type,
                etag=resp.get("ETag"),
            )
        except Exception as exc:
            logger.exception("r2_put_failed", key=key, bucket=bucket.value)
            raise StorageError(f"Failed to store object: {type(exc).__name__}") from exc

    async def get(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
    ) -> bytes:
        try:
            async with self._client() as client:
                resp = await client.get_object(
                    Bucket=self._bucket_name(bucket),
                    Key=key,
                )
                async with resp["Body"] as stream:
                    return await stream.read()
        except client.exceptions.NoSuchKey:  # type: ignore[name-defined]
            raise StorageError("Object not found", status_code=404) from None
        except Exception as exc:
            if "NoSuchKey" in type(exc).__name__ or "404" in str(exc):
                raise StorageError("Object not found", status_code=404) from exc
            logger.exception("r2_get_failed", key=key)
            raise StorageError(f"Failed to get object: {type(exc).__name__}") from exc

    async def stream(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
        chunk_size: int = 65536,
    ) -> AsyncIterator[bytes]:
        async with self._client() as client:
            try:
                resp = await client.get_object(
                    Bucket=self._bucket_name(bucket),
                    Key=key,
                )
            except Exception as exc:
                if "NoSuchKey" in type(exc).__name__ or "404" in str(exc):
                    raise StorageError("Object not found", status_code=404) from exc
                raise StorageError(f"Failed to stream object: {type(exc).__name__}") from exc

            body = resp["Body"]
            while True:
                chunk = await body.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    async def delete(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
    ) -> None:
        try:
            async with self._client() as client:
                await client.delete_object(
                    Bucket=self._bucket_name(bucket),
                    Key=key,
                )
        except Exception as exc:
            logger.exception("r2_delete_failed", key=key)
            raise StorageError(f"Failed to delete object: {type(exc).__name__}") from exc

    async def exists(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
    ) -> bool:
        try:
            async with self._client() as client:
                await client.head_object(
                    Bucket=self._bucket_name(bucket),
                    Key=key,
                )
            return True
        except Exception:
            return False

    async def signed_url(
        self,
        key: str,
        *,
        bucket: StorageBucket = StorageBucket.CACHE,
        expires_in: int | None = None,
        method: str = "GET",
    ) -> SignedUrl:
        expires = expires_in or self.settings.r2_signed_url_expiry_seconds
        client_method = "get_object" if method.upper() == "GET" else "put_object"
        try:
            async with self._client() as client:
                url = await client.generate_presigned_url(
                    client_method,
                    Params={
                        "Bucket": self._bucket_name(bucket),
                        "Key": key,
                    },
                    ExpiresIn=expires,
                )
            return SignedUrl(url=url, expires_in_seconds=expires, method=method.upper())
        except Exception as exc:
            logger.exception("r2_signed_url_failed", key=key)
            raise StorageError(f"Failed to generate signed URL: {type(exc).__name__}") from exc

    async def health_check(self) -> bool:
        try:
            async with self._client() as client:
                await client.list_buckets()
            return True
        except Exception:
            return False
