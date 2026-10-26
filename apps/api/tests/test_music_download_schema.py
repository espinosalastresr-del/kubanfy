"""Schema validation for browser-compatible protected downloads."""

import pytest
from pydantic import ValidationError

from app.schemas.music import MusicDownloadRequest


def test_download_request_defaults_to_legacy_kby_for_existing_clients():
    request = MusicDownloadRequest(track_id="12345678-1234-5678-1234-567812345678")
    assert request.kby_version == 1


def test_download_request_accepts_kby2_for_web_offline_storage():
    request = MusicDownloadRequest(
        track_id="12345678-1234-5678-1234-567812345678",
        quality="low",
        kby_version=2,
    )
    assert request.kby_version == 2


@pytest.mark.parametrize("version", [0, 3, -1])
def test_download_request_rejects_unsupported_kby_versions(version):
    with pytest.raises(ValidationError):
        MusicDownloadRequest(
            track_id="12345678-1234-5678-1234-567812345678",
            kby_version=version,
        )
