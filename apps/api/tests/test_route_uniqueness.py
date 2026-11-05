"""Guard against duplicate FastAPI route registration.

Historical issue on feat/cloudflare-containers-deploy: two handlers for
POST /artist/{artist_id}/tracks/upload. The canonical branch must keep
(method, path) pairs unique.
"""

from __future__ import annotations

from collections import defaultdict

from app.main import create_app


def test_no_duplicate_http_routes() -> None:
    app = create_app()
    seen: dict[tuple[str, str], list[str]] = defaultdict(list)

    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        name = getattr(route, "name", "") or repr(route)
        for method in methods:
            if method == "HEAD":
                continue
            seen[(method.upper(), path)].append(name)

    duplicates = {
        key: names for key, names in seen.items() if len(names) > 1
    }
    assert not duplicates, (
        "Duplicate FastAPI routes (method, path): "
        + "; ".join(
            f"{method} {path} -> {names}"
            for (method, path), names in sorted(duplicates.items())
        )
    )
