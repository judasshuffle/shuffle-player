#!/usr/bin/env python3
import os
import sys
import time
import sqlite3
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from config import MUSIC_ROOT, DB_PATH
AUDIO_EXTS = {".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".aiff", ".alac"}

def is_playlists_path(p: str) -> bool:
    s = p.replace("\\", "/")
    return "/Playlists/" in s or s.endswith("/Playlists") or s.startswith(f"{MUSIC_ROOT}/Playlists/")

def main():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    now = int(time.time())

    scanned = updated = skipped = 0

    for root, dirs, files in os.walk(MUSIC_ROOT):
        dirs[:] = [d for d in dirs if d != "Playlists"]
        if is_playlists_path(root):
            continue

        for fn in files:
            ext = Path(fn).suffix.lower()
            if ext not in AUDIO_EXTS:
                continue
            path = os.path.join(root, fn)
            if is_playlists_path(path):
                continue

            try:
                st = os.stat(path)
            except FileNotFoundError:
                continue
            except OSError:
                # e.g. transient NAS issue
                continue

            scanned += 1
            mtime = int(st.st_mtime)
            size  = int(st.st_size)

            row = con.execute("SELECT mtime, size FROM tracks WHERE path=?", (path,)).fetchone()
            if row and int(row[0]) == mtime and int(row[1]) == size and int(row[0]) != 0:
                skipped += 1
                continue

            con.execute("""
              INSERT INTO tracks(path, mtime, size, ext, added_at, updated_at)
              VALUES(?,?,?,?,?,?)
              ON CONFLICT(path) DO UPDATE SET
                mtime=excluded.mtime,
                size=excluded.size,
                ext=excluded.ext,
                updated_at=excluded.updated_at
            """, (path, mtime, size, ext, now, now))
            updated += 1

            if scanned % 2000 == 0:
                con.commit()
                print(f"Progress: scanned={scanned} updated={updated} skipped={skipped}", flush=True)

    con.commit()
    con.close()
    print(f"Done: scanned={scanned} updated={updated} skipped={skipped}")

if __name__ == "__main__":
    main()
