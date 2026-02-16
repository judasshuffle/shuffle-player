#!/usr/bin/env python3
import argparse
import os
import sys
import time
import sqlite3
from pathlib import Path
from mutagen import File as MutagenFile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from config import MUSIC_ROOT, DB_PATH

AUDIO_EXTS = {".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".aiff", ".alac"}

def connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con

def ensure_schema(con: sqlite3.Connection):
    con.executescript("""
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
      updated_at     INTEGER NOT NULL,
      genre          TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
    CREATE INDEX IF NOT EXISTS idx_tracks_year   ON tracks(year);
    CREATE INDEX IF NOT EXISTS idx_tracks_dur    ON tracks(duration);

    CREATE TABLE IF NOT EXISTS scan_state (
      key   TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );
    """)
    # Existing DBs: add genre column if missing (CREATE TABLE IF NOT EXISTS won't alter existing table)
    try:
        con.execute("ALTER TABLE tracks ADD COLUMN genre TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise
    con.execute("CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks(genre)")

def is_playlists_path(p: str) -> bool:
    s = p.replace("\\", "/")
    return "/Playlists/" in s or s.endswith("/Playlists") or s.startswith(f"{MUSIC_ROOT}/Playlists/")

def pick_first(tag):
    if tag is None:
        return None
    if isinstance(tag, list):
        return str(tag[0]) if tag else None
    return str(tag)

def norm(s):
    return " ".join(str(s).strip().split()) if s else None

def read_tags(path: str):
    m = MutagenFile(path, easy=True)
    if not m:
        return None
    tags = m.tags or {}
    info = getattr(m, "info", None)

    artist = norm(pick_first(tags.get("artist") or tags.get("albumartist")))
    album  = norm(pick_first(tags.get("album")))
    title  = norm(pick_first(tags.get("title")))
    year   = pick_first(tags.get("date")) or pick_first(tags.get("originaldate")) or pick_first(tags.get("year"))

    tn_raw = pick_first(tags.get("tracknumber"))
    tracknumber = None
    if tn_raw:
        try:
            tracknumber = int(str(tn_raw).split("/")[0])
        except Exception:
            tracknumber = None

    year_i = None
    if year:
        try:
            year_i = int(str(year)[:4])
        except Exception:
            year_i = None

    genre_raw = tags.get("genre") or tags.get("genres")
    if genre_raw is not None and isinstance(genre_raw, list) and genre_raw:
        genre = norm(str(genre_raw[0]))
    elif genre_raw is not None:
        genre = norm(str(genre_raw))
    else:
        genre = None

    duration = None
    bitrate = samplerate = channels = None
    if info:
        length = getattr(info, "length", None)
        duration = float(length) if length else None
        br = getattr(info, "bitrate", None)
        bitrate = int(br) if br else None
        sr = getattr(info, "sample_rate", None)
        samplerate = int(sr) if sr else None
        ch = getattr(info, "channels", None)
        channels = int(ch) if ch else None

    return {
        "artist": artist,
        "album": album,
        "title": title,
        "tracknumber": tracknumber,
        "year": year_i,
        "genre": genre,
        "duration": duration,
        "bitrate": bitrate,
        "samplerate": samplerate,
        "channels": channels,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="Re-read tags for every file and update rows even if mtime/size match")
    args = ap.parse_args()
    force = args.force

    con = connect()
    ensure_schema(con)

    now = int(time.time())

    scanned = inserted = changed = skipped = 0

    # speed: fetch existing mtime/size into a dict once (17k rows is fine)
    existing = {}
    for path, mtime, size in con.execute("SELECT path, mtime, size FROM tracks"):
        existing[path] = (int(mtime), int(size))

    def get_added_at(path: str):
        row = con.execute("SELECT added_at FROM tracks WHERE path=?", (path,)).fetchone()
        return int(row[0]) if row else now

    for root, dirs, files in os.walk(MUSIC_ROOT):
        # prune Playlists from traversal
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

            mtime = int(st.st_mtime)
            size  = int(st.st_size)

            scanned += 1

            prev = existing.get(path)
            if not force and prev and prev[0] == mtime and prev[1] == size and prev[0] != 0:
                skipped += 1
                continue

            meta = read_tags(path)
            if meta is None:
                meta = {"artist": None, "album": None, "title": None, "tracknumber": None,
                        "year": None, "genre": None, "duration": None, "bitrate": None, "samplerate": None, "channels": None}

            existed = prev is not None
            added_at = get_added_at(path) if existed else now

            con.execute("""
              INSERT INTO tracks(path,artist,album,title,tracknumber,year,genre,duration,bitrate,samplerate,channels,
                                 mtime,size,ext,added_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(path) DO UPDATE SET
                artist=excluded.artist,
                album=excluded.album,
                title=excluded.title,
                tracknumber=excluded.tracknumber,
                year=excluded.year,
                genre=excluded.genre,
                duration=excluded.duration,
                bitrate=excluded.bitrate,
                samplerate=excluded.samplerate,
                channels=excluded.channels,
                mtime=excluded.mtime,
                size=excluded.size,
                ext=excluded.ext,
                updated_at=excluded.updated_at
            """, (
                path,
                meta["artist"], meta["album"], meta["title"], meta["tracknumber"], meta["year"], meta["genre"],
                meta["duration"], meta["bitrate"], meta["samplerate"], meta["channels"],
                mtime, size, ext,
                added_at,
                now
            ))

            existing[path] = (mtime, size)

            if existed:
                changed += 1
            else:
                inserted += 1

            if (inserted + changed) % 250 == 0:
                con.commit()

    con.execute("INSERT OR REPLACE INTO scan_state(key,value) VALUES(?,?)", ("last_scan_at", str(now)))
    con.commit()
    con.close()

    print(f"Scanned: {scanned} | Inserted: {inserted} | Changed: {changed} | Skipped: {skipped}")

if __name__ == "__main__":
    main()
