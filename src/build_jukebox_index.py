
#!/usr/bin/env python3
import os, json, time
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

def parse_year_from_value(v) -> int | None:
    """
    Accepts '1967', '1967-12-27', '1967-12', etc.
    Returns int year or None.
    """
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

def parse_year(tags: dict) -> int | None:
    """
    Priority:
      1) originaldate
      2) originalyear
      3) date
      4) year
    This matches what your Dylan files show:
      date=2003, originaldate=1967-12-27
    """
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
        album  = norm(pick_first(tags.get("album")))
        title  = norm(pick_first(tags.get("title")))
        year   = parse_year(tags)

        if not title:
            base = os.path.basename(path)
            title = os.path.splitext(base)[0]

        return {
            "path": path,
            "artist": artist,
            "album": album,
            "title": title,
            "year": year,
            "duration": duration
        }
    except Exception:
        return None

def main():
    t0 = time.time()
    tracks = []
    seen = 0

    for dirpath, _, filenames in os.walk(MUSIC_ROOT):
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in AUDIO_EXTS:
                continue
            seen += 1
            full = os.path.join(dirpath, fn)
            meta = read_tags(full)
            if meta:
                tracks.append(meta)

            if seen % 5000 == 0:
                print(f"Scanned {seen} audio files... indexed {len(tracks)} tracks")

    data = {
        "music_root": MUSIC_ROOT,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tracks": tracks
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    dt = time.time() - t0
    print(f"\nWrote {OUT_JSON}")
    print(f"Indexed {len(tracks)} tracks in {dt:.1f}s")

if __name__ == "__main__":
    main()
