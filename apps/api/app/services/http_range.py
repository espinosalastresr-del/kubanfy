"""HTTP Range request parsing (plan §20 download/resume)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int  # inclusive
    total: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    def content_range_header(self) -> str:
        return f"bytes {self.start}-{self.end}/{self.total}"


def parse_bytes_range(header: str | None, total_size: int) -> ByteRange | None:
    """Parse a single Range: bytes=START-END header.

    Returns None if header missing or unsatisfiable (caller may send 416).
    Only supports a single contiguous range.
    """
    if not header or total_size <= 0:
        return None
    header = header.strip()
    if not header.lower().startswith("bytes="):
        return None
    spec = header[6:].strip()
    if "," in spec:
        # multi-range not supported — treat as full body
        return None
    if "-" not in spec:
        return None
    start_s, end_s = spec.split("-", 1)
    try:
        if start_s == "":
            # suffix: last N bytes
            suffix = int(end_s)
            if suffix <= 0:
                return None
            start = max(0, total_size - suffix)
            end = total_size - 1
        elif end_s == "":
            start = int(start_s)
            end = total_size - 1
        else:
            start = int(start_s)
            end = int(end_s)
    except ValueError:
        return None

    if start < 0 or end < start or start >= total_size:
        return None
    end = min(end, total_size - 1)
    return ByteRange(start=start, end=end, total=total_size)
