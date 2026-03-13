#!/bin/bash
set -e

DB="/home/dan/jukebox.db"
MUSIC_ROOT="/mnt/lossless"

if [ ! -f "$DB" ]; then
  echo "Database not found: $DB"
  exit 1
fi

if [ ! -d "$MUSIC_ROOT" ]; then
  echo "Music root not found: $MUSIC_ROOT"
  exit 1
fi

BACKUP="/home/dan/shuffle-player/jukebox.db.backup.$(date +%Y%m%d_%H%M%S)"
cp "$DB" "$BACKUP"

python3 - <<'PY'
import os
import sqlite3

db = "/home/dan/jukebox.db"
music_root = "/mnt/lossless"

con = sqlite3.connect(db)
cur = con.cursor()

rows = cur.execute("SELECT path FROM tracks").fetchall()
missing = [p for (p,) in rows if p and not os.path.exists(p)]

removed = 0
if missing:
    cur.executemany("DELETE FROM tracks WHERE path = ?", [(p,) for p in missing])
    removed = len(missing)

added = 0
updated = 0

# Try to detect likely columns without assuming too much.
cols = [r[1] for r in cur.execute("PRAGMA table_info(tracks)").fetchall()]
has_path = "path" in cols
has_title = "title" in cols
has_artist = "artist" in cols
has_album = "album" in cols

existing_paths = set()
if has_path:
    existing_paths = {p for (p,) in cur.execute("SELECT path FROM tracks").fetchall() if p}

audio_exts = {".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wav", ".aac", ".wma", ".aiff", ".alac"}

def guess_tags_from_path(path):
    rel = os.path.relpath(path, music_root)
    parts = rel.split(os.sep)
    artist = parts[0] if len(parts) >= 2 else ""
    album = parts[1] if len(parts) >= 3 else ""
    title = os.path.splitext(os.path.basename(path))[0]
    return artist, album, title

if has_path:
    for root, _, files in os.walk(music_root):
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in audio_exts:
                continue

            full_path = os.path.join(root, name)

            if full_path in existing_paths:
                continue

            artist, album, title = guess_tags_from_path(full_path)

            insert_cols = []
            insert_vals = []

            if has_path:
                insert_cols.append("path")
                insert_vals.append(full_path)
            if has_title:
                insert_cols.append("title")
                insert_vals.append(title)
            if has_artist:
                insert_cols.append("artist")
                insert_vals.append(artist)
            if has_album:
                insert_cols.append("album")
                insert_vals.append(album)

            if insert_cols:
                sql = f"INSERT INTO tracks ({', '.join(insert_cols)}) VALUES ({', '.join(['?']*len(insert_vals))})"
                cur.execute(sql, insert_vals)
                added += 1

con.commit()
total = cur.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
con.close()

print(f"Backup created")
print(f"Added: {added}")
print(f"Updated: {updated}")
print(f"Removed missing: {removed}")
print(f"Final total: {total}")
PY