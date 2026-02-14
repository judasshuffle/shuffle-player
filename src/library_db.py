import os
import sqlite3
import tempfile
import random
from typing import List, Tuple, Optional

DB_PATH = "/home/dan/jukebox.db"
TARGET_SECONDS_DEFAULT = 60 * 60  # ~1 hour

def db_connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con

def fetch_tracks_for_artist(con: sqlite3.Connection, artist: str, limit: int = 8000):
    cur = con.execute("""
      SELECT path, artist, year, duration
      FROM tracks
      WHERE artist IS NOT NULL
        AND lower(artist) = lower(?)
        AND duration IS NOT NULL
        AND duration > 30
        AND path NOT LIKE '%/Playlists/%'
        AND path NOT LIKE '/mnt/lossless/Playlists/%'
      ORDER BY year IS NULL, year, RANDOM()
      LIMIT ?
    """, (artist, limit))
    return list(cur.fetchall())

def build_target_playlist(rows, target_seconds: int = TARGET_SECONDS_DEFAULT) -> Tuple[List[str], float]:
    pool = list(rows)
    random.shuffle(pool)

    playlist: List[str] = []
    total = 0.0

    for r in pool:
        d = float(r["duration"] or 0.0)
        if d <= 0:
            continue

        if total >= target_seconds:
            break

        if total >= target_seconds * 0.85 and (total + d) > target_seconds * 1.10:
            break

        playlist.append(r["path"])
        total += d

    return playlist, total

def write_m3u(paths: List[str]) -> Optional[str]:
    if not paths:
        return None
    fd, m3u_path = tempfile.mkstemp(prefix="jukebox_", suffix=".m3u", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(p + "\n")
    return m3u_path

def fetch_tracks_for_artist_year_range(con: sqlite3.Connection, artist: str, y1: int, y2: int, limit: int = 8000):
    cur = con.execute("""
      SELECT path, artist, year, duration
      FROM tracks
      WHERE artist IS NOT NULL
        AND lower(artist) = lower(?)
        AND year IS NOT NULL
        AND year BETWEEN ? AND ?
        AND duration IS NOT NULL
        AND duration > 30
        AND path NOT LIKE '%/Playlists/%'
        AND path NOT LIKE '/mnt/lossless/Playlists/%'
      ORDER BY year, RANDOM()
      LIMIT ?
    """, (artist, int(y1), int(y2), limit))
    return list(cur.fetchall())
