"""KubanFy .kby protected audio container.

The container keeps audio objects in KubanFy's storage encrypted at rest.
The plaintext codec/container remains the payload so the iOS client can
decrypt it only after API authorization.

Format v1:
    MAGIC(4) + VERSION(1) + HEADER_LEN(4, big-endian) + NONCE(12)
    + JSON_HEADER + AES-256-GCM-CIPHERTEXT

The AES key is derived per content hash from a server-only KBY master secret.
The plaintext content hash is retained in the header and verified after
decryption.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import struct
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings, get_settings

MAGIC = b"KBY1"
VERSION = 1
NONCE_SIZE = 12
MAX_HEADER_SIZE = 16 * 1024


@dataclass(frozen=True)
class KBYHeader:
    version: int
    content_hash: str
    plaintext_size: int
    quality: str
    content_type: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "content_hash": self.content_hash,
            "plaintext_size": self.plaintext_size,
            "quality": self.quality,
            "content_type": self.content_type,
            "algorithm": "AES-256-GCM",
        }


def _master_key(settings: Settings | None = None) -> bytes:
    settings = settings or get_settings()
    value = settings.kby_master_key
    if not value:
        raise ValueError("KBY_MASTER_KEY is required")
    return hashlib.sha256(value.encode("utf-8")).digest()


def derive_key(content_hash: str, *, settings: Settings | None = None) -> bytes:
    if len(content_hash) != 64 or any(c not in "0123456789abcdefABCDEF" for c in content_hash):
        raise ValueError("content_hash must be a SHA-256 hex digest")
    return hmac.new(
        _master_key(settings),
        b"kubanfy-kby-v1:" + content_hash.lower().encode("ascii"),
        hashlib.sha256,
    ).digest()


def key_base64(content_hash: str, *, settings: Settings | None = None) -> str:
    return base64.b64encode(derive_key(content_hash, settings=settings)).decode("ascii")


def pack(
    plaintext: bytes,
    *,
    content_hash: str,
    quality: str,
    content_type: str,
    settings: Settings | None = None,
) -> bytes:
    actual_hash = hashlib.sha256(plaintext).hexdigest()
    if actual_hash != content_hash.lower():
        raise ValueError("content_hash does not match plaintext")

    header = KBYHeader(
        version=VERSION,
        content_hash=actual_hash,
        plaintext_size=len(plaintext),
        quality=quality,
        content_type=content_type,
    )
    header_bytes = json.dumps(
        header.as_dict(), separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    if len(header_bytes) > MAX_HEADER_SIZE:
        raise ValueError("KBY header too large")

    nonce = __import__("secrets").token_bytes(NONCE_SIZE)
    prefix = MAGIC + bytes([VERSION]) + struct.pack(">I", len(header_bytes)) + nonce
    ciphertext = AESGCM(derive_key(actual_hash, settings=settings)).encrypt(
        nonce,
        plaintext,
        prefix + header_bytes,
    )
    return prefix + header_bytes + ciphertext


def unpack(
    container: bytes,
    *,
    key: bytes,
    expected_content_hash: str | None = None,
) -> tuple[KBYHeader, bytes]:
    if len(container) < len(MAGIC) + 1 + 4 + NONCE_SIZE + 16:
        raise ValueError("KBY container is truncated")
    if container[:4] != MAGIC:
        raise ValueError("Invalid KBY magic")
    version = container[4]
    if version != VERSION:
        raise ValueError("Unsupported KBY version")
    header_len = struct.unpack(">I", container[5:9])[0]
    if header_len < 2 or header_len > MAX_HEADER_SIZE:
        raise ValueError("Invalid KBY header length")
    nonce = container[9:21]
    header_start = 21
    header_end = header_start + header_len
    if len(container) <= header_end:
        raise ValueError("KBY container is truncated")
    try:
        raw = json.loads(container[header_start:header_end].decode("utf-8"))
        header = KBYHeader(
            version=int(raw["version"]),
            content_hash=str(raw["content_hash"]),
            plaintext_size=int(raw["plaintext_size"]),
            quality=str(raw["quality"]),
            content_type=str(raw["content_type"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid KBY header") from exc
    if header.version != VERSION:
        raise ValueError("Unsupported KBY header version")
    if expected_content_hash and header.content_hash != expected_content_hash.lower():
        raise ValueError("KBY content hash mismatch")
    prefix = container[:21]
    ciphertext = container[header_end:]
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, prefix + container[header_start:header_end])
    except Exception as exc:
        raise ValueError("KBY authentication failed") from exc
    if len(plaintext) != header.plaintext_size:
        raise ValueError("KBY plaintext size mismatch")
    if hashlib.sha256(plaintext).hexdigest() != header.content_hash:
        raise ValueError("KBY plaintext integrity check failed")
    return header, plaintext
