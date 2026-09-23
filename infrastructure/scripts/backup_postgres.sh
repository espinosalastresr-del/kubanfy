#!/usr/bin/env bash
# PostgreSQL logical backup for staging/production (plan §42).
# Usage:
#   DATABASE_URL=postgresql://user:pass@host:5432/kubanfy ./infrastructure/scripts/backup_postgres.sh
#   OUT_DIR=/var/backups/kubanfy ./infrastructure/scripts/backup_postgres.sh

set -euo pipefail

OUT_DIR="${OUT_DIR:-./backups}"
mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="${OUT_DIR}/kubanfy_${STAMP}.sql.gz"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required (postgresql://...)" >&2
  exit 1
fi

# Strip SQLAlchemy driver prefix if present
URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql:\/\/}"
URL="${URL/postgresql+psycopg:\/\//postgresql:\/\/}"

echo "[backup] writing $FILE"
pg_dump "$URL" --no-owner --no-acl | gzip -c > "$FILE"
echo "[backup] done ($(du -h "$FILE" | cut -f1))"

# Keep last 14 files by default
KEEP="${BACKUP_KEEP:-14}"
ls -1t "$OUT_DIR"/kubanfy_*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "[backup] retention keep=$KEEP"
