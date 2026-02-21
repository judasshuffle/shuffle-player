#!/usr/bin/env python3
import json, os, time, subprocess
from pathlib import Path
import urllib.parse, urllib.request

SOCK = "/tmp/radio_mpv.sock"
OUT = Path("/home/dan/shuffle-player/web/shufflizer/nowplaying.json")
TMP = OUT.with_suffix(".json.tmp")

ICECAST_URL = "http://127.0.0.1:8001/admin/metadata"
ICECAST_USER = "admin"
ICECAST_PASS = "hackmejudasshuffle"
ICECAST_MOUNT = "/stream.mp3"

def mpv_get(prop: str):
    msg = json.dumps({"command": ["get_property", prop]}) + "\n"
    p = subprocess.run(
        ["socat", "-", SOCK],
        input=msg.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if p.returncode != 0:
        return None
    try:
        r = json.loads(p.stdout.decode(errors="replace").strip() or "{}")
        if r.get("error") == "success":
            return r.get("data")
    except Exception:
        return None
    return None

def norm_md(md):
    if not isinstance(md, dict):
        return {}
    artist = md.get("ARTIST") or md.get("artist")
    title  = md.get("TITLE") or md.get("title")
    album  = md.get("ALBUM") or md.get("album")
    track  = md.get("track") or md.get("TRACKNUMBER") or md.get("TRACK")
    year   = md.get("DATE") or md.get("date") or md.get("YEAR") or md.get("year")
    return {"artist": artist, "title": title, "album": album, "track": track, "year": year}

def write_json(obj):
    TMP.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    os.replace(TMP, OUT)

def update_icecast_metadata(artist, title):
    if not artist or not title:
        return
    song = f"{artist} - {title}"
    params = urllib.parse.urlencode({"mode": "updinfo", "mount": ICECAST_MOUNT, "song": song})
    url = f"{ICECAST_URL}?{params}"

    mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password(None, ICECAST_URL, ICECAST_USER, ICECAST_PASS)
    opener = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(mgr))

    try:
        opener.open(url, timeout=3).read()
    except Exception:
        pass

def main():
    last_sig = None
    while True:
        path = mpv_get("path")
        md = mpv_get("metadata")
        d = norm_md(md)

        sig = (path, d.get("artist"), d.get("title"), d.get("album"), d.get("track"), d.get("year"))
        if sig != last_sig:
            payload = {"ts": int(time.time()), "path": path, **d}
            try:
                OUT.parent.mkdir(parents=True, exist_ok=True)
                write_json(payload)
                update_icecast_metadata(payload.get("artist"), payload.get("title"))
            except Exception:
                pass
            last_sig = sig

        time.sleep(1)

if __name__ == "__main__":
    main()
