#!/usr/bin/env python3
import os
import json
import time
import argparse
from mutagen import File as MutagenFile

MUSIC_ROOT = "/mnt/lossless"
OUT_JSON = "/home/dan/jukebox_index.json"

AUDIO_EXTS = {".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".aiff", ".alac"}

def pick_first(tag):
    if tag is None:
        return None
    if isinstance(tag, list):
        return str(tag[0]) if tag else None
    return str(tag)

def norm(s):
    return " ".join(str(s).strip().split()) if s else None

def parse_year_from_value(v):
    if not v:
        return None
    v = str(v).strip()
    if len(v) < 4:
        return None
    head = v[:4]
    try:
        y = int(head)
        if 1000 <= y <= 3000:
            return y
    except Exception:
        return None
    return None

def parse_year(tags: dict):
    # Priority: originaldate/originalyear over date/year
    for key in ("originaldate", "originalyear", "date", "year"):
        v = pick_first(tags.get(key))
        y = parse_year_from_value(v)
        if y is not None:
            return y
    return None

def read_tags(path: str):
    try:
        m = MutagenFile(path, easy=True)
        if not m:
            return None
        tags = dict(m.tags or {})
        info = m.info
        duration = float(getattr(info, "length", 0.0) or 0.0)

        artist = norm(pick_first(tags.get("artist")))
        album = norm(pick_first(tags.get("album")))
        title = norm(pick_first(tags.get("title")))
        year = parse_year(tags)

        if not title:
            base = os.path.basename(path)
            title = os.path.splitext(base)[0]

        return {
            "path": path,
            "artist": artist,
            "album": album,
            "title": title,
            "year": year,
            "duration": duration,
        }
    except Exception:
        return None

def scan_audio_files():
    for dirpath, _, filenames in os.walk(MUSIC_ROOT):
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in AUDIO_EXTS:
                yield os.path.join(dirpath, fn)

def file_sig(path: str):
    try:
        st = os.stat(path)
        return (st.st_size, int(st.st_mtime))
    except Exception:
        return None

def load_existing_index():
    if not os.path.exists(OUT_JSON):
        return {}
    try:
        with open(OUT_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        tracks = data.get("tracks", [])
        # map: path -> (track, sig)
        m = {}
        for t in tracks:
            p = t.get("path")
            if not p:
                continue
            sig = file_sig(p)
            m[p] = (t, sig)
        return m
    except Exception:
        return {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="Incremental update (only rescan changed/new files)")
    args = ap.parse_args()

    t0 = time.time()
    tracks = []
    seen = 0

    existing = load_existing_index() if args.update else {}
    existing_paths = set(existing.keys())

    kept = 0
    changed = 0
    new = 0

    for full in scan_audio_files():
        seen += 1
        sig = file_sig(full)

        if args.update and full in existing:
            old_track, old_sig = existing[full]
            if old_sig == sig and old_track:
                tracks.append(old_track)
                kept += 1
            else:
                meta = read_tags(full)
                if meta:
                    tracks.append(meta)
                    changed += 1
        else:
            meta = read_tags(full)
            if meta:
                tracks.append(meta)
                new += 1

        if seen % 5000 == 0:
            print(f"Scanned {seen} audio files... indexed {len(tracks)} tracks")

    # Removed files (present in old index, missing now) automatically drop out because we only add scanned files.

    data = {
        "music_root": MUSIC_ROOT,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "update" if args.update else "full",
        "tracks": tracks,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    dt = time.time() - t0
    print(f"\nWrote {OUT_JSON}")
    print(f"Indexed {len(tracks)} tracks in {dt:.1f}s (seen {seen})")
    if args.update:
        print(f"Kept {kept} unchanged, updated {changed}, added {new}")

if __name__ == "__main__":
    main()
