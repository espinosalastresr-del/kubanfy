#!/bin/sh
set -eu

echo "[kubanfy] waiting for database..."
python - <<'PY'
import asyncio, os, sys
async def wait():
    import asyncpg
    url = os.environ.get("DATABASE_URL", "")
    # asyncpg wants postgresql:// not postgresql+asyncpg://
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    for i in range(60):
        try:
            conn = await asyncpg.connect(url)
            await conn.close()
            print("[kubanfy] database ready")
            return
        except Exception as e:
            print(f"[kubanfy] db wait {i+1}/60: {e}")
            await asyncio.sleep(2)
    sys.exit(1)
asyncio.run(wait())
PY

echo "[kubanfy] alembic upgrade head..."
alembic upgrade head

echo "[kubanfy] starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
