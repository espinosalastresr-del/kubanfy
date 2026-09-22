"""Integration-ish unit tests for FFmpeg transcoding."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.models.music import AudioQuality
from app.services.transcoding import TranscodingService


def _sine_wav(path: Path, duration: float = 1.0) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def service() -> TranscodingService:
    return TranscodingService()


@pytest.mark.asyncio
async def test_transcode_low(service: TranscodingService, tmp_path: Path) -> None:
    src = tmp_path / "src.wav"
    _sine_wav(src, 1.2)
    out = await service.transcode_to_quality(src, AudioQuality.LOW, output_dir=tmp_path / "out")
    assert out.path.is_file()
    assert out.quality == AudioQuality.LOW
    assert out.probe.duration is not None
    assert out.probe.duration >= 1.0
    assert out.codec == "aac"


@pytest.mark.asyncio
async def test_transcode_medium(service: TranscodingService, tmp_path: Path) -> None:
    src = tmp_path / "src.wav"
    _sine_wav(src, 1.0)
    out = await service.transcode_to_quality(src, AudioQuality.MEDIUM, output_dir=tmp_path / "out")
    assert out.path.is_file()
    assert out.bitrate_kbps is not None


@pytest.mark.asyncio
async def test_generate_derivatives(service: TranscodingService, tmp_path: Path) -> None:
    src = tmp_path / "master.wav"
    _sine_wav(src, 1.0)
    results = await service.generate_derivatives(src, output_dir=tmp_path / "der")
    assert len(results) == 2
    qualities = {r.quality for r in results}
    assert AudioQuality.LOW in qualities
    assert AudioQuality.MEDIUM in qualities
