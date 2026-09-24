"""Tests for FFprobe-based audio validation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.core.exceptions import ValidationError
from app.services.audio_validation import AudioValidationService


def _generate_test_wav(path: Path, duration_s: float = 1.0) -> None:
    """Generate a short silent WAV via ffmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration_s}",
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
def service() -> AudioValidationService:
    return AudioValidationService()


@pytest.mark.asyncio
async def test_probe_valid_wav(service: AudioValidationService, tmp_path: Path) -> None:
    wav = tmp_path / "test.wav"
    _generate_test_wav(wav, 1.5)
    result = await service.probe_file(wav)
    assert result.duration is not None
    assert 1.4 <= result.duration <= 1.7
    assert result.sample_rate == 44100
    assert result.channels == 2
    assert result.content_hash
    assert len(result.content_hash) == 64


@pytest.mark.asyncio
async def test_validate_for_storage(service: AudioValidationService, tmp_path: Path) -> None:
    wav = tmp_path / "ok.wav"
    _generate_test_wav(wav, 2.0)
    result = await service.validate_for_storage(wav)
    assert result.codec is not None
    assert result.duration is not None


@pytest.mark.asyncio
async def test_empty_file_rejected(service: AudioValidationService, tmp_path: Path) -> None:
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(ValidationError):
        await service.probe_file(empty)


@pytest.mark.asyncio
async def test_probe_bytes(service: AudioValidationService, tmp_path: Path) -> None:
    wav = tmp_path / "b.wav"
    _generate_test_wav(wav, 1.0)
    data = wav.read_bytes()
    result = await service.probe_bytes(data, suffix=".wav")
    assert result.duration is not None
    assert result.size == len(data)


@pytest.mark.asyncio
async def test_corrupt_rejected(service: AudioValidationService, tmp_path: Path) -> None:
    bad = tmp_path / "bad.mp3"
    bad.write_bytes(b"not-an-audio-file-at-all")
    with pytest.raises(ValidationError):
        await service.probe_file(bad)


def test_seed_demo_audio_is_valid_wav() -> None:
    """The staging bootstrap fixture must be a real playable WAV, not a URL stub."""
    import io
    import wave

    from scripts.seed import _demo_wav_bytes

    data = _demo_wav_bytes()
    with wave.open(io.BytesIO(data), "rb") as wav:
        assert wav.getnchannels() == 2
        assert wav.getframerate() == 44100
        assert wav.getsampwidth() == 2
        assert wav.getnframes() == 352800
        assert abs(wav.getnframes() / wav.getframerate() - 8.0) < 0.001
