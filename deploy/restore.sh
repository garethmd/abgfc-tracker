#!/usr/bin/env bash
# Restore a backup over the production database. Usage: restore.sh <backup.db>
# Keeps the database it replaced as /data/backups/pre-restore-<stamp>.db.
set -euo pipefail
SRC=${1:?usage: restore.sh <backup.db>}
DB=/data/abgfc.db
COMPOSE="docker compose -f /opt/abgfc/docker-compose.prod.yml"

sqlite3 "$SRC" "PRAGMA integrity_check;" | grep -qx ok || { echo "refusing: $SRC fails integrity check" >&2; exit 1; }
$COMPOSE stop backend >/dev/null
cp "$DB" "/data/backups/pre-restore-$(date +%Y-%m-%d_%H%M%S).db"
rm -f "$DB-wal" "$DB-shm"
cp "$SRC" "$DB"
chmod 600 "$DB"
$COMPOSE start backend >/dev/null
for _ in $(seq 1 30); do
  $COMPOSE exec -T backend python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')" 2>/dev/null && { echo "restored $SRC; api healthy"; exit 0; }
  sleep 2
done
echo "api did not come back healthy" >&2; exit 1
