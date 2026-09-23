"""HTTP Range parsing tests (plan §20)."""

from app.services.http_range import parse_bytes_range


def test_full_range():
    r = parse_bytes_range("bytes=0-99", 1000)
    assert r is not None
    assert r.start == 0 and r.end == 99 and r.length == 100


def test_open_end():
    r = parse_bytes_range("bytes=100-", 500)
    assert r is not None
    assert r.start == 100 and r.end == 499


def test_suffix():
    r = parse_bytes_range("bytes=-50", 200)
    assert r is not None
    assert r.start == 150 and r.end == 199


def test_invalid():
    assert parse_bytes_range(None, 100) is None
    assert parse_bytes_range("bytes=500-600", 100) is None
    assert parse_bytes_range("bytes=abc", 100) is None


def test_content_range_header():
    r = parse_bytes_range("bytes=0-9", 100)
    assert r is not None
    assert r.content_range_header() == "bytes 0-9/100"
