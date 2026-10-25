from app.services.offline_license import is_protected_offline_asset_key


def test_offline_license_only_accepts_protected_kby_assets() -> None:
    assert is_protected_offline_asset_key("audio/track-v3.kby")
    assert not is_protected_offline_asset_key(None)
    assert not is_protected_offline_asset_key("")
    assert not is_protected_offline_asset_key("audio/track.mp3")
    assert not is_protected_offline_asset_key("audio/track.kby2")
