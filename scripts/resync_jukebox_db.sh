#!/usr/bin/env bash
set -euo pipefail

DB="${JUKEBOX_DB_PATH:-/home/dan/jukebox.db}"
MUSIC_ROOT="${JUKEBOX_MUSIC_ROOT:-/mnt/lossless}"
PROJECT_DIR="/home/dan/shuffle-player"
INDEXER="$PROJECT_DIR/scripts/update_index_sqlite.py"
BACKUP_DIR="/home/dan/jukebox-backups"
LOCK_FILE="/tmp/shuffle-library-scan.lock"

if [[ ! -f "$DB" ]]; then
  echo "Library scan stopped: database not found: $DB" >&2
  exit 1
fi

if [[ ! -d "$MUSIC_ROOT" ]]; then
  echo "Library scan stopped: music root not found: $MUSIC_ROOT" >&2
  exit 1
fi

if [[ ! -f "$INDEXER" ]]; then
  echo "Library scan stopped: indexer not found: $INDEXER" >&2
  exit 1
fi

if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  PYTHON="$PROJECT_DIR/.venv/bin/python"
else
  PYTHON="/usr/bin/python3"
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Library scan already running. Please wait for it to finish." >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
BACKUP="$BACKUP_DIR/jukebox.db.$(date +%Y%m%d_%H%M%S).backup"
cp --preserve=mode,timestamps "$DB" "$BACKUP"

echo "Library scan started"
echo "Database backup: $BACKUP"
echo "Music root: $MUSIC_ROOT"
echo

JUKEBOX_DB_PATH="$DB" JUKEBOX_MUSIC_ROOT="$MUSIC_ROOT" \
  "$PYTHON" "$INDEXER" --prune
