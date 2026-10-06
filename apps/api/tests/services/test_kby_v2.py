from types import SimpleNamespace

from app.services.kby import pack as pack_v1, unpack as unpack_v1, derive_key
from app.services.kby_v2 import pack, parse_header, unpack


def test_kby_v2_round_trip_and_chunking():
    settings = SimpleNamespace(kby_master_key="test-kby-master-secret")
    plaintext = (b"KubanFy streaming test audio " * 12000) + b"!"
    content_hash = __import__("hashlib").sha256(plaintext).hexdigest()

    container = pack(
        plaintext,
        content_hash=content_hash,
        quality="low",
        content_type="audio/mp4",
        chunk_size=16 * 1024,
        settings=settings,
    )

    header, payload_offset = parse_header(container)
    assert header.version == 2
    assert header.chunk_size == 16 * 1024
    assert header.chunk_count > 1
    assert header.plaintext_size == len(plaintext)

    decoded_header, decoded = unpack(
        container,
        key=derive_key(content_hash, settings=settings),
        expected_content_hash=content_hash,
    )
    assert decoded_header == header
    assert decoded == plaintext


def test_kby_v1_remains_compatible_during_migration():
    settings = SimpleNamespace(kby_master_key="test-kby-master-secret")
    plaintext = b"legacy kubanfy audio" * 100
    content_hash = __import__("hashlib").sha256(plaintext).hexdigest()
    container = pack_v1(
        plaintext,
        content_hash=content_hash,
        quality="low",
        content_type="audio/mp4",
        settings=settings,
    )
    header, decoded = unpack_v1(
        container,
        key=derive_key(content_hash, settings=settings),
        expected_content_hash=content_hash,
    )
    assert header.version == 1
    assert decoded == plaintext
