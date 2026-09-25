"""Development seed data — never use real production data.

Usage:
    cd apps/api && PYTHONPATH=. python -m scripts.seed
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import math
import struct
import sys
import wave
from pathlib import Path

# Allow running as module from apps/api
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import close_db, init_db
import app.core.database as database
from app.core.logging import setup_logging
from app.core.security import hash_password
from app.models.artist_member import ArtistMember, ArtistMemberRole
from app.models.music import AudioAsset, AudioQuality, Artist, QualityConfidence, Release, ReleaseType, SourceType, Track, TrackArtist, TrackStatus
from app.models.rights import LicenseRecord, LicenseStatus
from app.models.rbac import SystemRole
from app.models.user import User, UserStatus
from app.services.admin import AdminService
from app.services.audio_validation import AudioValidationService
from app.services.entitlement import EntitlementService
from app.services.kby import pack
from app.services.rbac import RbacService
from app.storage import StorageBucket, get_storage


def _demo_wav_bytes(*, duration_seconds: float = 8.0, sample_rate: int = 44100) -> bytes:
    """Create a tiny deterministic PCM WAV used only for staging/dev playback tests."""
    frames = int(duration_seconds * sample_rate)
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for i in range(frames):
            t = i / sample_rate
            freq = 440.0 if t < duration_seconds / 2 else 660.0
            sample = int(0.18 * 32767 * math.sin(2 * math.pi * freq * t))
            wav.writeframes(struct.pack("<hh", sample, sample))
    return out.getvalue()


async def _ensure_demo_playable_track(session) -> None:
    """Create a fully playable staging fixture through the real storage contract."""
    artist = await session.scalar(select(Artist).where(Artist.slug == "kubanfy-demo"))
    if artist is None:
        artist = Artist(
            name="KubanFy Demo",
            slug="kubanfy-demo",
            bio="Contenido técnico de demostración — no es una grabación comercial",
            country="CU",
            status="active",
            verified=True,
        )
        session.add(artist)
        await session.flush()

    track = await session.scalar(select(Track).where(Track.slug == "kubanfy-connectivity-test"))
    if track is None:
        track = Track(
            title="KubanFy Connectivity Test",
            slug="kubanfy-connectivity-test",
            duration=8.0,
            status=TrackStatus.PROCESSING,
            language="zxx",
        )
        session.add(track)
        await session.flush()
        session.add(TrackArtist(track_id=track.id, artist_id=artist.id, role="main", display_order=0))
        await session.flush()

    audio = _demo_wav_bytes()
    probe = await AudioValidationService(get_settings()).validate_bytes(audio, suffix=".wav")
    storage = get_storage()

    for quality in (AudioQuality.LOW, AudioQuality.MEDIUM, AudioQuality.LOSSLESS):
        source_type = (
            SourceType.ARTIST_UPLOAD
            if quality == AudioQuality.LOSSLESS
            else SourceType.DERIVATIVE
        )
        key = f"artists/{artist.id}/demo/connectivity-test/{quality.value}/{probe.content_hash}.kby"
        if not await storage.exists(key, bucket=StorageBucket.PERMANENT):
            kby = pack(
                audio,
                content_hash=probe.content_hash,
                quality=quality.value,
                content_type="audio/wav",
                settings=get_settings(),
            )
            await storage.put(
                key,
                kby,
                bucket=StorageBucket.PERMANENT,
                content_type="application/vnd.kubanfy.kby",
            )
        asset = await session.scalar(
            select(AudioAsset).where(
                AudioAsset.track_id == track.id,
                AudioAsset.quality == quality,
                AudioAsset.is_active.is_(True),
            )
        )
        if asset is None:
            asset = AudioAsset(track_id=track.id, quality=quality)
            session.add(asset)

        asset.storage_key = key
        asset.codec = probe.codec
        asset.bitrate = (probe.bitrate // 1000) if probe.bitrate else None
        asset.bit_depth = probe.bit_depth
        asset.sample_rate = probe.sample_rate
        asset.channels = probe.channels
        asset.duration = probe.duration
        asset.size = probe.size
        asset.quality = quality
        asset.source_type = source_type
        asset.content_hash = probe.content_hash
        asset.quality_confidence = QualityConfidence.VERIFIED
        asset.version = 1
        asset.is_active = True
    await session.flush()
    track.status = TrackStatus.PUBLISHED
    await session.flush()
    print(f"Ensured playable demo track: {track.id}")


async def seed() -> None:
    settings = get_settings()
    setup_logging(settings)
    init_db(settings)

    if database.async_session_factory is None:
        raise RuntimeError("DB not initialized")

    async with database.async_session_factory() as session:
        rbac = RbacService(session)
        await rbac.ensure_default_rbac()

        admin_svc = AdminService(session)
        await admin_svc.ensure_default_flags()

        ent = EntitlementService(session)
        await ent.ensure_default_plans()

        admin_email = settings.super_admin_email.lower()
        admin = await session.scalar(select(User).where(User.email == admin_email))
        if admin is None:
            admin = User(
                email=admin_email,
                password_hash=hash_password(settings.super_admin_password),
                display_name="Super Admin",
                country="CU",
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(admin)
            await session.flush()
            await rbac.assign_role(admin.id, SystemRole.SUPER_ADMIN.value)
            print(f"Created super admin: {admin_email}")
        else:
            print(f"Super admin exists: {admin_email}")

        demo = await session.scalar(select(User).where(User.email == "demo@kubanfy.local"))
        if demo is None:
            demo = User(
                email="demo@kubanfy.local",
                password_hash=hash_password("DemoPass123!"),
                display_name="Demo User",
                country="CU",
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(demo)
            await session.flush()
            print("Created demo user: demo@kubanfy.local / DemoPass123!")

        artist = await session.scalar(select(Artist).where(Artist.slug == "buena-vista-demo"))
        if artist is None:
            artist = Artist(
                name="Buena Vista Demo",
                slug="buena-vista-demo",
                bio="Artista de demostración — datos ficticios",
                country="CU",
                status="active",
                verified=True,
            )
            session.add(artist)
            await session.flush()
            if demo:
                session.add(
                    ArtistMember(
                        artist_id=artist.id,
                        user_id=demo.id,
                        role=ArtistMemberRole.OWNER,
                    )
                )

        track = await session.scalar(select(Track).where(Track.slug == "guantanamera-demo"))
        if track is None:
            release = Release(
                artist_id=artist.id,
                title="Guantanamera Demo",
                type=ReleaseType.SINGLE,
                status=TrackStatus.DRAFT,
            )
            session.add(release)
            await session.flush()
            track = Track(
                title="Guantanamera (Demo)",
                slug="guantanamera-demo",
                duration=8.0,
                release_id=release.id,
                album_id=release.id,
                status=TrackStatus.PROCESSING,
                language="es",
            )
            session.add(track)
            await session.flush()
            session.add(
                TrackArtist(track_id=track.id, artist_id=artist.id, role="main", display_order=0)
            )
            if demo:
                session.add(
                    LicenseRecord(
                        track_id=track.id,
                        release_id=release.id,
                        artist_id=artist.id,
                        accepted_by_user_id=demo.id,
                        storage_allowed=True,
                        processing_allowed=True,
                        transcoding_allowed=True,
                        streaming_allowed=True,
                        artwork_allowed=True,
                        metadata_allowed=True,
                        license_version="1.0",
                        status=LicenseStatus.ACTIVE,
                    )
                )
            await session.flush()
            print("Created demo artist + track")
        else:
            release = await session.get(Release, track.release_id) if track.release_id else None

        if demo is not None and release is not None:
            existing_license = await session.scalar(
                select(LicenseRecord).where(
                    LicenseRecord.track_id == track.id,
                    LicenseRecord.artist_id == artist.id,
                )
            )
            if existing_license is None:
                session.add(
                    LicenseRecord(
                        track_id=track.id,
                        release_id=release.id,
                        artist_id=artist.id,
                        accepted_by_user_id=demo.id,
                        storage_allowed=True,
                        processing_allowed=True,
                        transcoding_allowed=True,
                        streaming_allowed=True,
                        artwork_allowed=True,
                        metadata_allowed=True,
                        license_version="1.0",
                        status=LicenseStatus.ACTIVE,
                    )
                )
                await session.flush()

        # Never seed a published track without the same validated/KBY/AudioAsset
        # chain required by the production playback path.
        # Reconcile the complete playable chain on every staging seed run.
        # This also repairs legacy fixtures that were published before AudioAsset
        # creation became mandatory.
        if track is not None:
            audio = _demo_wav_bytes()
            probe = await AudioValidationService(get_settings()).validate_bytes(audio, suffix=".wav")
            storage = get_storage()
            for quality in (AudioQuality.LOW, AudioQuality.MEDIUM, AudioQuality.LOSSLESS):
                source_type = (
                    SourceType.ARTIST_UPLOAD
                    if quality == AudioQuality.LOSSLESS
                    else SourceType.DERIVATIVE
                )
                key = f"artists/{artist.id}/tracks/{track.id}/demo/{quality.value}/{probe.content_hash}.kby"
                if not await storage.exists(key, bucket=StorageBucket.PERMANENT):
                    kby = pack(
                        audio,
                        content_hash=probe.content_hash,
                        quality=quality.value,
                        content_type="audio/wav",
                        settings=get_settings(),
                    )
                    await storage.put(
                        key,
                        kby,
                        bucket=StorageBucket.PERMANENT,
                        content_type="application/vnd.kubanfy.kby",
                    )
                asset = await session.scalar(
                    select(AudioAsset).where(
                        AudioAsset.track_id == track.id,
                        AudioAsset.quality == quality,
                        AudioAsset.is_active.is_(True),
                    )
                )
                if asset is None:
                    asset = AudioAsset(track_id=track.id, quality=quality)
                    session.add(asset)

                asset.storage_key = key
                asset.codec = probe.codec
                asset.bitrate = (probe.bitrate // 1000) if probe.bitrate else None
                asset.bit_depth = probe.bit_depth
                asset.sample_rate = probe.sample_rate
                asset.channels = probe.channels
                asset.duration = probe.duration
                asset.size = probe.size
                asset.quality = quality
                asset.source_type = source_type
                asset.content_hash = probe.content_hash
                asset.quality_confidence = QualityConfidence.VERIFIED
                asset.version = 1
                asset.is_active = True
            await session.flush()
            release = await session.get(Release, track.release_id) if track.release_id else None
            license_rec = await session.scalar(
                select(LicenseRecord).where(
                    LicenseRecord.track_id == track.id,
                    LicenseRecord.artist_id == artist.id,
                    LicenseRecord.status == LicenseStatus.ACTIVE,
                )
            )
            assets = list((await session.scalars(
                select(AudioAsset).where(
                    AudioAsset.track_id == track.id,
                    AudioAsset.is_active.is_(True),
                )
            )).all())
            qualities = {a.quality for a in assets}
            has_master = any(a.source_type == SourceType.ARTIST_UPLOAD for a in assets)
            if license_rec and has_master and {AudioQuality.LOW, AudioQuality.MEDIUM}.issubset(qualities):
                track.status = TrackStatus.PUBLISHED
                if release:
                    release.status = TrackStatus.PUBLISHED
                await session.flush()

        # The connectivity fixture is created through the same validation + KBY
        # storage contract used by first-party audio before it is published.
        await _ensure_demo_playable_track(session)

        await session.commit()
        print("Seed complete.")

    await close_db()


if __name__ == "__main__":
    asyncio.run(seed())
