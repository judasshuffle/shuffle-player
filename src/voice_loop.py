#!/usr/bin/env python3
import json
import re
import os
import socket
import sys
import subprocess
import time
from difflib import get_close_matches

from faster_whisper import WhisperModel

# local modules (in same folder)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from library_db import (
    db_connect,
    fetch_tracks_for_artist,
    fetch_tracks_for_artist_year_range,
    build_target_playlist,
    write_m3u,
)
from config import ARTISTS_PATH

AUDIO_FILE = "utterance.wav"
AUDIO_FILE_NORM = "utterance_norm.wav"

# Build playlists about ~1 hour long
PLAYLIST_SECONDS = 3600

# IMPORTANT: stream mpv socket (created by start_stream.sh)
MPV_IPC_SOCK = "/tmp/radio_mpv.sock"

DUCK_VOLUME = 35
NORMAL_VOLUME = 70

START_STREAM_SH = "/home/dan/start_stream.sh"
STOP_STREAM_SH = "/home/dan/stop_stream.sh"

ARECORD_CMD = [
    "arecord",
    "-D", "default",
    "-f", "S16_LE",
    "-r", "16000",
    "-c", "1",
    "-d", "5",
    AUDIO_FILE,
]


def normalize(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9+& ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_artists():
    with open(ARTISTS_PATH, "r", encoding="utf-8", errors="ignore") as f:
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

    # direct substring match first
    for a in artists:
        an = normalize(a)
        if an and an in t:
            return a

    # fuzzy match fallback
    norm_map = {normalize(a): a for a in artists}
    candidates = get_close_matches(t, list(norm_map.keys()), n=3, cutoff=0.6)
    if not candidates:
        return "NONE"
    return norm_map[candidates[0]]


def mpv_ipc_send(command_list):
    """Send a JSON command to mpv over IPC. No-op if socket missing."""
    if not os.path.exists(MPV_IPC_SOCK):
        return False
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect(MPV_IPC_SOCK)
        sock.sendall((json.dumps({"command": command_list}) + "\n").encode("utf-8"))
        sock.close()
        return True
    except OSError:
        return False


def duck_audio():
    mpv_ipc_send(["set_property", "volume", DUCK_VOLUME])


def restore_audio():
    mpv_ipc_send(["set_property", "volume", NORMAL_VOLUME])


def record_audio():
    print("\nPress Enter to START recording...")
    sys.stdin.readline()
    time.sleep(0.2)

    duck_audio()
    print("Recording 5 seconds...")
    rec = subprocess.Popen(ARECORD_CMD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rec.wait()
    restore_audio()
    print("Recorded.")


def normalize_recording():
    """ffmpeg loudnorm -> returns norm file, or raw on failure."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", AUDIO_FILE, "-af", "loudnorm", "-ar", "16000", "-ac", "1", AUDIO_FILE_NORM],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        if r.returncode == 0 and os.path.isfile(AUDIO_FILE_NORM):
            return AUDIO_FILE_NORM
    except Exception:
        pass
    return AUDIO_FILE


def transcribe(asr_model, wav_path):
    segments, _ = asr_model.transcribe(wav_path, language="en")
    return "".join(s.text for s in segments).strip()


def ensure_stream_running():
    """If mpv socket isn't up, request start."""
    if os.path.exists(MPV_IPC_SOCK):
        return
    try:
        subprocess.Popen([START_STREAM_SH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)
    except Exception:
        pass


def load_playlist_into_stream(m3u_path: str, do_shuffle: bool = True):
    """Tell running stream mpv to replace playlist with this m3u."""
    ensure_stream_running()
    ok = mpv_ipc_send(["loadlist", os.path.abspath(m3u_path), "replace"])
    if do_shuffle:
        mpv_ipc_send(["playlist-shuffle"])
    mpv_ipc_send(["set_property", "pause", False])
    return ok


def build_and_play_artist(artist_name: str):
    con = db_connect()
    rows = fetch_tracks_for_artist(con, artist_name)
    con.close()

    playlist_paths, total = build_target_playlist(rows, target_seconds=PLAYLIST_SECONDS)
    m3u = write_m3u(playlist_paths)
    if not m3u:
        print(f"No playable tracks found in DB for: {artist_name}")
        return

    mins = int(total // 60)
    print(f"Loading ~{mins} mins of {artist_name} ({len(playlist_paths)} tracks) into stream")
    load_playlist_into_stream(m3u, do_shuffle=True)


def build_and_play_artist_year_range(artist_name: str, y1: int, y2: int, label: str):
    con = db_connect()
    rows = fetch_tracks_for_artist_year_range(con, artist_name, y1, y2)
    con.close()

    playlist_paths, total = build_target_playlist(rows, target_seconds=PLAYLIST_SECONDS)
    m3u = write_m3u(playlist_paths)
    if not m3u:
        print(f"No indexed tracks found for {artist_name} in {y1}-{y2}.")
        return

    print(f"Loading {label} {artist_name} ({len(playlist_paths)} tracks) into stream")
    load_playlist_into_stream(m3u, do_shuffle=True)


def build_and_play_random():
    con = db_connect()
    rows = con.execute(
        """
        SELECT path, duration
        FROM tracks
        WHERE duration IS NOT NULL AND duration > 30
          AND path NOT LIKE '%/Playlists/%'
          AND path NOT LIKE '/mnt/lossless/Playlists/%'
        ORDER BY RANDOM()
        LIMIT 5000
        """
    ).fetchall()
    con.close()

    playlist_paths, total = build_target_playlist(rows, target_seconds=PLAYLIST_SECONDS)
    m3u = write_m3u(playlist_paths)
    if not m3u:
        print("No tracks available for random play.")
        return

    print(f"Loading random mix (~{int(total//60)} mins) ({len(playlist_paths)} tracks) into stream")
    load_playlist_into_stream(m3u, do_shuffle=True)


def main():
    # mic presence check
    test = subprocess.run(["arecord", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out = (test.stdout or "") + "\n" + (test.stderr or "")
    if "card" not in out.lower():
        print("No microphone detected. Plug in mic and restart.")
        return

    print("Voice Jukebox ready. Ctrl+C to quit.")
    artists = load_artists()
    print(f"Loaded {len(artists)} artists.")
    print("Using SQLite index: /home/dan/jukebox.db")
    print("Using stream mpv socket:", MPV_IPC_SOCK)

    print("Loading ASR model...")
    asr = WhisperModel("small", compute_type="int8")
    print("Ready.")

    while True:
        record_audio()
        wav_path = normalize_recording()
        text = transcribe(asr, wav_path)
        print("You: " + text)
        t = normalize(text)

        # Stream control
        if t in {"start stream", "start the stream", "start radio", "start the radio"}:
            subprocess.Popen([START_STREAM_SH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("Stream start requested.")
            continue

        if t in {"stop stream", "stop the stream", "stop radio", "stop the radio"}:
            subprocess.Popen([STOP_STREAM_SH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("Stream stop requested.")
            continue

        # Transport controls
        if t in {"skip", "next", "next song"}:
            ensure_stream_running()
            mpv_ipc_send(["playlist-next", "force"])
            print("Skipped.")
            continue

        # Music selection
        if t in {"play some music", "play music", "play some", "play something", "surprise me"}:
            build_and_play_random()
            continue

        y1, y2, label = detect_decade(text)
        artist = pick_artist(text, artists)

        if artist == "NONE":
            print("No confident artist match.")
            continue

        if label:
            print(f"Building ~1 hour playlist: {label} {artist}")
            build_and_play_artist_year_range(artist, y1, y2, label)
        else:
            build_and_play_artist(artist)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye")
