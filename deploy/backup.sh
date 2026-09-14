#!/usr/bin/env bash
# Nightly (and on-demand) backup of the production SQLite database.
# Uses SQLite's online backup so the copy is consistent while the app is running.
# Keeps 14 days under /data/backups. Run as the deploy user; cron line installed by
# `make deploy`. Exit non-zero on any failure so cron mails/logs it.
set -euo pipefail

DB=/data/abgfc.db
DIR=/data/backups
KEEP_DAYS=14
STAMP=$(date +%Y-%m-%d_%H%M%S)
OUT="$DIR/abgfc-$STAMP.db"

mkdir -p "$DIR"
test -f "$DB" || { echo "$(date -Is) no database at $DB" >&2; exit 1; }

sqlite3 "$DB" ".backup '$OUT'"
sqlite3 "$OUT" "PRAGMA integrity_check;" | grep -qx ok || { echo "$(date -Is) integrity check failed on $OUT" >&2; rm -f "$OUT"; exit 1; }
chmod 600 "$OUT"

find "$DIR" -name 'abgfc-*.db' -mtime +"$KEEP_DAYS" -delete
echo "$(date -Is) ok $OUT ($(du -h "$OUT" | cut -f1)) fixtures=$(sqlite3 "$OUT" 'select count(*) from fixtures')"
