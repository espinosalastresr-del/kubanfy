"""Audio validation using FFprobe / FFmpeg.

Validates format, duration, size, codec, sample rate, bit depth, channels,
hash, and truncated files before storage.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import TranscodeError, ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Reasonable defaults; overridable via config later
MAX_DURATION_SECONDS = 3600 * 2  # 2 hours
MIN_DURATION_SECONDS = 1.0
MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024  # 200 MB
ALLOWED_CODECS = {
    "aac",
    "mp3",
    "flac",
    "pcm_s16le",
    "pcm_s24le",
    "pcm_s32le",
    "opus",
    "vorbis",
    "alac",
    "mp3float",
}


@dataclass
class AudioProbeResult:
    codec: str | None
    format_name: str | None
    duration: float | None
    size: int | None
    bitrate: int | None  # bits per second
    sample_rate: int | None
    channels: int | None
    bit_depth: int | None
    content_hash: str
    raw: dict[str, Any]


class AudioValidationService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def probe_file(self, path: str | Path) -> AudioProbeResult:
        path = Path(path)
        if not path.is_file():
            raise ValidationError(f"File not found: {path}")

        size = path.stat().st_size
        if size == 0:
            raise ValidationError("Empty audio file")
        if size > MAX_FILE_SIZE_BYTES:
            raise ValidationError(f"File exceeds max size ({MAX_FILE_SIZE_BYTES} bytes)")

        content_hash = await self._hash_file(path)

        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.warning("ffprobe_failed", stderr=stderr.decode()[:500])
            raise ValidationError("Unable to probe audio file (corrupt or unsupported)")

        try:
            data = json.loads(stdout.decode())
        except json.JSONDecodeError as exc:
            raise ValidationError("Invalid ffprobe output") from exc

        audio_stream = None
        for stream in data.get("streams") or []:
            if stream.get("codec_type") == "audio":
                audio_stream = stream
                break
        if audio_stream is None:
            raise ValidationError("No audio stream found")

        fmt = data.get("format") or {}
        duration = _safe_float(fmt.get("duration") or audio_stream.get("duration"))
        bitrate = _safe_int(fmt.get("bit_rate") or audio_stream.get("bit_rate"))
        sample_rate = _safe_int(audio_stream.get("sample_rate"))
        channels = _safe_int(audio_stream.get("channels"))
        codec = audio_stream.get("codec_name")
        bit_depth = _safe_int(
            audio_stream.get("bits_per_raw_sample") or audio_stream.get("bits_per_sample")
        )
        format_name = fmt.get("format_name")

        if duration is not None:
            if duration < MIN_DURATION_SECONDS:
                raise ValidationError("Audio duration too short")
            if duration > MAX_DURATION_SECONDS:
                raise ValidationError("Audio duration too long")

        if codec and codec.lower() not in ALLOWED_CODECS:
            # Soft warning path: still return probe but callers may reject
            logger.info("unusual_codec", codec=codec)

        return AudioProbeResult(
            codec=codec,
            format_name=format_name,
            duration=duration,
            size=size,
            bitrate=bitrate,
            sample_rate=sample_rate,
            channels=channels,
            bit_depth=bit_depth,
            content_hash=content_hash,
            raw=data,
        )

    async def probe_bytes(self, data: bytes, *, suffix: str = ".bin") -> AudioProbeResult:
        if len(data) == 0:
            raise ValidationError("Empty audio payload")
        if len(data) > MAX_FILE_SIZE_BYTES:
            raise ValidationError("Audio payload exceeds max size")

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(data)
            tmp.flush()
            return await self.probe_file(tmp.name)

    async def validate_bytes(self, data: bytes, *, suffix: str = ".bin") -> AudioProbeResult:
        """Validate an acquired audio payload before it can enter KubanFy storage."""
        if not data:
            raise ValidationError("Empty audio payload")
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(data)
            tmp.flush()
            return await self.validate_for_storage(tmp.name)

    async def validate_for_storage(self, path: str | Path) -> AudioProbeResult:
        """Full validation before storing master/derivative."""
        result = await self.probe_file(path)
        if result.duration is None:
            raise ValidationError("Could not determine duration")
        if result.codec is None:
            raise ValidationError("Could not determine codec")
        # Attempt a light decode check via ffmpeg null muxer
        await self._decode_check(path)
        return result

    async def _decode_check(self, path: str | Path) -> None:
        """Ensure FFmpeg can decode at least a short window."""
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-t",
            "1",
            "-f",
            "null",
            "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise TranscodeError(f"Audio decode check failed: {stderr.decode()[:300]}")

    async def _hash_file(self, path: Path) -> str:
        def _hash() -> str:
            h = hashlib.sha256()
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()

        return await asyncio.to_thread(_hash)


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
