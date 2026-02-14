#!/usr/bin/env python3
import re
import os
import json
import random
import subprocess
import time
from difflib import get_close_matches
from faster_whisper import WhisperModel

AUDIO_FILE = "utterance.wav"
ARTISTS_FILE = "artists.txt"
MUSIC_ROOT = "/mnt/lossless"
INDEX_FILE = "/home/dan/jukebox_index.json"
PLAYLIST_SECONDS = 3600

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

def load_index_tracks():
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    tracks = data.get("tracks", [])
    for t in tracks:
        t["_artist_norm"] = normalize(t.get("artist", ""))
    return tracks

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
    print("\nPress Enter to START recording...")
    input()
    time.sleep(0.2)

    print("Recording... press Enter to STOP.")
    rec = subprocess.Popen(ARECORD_CMD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    input()
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

def play_artist_folder(artist_folder):
    global current_player
    path = os.path.join(MUSIC_ROOT, artist_folder)
    print("Playing (artist shuffle): " + path)
    stop_current()
    current_player = subprocess.Popen(["mpv", "--no-video", "--shuffle", path])

def build_hour_playlist(tracks, artist_name, y1, y2):
    a_norm = normalize(artist_name)
    pool = []
    for t in tracks:
        if t.get("_artist_norm") != a_norm:
            continue
        y = t.get("year")
        if not isinstance(y, int):
            continue
        if y < y1 or y > y2:
            continue
        dur = float(t.get("duration") or 0.0)
        if dur <= 0:
            continue
        p = t.get("path")
        if not isinstance(p, str) or not p:
            continue
        if "/Playlists/" in p:
            continue
        pool.append((p, dur))

    random.shuffle(pool)
    out = []
    total = 0.0
    for p, dur in pool:
        out.append(p)
        total += dur
        if total >= PLAYLIST_SECONDS:
            break
    return out, total, len(pool)

def play_playlist_paths(paths):
    global current_player
    if not paths:
        return
    playlist_path = "/tmp/jukebox_playlist.m3u8"
    with open(playlist_path, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(p + "\n")

    print("Playing (playlist): " + playlist_path)
    stop_current()
    current_player = subprocess.Popen([
        "mpv",
        "--no-video",
        "--shuffle",
        f"--playlist={playlist_path}"
    ])

def main():
    print("Voice Jukebox ready. Ctrl+C to quit.")
    artists = load_artists()
    print(f"Loaded {len(artists)} artists.")
    print("Loading index...")
    tracks = load_index_tracks()
    print(f"Indexed tracks loaded: {len(tracks)}")

    print("Loading ASR model...")
    asr = WhisperModel("small", compute_type="int8")
    print("Ready.")

    while True:
        record_audio()
        text = transcribe(asr)
        print("You: " + text)

        y1, y2, label = detect_decade(text)
        artist = pick_artist(text, artists)

        if artist == "NONE":
            print("No confident match.")
            continue

        if label:
            print(f"Building ~1 hour playlist: {label} {artist}")
            paths, total, cand = build_hour_playlist(tracks, artist, y1, y2)
            if cand == 0 or not paths:
                print(f"No indexed tracks found for {artist} in {y1}-{y2}.")
                continue
            print(f"Picked {len(paths)} tracks from {cand} candidates (~{int(total)}s)")
            play_playlist_paths(paths)
        else:
            play_artist_folder(artist)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye")
