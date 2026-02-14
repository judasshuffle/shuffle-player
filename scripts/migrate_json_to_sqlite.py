#!/usr/bin/env python3
import json, os, sqlite3, time
from pathlib import Path

JSON_PATH = "/home/dan/jukebox_index.json"
DB_PATH   = "/home/dan/jukebox.db"

def connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tracks (
  path           TEXT PRIMARY KEY,
  artist         TEXT,
  artist_sort    TEXT,
  album          TEXT,
  title          TEXT,
  tracknumber    INTEGER,
  year           INTEGER,
  duration       REAL,
  bitrate        INTEGER,
  samplerate     INTEGER,
  channels       INTEGER,
  mtime          INTEGER NOT NULL,
  size           INTEGER NOT NULL,
  ext            TEXT,
  added_at       INTEGER NOT NULL,
  updated_at     INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
CREATE INDEX IF NOT EXISTS idx_tracks_year   ON tracks(year);
CREATE INDEX IF NOT EXISTS idx_tracks_dur    ON tracks(duration);

CREATE TABLE IF NOT EXISTS scan_state (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

def norm_int(v):
    try:
        if v is None: return None
        if isinstance(v, str) and not v.strip(): return None
        return int(v)
    except Exception:
        return None

def norm_float(v):
    try:
        if v is None: return None
        return float(v)
    except Exception:
        return None

def main():
    now = int(time.time())

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Support either {"tracks":[...]} or direct list
    tracks = data["tracks"] if isinstance(data, dict) and "tracks" in data else data
    if not isinstance(tracks, list):
        raise SystemExit("JSON format unexpected; expected list or {'tracks':[...]}")

    con = connect(DB_PATH)
    con.executescript(SCHEMA_SQL)

    # If old JSON doesn’t have mtime/size, set to 0 and let the incremental updater fix it later.
    rows = []
    for t in tracks:
        path = t.get("path") or t.get("filepath") or t.get("file")
        if not path:
            continue

        ext = Path(path).suffix.lower()
        rows.append((
            path,
            t.get("artist"),
            t.get("artist_sort"),
            t.get("album"),
            t.get("title"),
            norm_int(t.get("tracknumber") or t.get("track")),
            norm_int(t.get("year") or t.get("date")),
            norm_float(t.get("duration")),
            norm_int(t.get("bitrate")),
            norm_int(t.get("samplerate")),
            norm_int(t.get("channels")),
            norm_int(t.get("mtime")) or 0,
            norm_int(t.get("size")) or 0,
            ext,
            now,
            now,
        ))

    con.executemany("""
      INSERT INTO tracks(
        path, artist, artist_sort, album, title, tracknumber, year, duration,
        bitrate, samplerate, channels, mtime, size, ext, added_at, updated_at
      )
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(path) DO UPDATE SET
        artist=excluded.artist,
        artist_sort=excluded.artist_sort,
        album=excluded.album,
        title=excluded.title,
        tracknumber=excluded.tracknumber,
        year=excluded.year,
        duration=excluded.duration,
        bitrate=excluded.bitrate,
        samplerate=excluded.samplerate,
        channels=excluded.channels,
        mtime=CASE WHEN excluded.mtime!=0 THEN excluded.mtime ELSE tracks.mtime END,
        size=CASE WHEN excluded.size!=0 THEN excluded.size ELSE tracks.size END,
        ext=excluded.ext,
        updated_at=excluded.updated_at
    """, rows)

    con.execute("INSERT OR REPLACE INTO scan_state(key,value) VALUES(?,?)",
                ("migrated_from_json_at", str(now)))
    con.commit()
    con.close()

    print(f"Imported {len(rows)} tracks into {DB_PATH} from {JSON_PATH}")

if __name__ == "__main__":
    main()
