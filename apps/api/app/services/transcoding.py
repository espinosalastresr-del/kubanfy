"""Audio transcoding with FFmpeg.

Master is stored once; derivatives: LOW, MEDIUM, LOSSLESS.
Subscription determines authorization, not asset identity.
"""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.exceptions import TranscodeError, ValidationError
from app.core.logging import get_logger
from app.models.music import AudioQuality
from app.services.audio_validation import AudioProbeResult, AudioValidationService

logger = get_logger(__name__)


@dataclass
class TranscodeOutput:
    quality: AudioQuality
    path: Path
    probe: AudioProbeResult
    codec: str
    bitrate_kbps: int | None


class TranscodingService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.validator = AudioValidationService(self.settings)

    async def transcode_to_quality(
        self,
        input_path: str | Path,
        quality: AudioQuality,
        *,
        output_dir: str | Path | None = None,
    ) -> TranscodeOutput:
        """Transcode input master to a target logical quality."""
        input_path = Path(input_path)
        if not input_path.is_file():
            raise ValidationError(f"Input not found: {input_path}")

        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="kubanfy-tx-"))
        out_dir.mkdir(parents=True, exist_ok=True)

        if quality == AudioQuality.LOSSLESS:
            # Re-wrap / ensure FLAC; if already lossless, still normalize to flac
            out_path = out_dir / f"{input_path.stem}.flac"
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-vn",
                "-c:a",
                "flac",
                "-compression_level",
                "5",
                str(out_path),
            ]
            codec = "flac"
            bitrate_kbps = None
        elif quality == AudioQuality.LOW:
            out_path = out_dir / f"{input_path.stem}_low.m4a"
            kbps = self.settings.audio_low_bitrate_kbps
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-vn",
                "-c:a",
                "aac",
                "-b:a",
                f"{kbps}k",
                "-ar",
                "44100",
                "-ac",
                "2",
                str(out_path),
            ]
            codec = "aac"
            bitrate_kbps = kbps
        else:  # MEDIUM
            out_path = out_dir / f"{input_path.stem}_medium.m4a"
            kbps = self.settings.audio_medium_bitrate_kbps
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-vn",
                "-c:a",
                "aac",
                "-b:a",
                f"{kbps}k",
                "-ar",
                "44100",
                "-ac",
                "2",
                str(out_path),
            ]
            codec = "aac"
            bitrate_kbps = kbps

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0 or not out_path.is_file():
            logger.error("transcode_failed", quality=quality.value, stderr=stderr.decode()[:800])
            raise TranscodeError(f"Transcode to {quality.value} failed")

        probe = await self.validator.validate_for_storage(out_path)
        logger.info(
            "transcode_ok",
            quality=quality.value,
            codec=probe.codec,
            duration=probe.duration,
            size=probe.size,
        )
        return TranscodeOutput(
            quality=quality,
            path=out_path,
            probe=probe,
            codec=codec,
            bitrate_kbps=bitrate_kbps,
        )

    async def generate_derivatives(
        self,
        master_path: str | Path,
        *,
        qualities: list[AudioQuality] | None = None,
        output_dir: str | Path | None = None,
    ) -> list[TranscodeOutput]:
        """Generate LOW + MEDIUM (+ optional LOSSLESS) from a validated master."""
        qualities = qualities or [AudioQuality.LOW, AudioQuality.MEDIUM]
        results: list[TranscodeOutput] = []
        for q in qualities:
            results.append(await self.transcode_to_quality(master_path, q, output_dir=output_dir))
        return results
