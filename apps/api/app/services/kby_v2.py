"""KubanFy KBY v2 chunked encrypted audio container.

KBY v2 keeps the same per-content key derivation as KBY v1 but encrypts the
plaintext audio in independently authenticated chunks. This permits clients
to fetch and decrypt only the ranges they need for progressive playback and
encrypted offline caching.

Container:
    MAGIC(4) + VERSION(1) + HEADER_LEN(4, BE) + JSON_HEADER
    + repeated CHUNK records:
        PLAINTEXT_LEN(4, BE) + NONCE(12) + CIPHERTEXT(PLAINTEXT_LEN + 16)

Each chunk uses AES-256-GCM with AAD binding the container header, chunk index,
and plaintext length. The content hash remains the SHA-256 of the complete
plaintext audio, so v1/v2 assets identify the same recording.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import struct
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.services.kby import MAX_HEADER_SIZE, derive_key

MAGIC = b"KBY2"
VERSION = 2
NONCE_SIZE = 12
TAG_SIZE = 16
DEFAULT_CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True)
class KBY2Header:
    version: int
    content_hash: str
    plaintext_size: int
    quality: str
    content_type: str
    chunk_size: int
    chunk_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "content_hash": self.content_hash,
            "plaintext_size": self.plaintext_size,
            "quality": self.quality,
            "content_type": self.content_type,
            "chunk_size": self.chunk_size,
            "chunk_count": self.chunk_count,
            "algorithm": "AES-256-GCM-CHUNKED",
            "key_derivation": "KBY-V1-HMAC-SHA256",
        }


def _aad(header_bytes: bytes, index: int, plaintext_len: int) -> bytes:
    return (
        MAGIC
        + bytes([VERSION])
        + header_bytes
        + struct.pack(">II", index, plaintext_len)
    )


def pack(
    plaintext: bytes,
    *,
    content_hash: str,
    quality: str,
    content_type: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    settings=None,
) -> bytes:
    if not 16 * 1024 <= chunk_size <= 1024 * 1024:
        raise ValueError("chunk_size must be between 16 KiB and 1 MiB")

    actual_hash = hashlib.sha256(plaintext).hexdigest()
    if actual_hash != content_hash.lower():
        raise ValueError("content_hash does not match plaintext")

    chunk_count = (len(plaintext) + chunk_size - 1) // chunk_size
    header = KBY2Header(
        version=VERSION,
        content_hash=actual_hash,
        plaintext_size=len(plaintext),
        quality=quality,
        content_type=content_type,
        chunk_size=chunk_size,
        chunk_count=chunk_count,
    )
    header_bytes = json.dumps(
        header.as_dict(), separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    if len(header_bytes) > MAX_HEADER_SIZE:
        raise ValueError("KBY2 header too large")

    key = derive_key(actual_hash, settings=settings)
    out = bytearray()
    out.extend(MAGIC)
    out.append(VERSION)
    out.extend(struct.pack(">I", len(header_bytes)))
    out.extend(header_bytes)

    aes = AESGCM(key)
    for index in range(chunk_count):
        start = index * chunk_size
        chunk = plaintext[start : start + chunk_size]
        nonce = secrets.token_bytes(NONCE_SIZE)
        ciphertext = aes.encrypt(
            nonce,
            chunk,
            _aad(header_bytes, index, len(chunk)),
        )
        out.extend(struct.pack(">I", len(chunk)))
        out.extend(nonce)
        out.extend(ciphertext)

    return bytes(out)


def parse_header(container: bytes) -> tuple[KBY2Header, int]:
    if len(container) < 9 or container[:4] != MAGIC or container[4] != VERSION:
        raise ValueError("Invalid KBY2 header")
    header_len = struct.unpack(">I", container[5:9])[0]
    if header_len < 2 or header_len > MAX_HEADER_SIZE:
        raise ValueError("Invalid KBY2 header length")
    header_start = 9
    header_end = header_start + header_len
    if len(container) < header_end:
        raise ValueError("KBY2 header is truncated")
    try:
        raw = json.loads(container[header_start:header_end].decode("utf-8"))
        header = KBY2Header(
            version=int(raw["version"]),
            content_hash=str(raw["content_hash"]),
            plaintext_size=int(raw["plaintext_size"]),
            quality=str(raw["quality"]),
            content_type=str(raw["content_type"]),
            chunk_size=int(raw["chunk_size"]),
            chunk_count=int(raw["chunk_count"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid KBY2 header") from exc
    if header.version != VERSION or header.chunk_size < 16 * 1024:
        raise ValueError("Invalid KBY2 header values")
    return header, header_end


def unpack(
    container: bytes,
    *,
    key: bytes,
    expected_content_hash: str | None = None,
) -> tuple[KBY2Header, bytes]:
    header, offset = parse_header(container)
    if expected_content_hash and header.content_hash != expected_content_hash.lower():
        raise ValueError("KBY2 content hash mismatch")

    aes = AESGCM(key)
    plaintext = bytearray()
    header_bytes = container[9:offset]
    for index in range(header.chunk_count):
        if offset + 16 > len(container):
            raise ValueError("KBY2 chunk header is truncated")
        plaintext_len = struct.unpack(">I", container[offset : offset + 4])[0]
        nonce = container[offset + 4 : offset + 16]
        cipher_start = offset + 16
        cipher_end = cipher_start + plaintext_len + TAG_SIZE
        if cipher_end > len(container):
            raise ValueError("KBY2 chunk is truncated")
        chunk = aes.decrypt(
            nonce,
            container[cipher_start:cipher_end],
            _aad(header_bytes, index, plaintext_len),
        )
        if len(chunk) != plaintext_len:
            raise ValueError("KBY2 chunk length mismatch")
        plaintext.extend(chunk)
        offset = cipher_end

    if len(plaintext) != header.plaintext_size:
        raise ValueError("KBY2 plaintext size mismatch")
    if hashlib.sha256(plaintext).hexdigest() != header.content_hash:
        raise ValueError("KBY2 plaintext integrity check failed")
    return header, bytes(plaintext)


def key_base64(content_hash: str, *, settings=None) -> str:
    from app.services.kby import key_base64 as v1_key_base64
    return v1_key_base64(content_hash, settings=settings)
