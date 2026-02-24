#!/usr/bin/env python3
import re
import os
import sys
import socket
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import random
import subprocess
import time
from pathlib import Path
from difflib import get_close_matches
from faster_whisper import WhisperModel
from library_db import db_connect, fetch_tracks_for_artist, fetch_tracks_for_artist_year_range, build_target_playlist, write_m3u

AUDIO_FILE = "utterance.wav"
ARTISTS_FILE = "artists.txt"
MUSIC_ROOT = "/mnt/lossless"
PLAYLIST_SECONDS = 3600


MPV_IPC_SOCK = os.environ.get("MPV_IPC_SOCK", "/tmp/radio_mpv.sock")

def mpv_send(cmd):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(MPV_IPC_SOCK)
    s.send((json.dumps({"command": cmd}) + "\n").encode())
    s.recv(65536)
    s.close()

def mpv_get(prop):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(MPV_IPC_SOCK)
    s.send((json.dumps({"command": ["get_property", prop]}) + "\n").encode())
    data = s.recv(65536)
    s.close()
    return json.loads(data.decode(errors="ignore")).get("data")

def enqueue_next_mpv(paths):
    if not paths:
        return 0
    if not Path(MPV_IPC_SOCK).exists():
        print(f"[WARN] MPV socket missing: {MPV_IPC_SOCK}", flush=True)
        return 0

    cur_pos = mpv_get("playlist-pos")
    if cur_pos is None:
        print("[WARN] Could not read mpv playlist-pos", flush=True)
        return 0

    insert_pos = int(cur_pos) + 1
    added = 0
    for path in paths:
        before = mpv_get("playlist-count")
        if before is None:
            break
        mpv_send(["loadfile", path, "append"])
        mpv_send(["playlist-move", int(before), int(insert_pos)])
        insert_pos += 1
        added += 1
    return added

current_player = None

ARECORD_CMD = [
    "arecord",
    "-D", "default",
    "-f", "S16_LE",
    "-r", "16000",
    "-c", "1",
    AUDIO_FILE,
]

def normalize(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9+& ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
def load_artists():
    with open(ARTISTS_FILE, "r", encoding="utf-8", errors="ignore") as f:
        return [line.strip() for line in f if line.strip()]


def detect_decade(text):
    t = normalize(text)

    # 80s, 80's, 80 s
    m = re.search(r"\b([0-9]{2})\s*s\b", t)
    if m:
        two = int(m.group(1))
        if two == 0:
            start = 2000
        elif two <= 29:
            start = 2000 + two
        else:
            start = 1900 + two
        return start, start + 9, f"{start}s"

    # 1980s, 1980's, 1980 s
    m = re.search(r"\b(19[0-9]{2}|20[0-9]{2})\s*s\b", t)
    if m:
        start = int(m.group(1))
        start = (start // 10) * 10
        return start, start + 9, f"{start}s"

    # specific year like 1987
    m = re.search(r"\b(19[0-9]{2}|20[0-9]{2})\b", t)
    if m:
        year = int(m.group(1))
        return year, year, str(year)

    return None, None, None

def pick_artist(user_text, artists):
    t = normalize(user_text)
    t = re.sub(r"^(play|put on|start|shuffle)\s+", "", t).strip()

    # remove year/decade words so matching artist is easier
    t = re.sub(r"\b([0-9]{2})\s*s\b", " ", t)
    t = re.sub(r"\b(19[0-9]{2}|20[0-9]{2})\s*s\b", " ", t)
    t = re.sub(r"\b(19[0-9]{2}|20[0-9]{2})\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    for a in artists:
        an = normalize(a)
        if an and an in t:
            return a

    norm_map = {normalize(a): a for a in artists}
    candidates = get_close_matches(t, list(norm_map.keys()), n=3, cutoff=0.6)
    if not candidates:
        return "NONE"
    return norm_map[candidates[0]]

def record_audio():
    print("\nAUTO TEST: recording will START now (4 seconds)...", flush=True)
    time.sleep(0.2)

    print("AUTO TEST: Recording 4 seconds...")
    rec = subprocess.Popen(ARECORD_CMD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    time.sleep(7.0)
    time.sleep(0.2)

    rec.terminate()
    try:
        rec.wait(timeout=1.5)
    except subprocess.TimeoutExpired:
        rec.kill()
        rec.wait()

    print("Recorded.")

def transcribe(asr_model):
    segments, _ = asr_model.transcribe(AUDIO_FILE, language="en")
    return "".join(s.text for s in segments).strip()
def stop_current():
    global current_player
    if current_player and current_player.poll() is None:
        current_player.terminate()
        try:
            current_player.wait(timeout=3)
        except subprocess.TimeoutExpired:
            current_player.kill()
            current_player.wait()

def play_artist_sqlite(artist_name: str):
    global current_player
    con = db_connect()
    rows = fetch_tracks_for_artist(con, artist_name)
    con.close()

    playlist_paths, total = build_target_playlist(rows, target_seconds=PLAYLIST_SECONDS)
    m3u = write_m3u(playlist_paths)

    if not m3u:
        print(f"No playable tracks found in DB for: {artist_name}")
        return

    mins = int(total // 60)
    print(f"Queueing NEXT: ~{mins} mins of {artist_name} ({len(playlist_paths)} tracks)", flush=True)
    n = enqueue_next_mpv(playlist_paths)
    if n:
        print(f"Queued NEXT into mpv: {n} track(s)", flush=True)
    else:
        print("[WARN] Nothing queued (mpv socket missing?)", flush=True)
def play_random_sqlite():
    global current_player
    con = db_connect()
    rows = con.execute("""
        SELECT path, duration
        FROM tracks
        WHERE duration IS NOT NULL AND duration > 30
          AND path NOT LIKE '%/Playlists/%'
          AND path NOT LIKE '/mnt/lossless/Playlists/%'
        ORDER BY RANDOM()
        LIMIT 5000
    """).fetchall()
    con.close()

    playlist_paths, total = build_target_playlist(rows, target_seconds=PLAYLIST_SECONDS)
    m3u = write_m3u(playlist_paths)
    if not m3u:
        print("No tracks available for random play.")
        return

    print(f"Playing random mix (~{int(total//60)} mins) ({len(playlist_paths)} tracks)")
    stop_current()
    current_player = subprocess.Popen(
        ["mpv", "--no-video", "--shuffle", f"--playlist={m3u}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

def main():
    global current_player
    print("Voice Jukebox ready. Ctrl+C to quit.")
    artists = load_artists()
    print(f"Loaded {len(artists)} artists.")
    print("Using SQLite index: /home/dan/jukebox.db")

    print("Loading ASR model...")
    asr = WhisperModel("small", compute_type="int8")
    print("Ready.")

    while True:
        record_audio()
        text = transcribe(asr)
        print("You: " + text)
        t = normalize(text)
        if t in {"play some music", "play music", "play some", "play something", "surprise me"}:
            play_random_sqlite()
            continue


        y1, y2, label = detect_decade(text)
        artist = pick_artist(text, artists)

        if artist == "NONE":
            print("No confident match.")
            continue

        if label:
            print(f"Building ~1 hour playlist: {label} {artist}")
            con = db_connect()
            rows = fetch_tracks_for_artist_year_range(con, artist, y1, y2)
            con.close()

            playlist_paths, total = build_target_playlist(rows, target_seconds=PLAYLIST_SECONDS)
            m3u = write_m3u(playlist_paths)
            if not m3u:
                print(f"No indexed tracks found for {artist} in {y1}-{y2}.")
                continue

            print(f"Picked {len(playlist_paths)} tracks (~{int(total)}s)")
            stop_current()
            current_player = subprocess.Popen(["mpv",
                "--no-video",
                "--shuffle",
                f"--playlist={m3u}"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            play_artist_sqlite(artist)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye")
