#!/usr/bin/env python3

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import json
import os
import subprocess
import socket
import urllib.request
import re
import time

ROOT = "/home/dan/shuffle-player/web/shufflizer"
PORT = 8091
MPV_SOCKET = "/tmp/radio_mpv.sock"
NOWPLAYING_JSON = "/home/dan/shuffle-player/web/shufflizer/nowplaying.json"
RESYNC_SCRIPT = "/home/dan/shuffle-player/scripts/resync_jukebox_db.sh"
COVER_CACHE = os.path.join(ROOT, "nowplaying_cover.jpg")

SERVICES = {
    "icecast": "icecast2.service",
    "mp3_stream": "shuffle-radio.service",
    "snapserver": "snapserver.service",
    "snapfifo_feed": "shuffle-snapfifo-feed.service",
}

GROUPS = {
    "everything": ["icecast"],
}

AUDIO_ENV = {
    **os.environ,
    "XDG_RUNTIME_DIR": "/run/user/1000",
    "PULSE_SERVER": "unix:/run/user/1000/pulse/native",
}

_LAST_COVER_TRACK = None
_LAST_COVER_URL = ""


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def is_active(service):
    r = run(["sudo", "systemctl", "is-active", service])
    return (r.returncode == 0) and (r.stdout.strip() == "active")


def icecast_mp3_active():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8001/status-json.xsl", timeout=2) as r:
            data = json.loads(r.read().decode())

        src = data.get("icestats", {}).get("source")

        if isinstance(src, list):
            for s in src:
                if s.get("listenurl", "").endswith("/stream.mp3"):
                    return True

        elif isinstance(src, dict):
            if src.get("listenurl", "").endswith("/stream.mp3"):
                return True

    except Exception:
        pass

    return False


def resolve_art_url(data):
    candidates = (
        "cover_url",
        "art_url",
        "cover",
        "art",
        "image",
        "album_art",
    )

    for key in candidates:
        raw = str(data.get(key, "")).strip()
        if not raw:
            continue

        if raw.startswith(("http://", "https://", "data:")):
            return raw

        if raw.startswith("/"):
            return raw

        candidate = os.path.join(ROOT, raw)
        if os.path.exists(candidate):
            return "/" + raw.replace(os.sep, "/")

        if os.path.isabs(raw) and os.path.exists(raw):
            try:
                rel = os.path.relpath(raw, ROOT)
                if not rel.startswith(".."):
                    return "/" + rel.replace(os.sep, "/")
            except Exception:
                pass

    return ""


def mpv_ipc(command):
    request_id = int(time.time() * 1000) % 1000000000
    payload = json.dumps({"command": command, "request_id": request_id}) + "\n"

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        s.connect(MPV_SOCKET)
        s.sendall(payload.encode("utf-8"))

        buf = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk

            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode("utf-8", errors="replace"))
                except Exception:
                    continue
                if msg.get("request_id") == request_id:
                    return msg

    return None


def mpv_get_property(prop):
    try:
        msg = mpv_ipc(["get_property", prop])
        if msg and msg.get("error") == "success":
            return msg.get("data")
    except Exception:
        pass
    return None


def get_current_track_path(nowplaying_data=None):
    path_candidates = []
    if isinstance(nowplaying_data, dict):
        for key in ("path", "file", "filename"):
            raw = str(nowplaying_data.get(key, "")).strip()
            if raw:
                path_candidates.append(raw)

    mpv_path = mpv_get_property("path")
    if isinstance(mpv_path, str) and mpv_path.strip():
        path_candidates.insert(0, mpv_path.strip())

    workdir = mpv_get_property("working-directory")
    if isinstance(workdir, str):
        workdir = workdir.strip()
    else:
        workdir = ""

    for raw in path_candidates:
        if os.path.isabs(raw) and os.path.exists(raw):
            return raw

        if workdir:
            candidate = os.path.abspath(os.path.join(workdir, raw))
            if os.path.exists(candidate):
                return candidate

    return ""


def find_folder_art(track_path):
    if not track_path:
        return ""

    folder = os.path.dirname(track_path)
    names = (
        "cover.jpg",
        "cover.jpeg",
        "cover.png",
        "folder.jpg",
        "folder.jpeg",
        "folder.png",
        "front.jpg",
        "front.jpeg",
        "front.png",
    )

    for name in names:
        candidate = os.path.join(folder, name)
        if os.path.exists(candidate):
            try:
                rel = os.path.relpath(candidate, ROOT)
                if not rel.startswith(".."):
                    return "/" + rel.replace(os.sep, "/")
            except Exception:
                pass

    return ""


def cover_cache_url():
    if os.path.exists(COVER_CACHE):
        return f"/nowplaying_cover.jpg?t={int(os.path.getmtime(COVER_CACHE))}"
    return ""


def extract_embedded_cover(track_path):
    if not track_path or not os.path.exists(track_path):
        return ""

    try:
        if os.path.exists(COVER_CACHE):
            os.remove(COVER_CACHE)
    except Exception:
        pass

    cmd = [
        "/usr/bin/ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        track_path,
        "-an",
        "-map",
        "0:v:0",
        "-frames:v",
        "1",
        "-c:v",
        "mjpeg",
        COVER_CACHE,
    ]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        if r.returncode == 0 and os.path.exists(COVER_CACHE) and os.path.getsize(COVER_CACHE) > 0:
            return cover_cache_url()
    except Exception:
        pass

    return ""


def get_nowplaying_art(nowplaying_data):
    global _LAST_COVER_TRACK, _LAST_COVER_URL

    explicit = resolve_art_url(nowplaying_data)
    if explicit:
        _LAST_COVER_TRACK = None
        _LAST_COVER_URL = explicit
        return explicit

    track_path = get_current_track_path(nowplaying_data)

    if track_path and track_path == _LAST_COVER_TRACK:
        if _LAST_COVER_URL:
            return _LAST_COVER_URL
        if os.path.exists(COVER_CACHE):
            _LAST_COVER_URL = cover_cache_url()
            return _LAST_COVER_URL

    extracted = extract_embedded_cover(track_path)
    if extracted:
        _LAST_COVER_TRACK = track_path
        _LAST_COVER_URL = extracted
        return extracted

    folder_art = find_folder_art(track_path)
    if folder_art:
        _LAST_COVER_TRACK = track_path
        _LAST_COVER_URL = folder_art
        return folder_art

    _LAST_COVER_TRACK = track_path or None
    _LAST_COVER_URL = ""
    return ""


def db_to_percent(db_value):
    if db_value is None:
        return 0

    db_value = max(-60.0, min(0.0, db_value))
    return int(round(((db_value + 60.0) / 60.0) * 100))


def get_vu_levels():
    cmd = [
        "/usr/bin/ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "info",
        "-f",
        "pulse",
        "-i",
        "radio_sink.monitor",
        "-t",
        "0.15",
        "-af",
        "astats=metadata=0:reset=1:measure_perchannel=Peak_level",
        "-f",
        "null",
        "-",
    ]

    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3,
            env=AUDIO_ENV,
        )
        text = (r.stdout or "") + "\n" + (r.stderr or "")
        peaks = [float(x) for x in re.findall(r"Peak level dB:\s*(-?\d+(?:\.\d+)?)", text)]

        if len(peaks) >= 2:
            left_db, right_db = peaks[0], peaks[1]
        elif len(peaks) == 1:
            left_db = right_db = peaks[0]
        else:
            return {
                "left": 0,
                "right": 0,
                "left_db": None,
                "right_db": None,
            }

        return {
            "left": db_to_percent(left_db),
            "right": db_to_percent(right_db),
            "left_db": left_db,
            "right_db": right_db,
        }

    except Exception:
        return {
            "left": 0,
            "right": 0,
            "left_db": None,
            "right_db": None,
        }


def get_output_status():
    mp3_on = icecast_mp3_active()
    snapserver_on = is_active("snapserver.service")
    snapfifo_feed_on = is_active("shuffle-snapfifo-feed.service")

    if snapserver_on and snapfifo_feed_on:
        snapcast_state = "running"
    elif snapserver_on or snapfifo_feed_on:
        snapcast_state = "partial"
    else:
        snapcast_state = "stopped"

    return {
        "mp3_stream": mp3_on,
        "snapserver": snapserver_on,
        "snapfifo_feed": snapfifo_feed_on,
        "snapcast_state": snapcast_state,
    }


def control_output(output_name, action):
    if action not in ("start", "stop", "restart"):
        return {"ok": False, "error": f"bad action: {action}"}

    if output_name == "mp3_stream":
        svc = "shuffle-radio.service"
        r = run(["sudo", "systemctl", action, svc])
        return {
            "ok": r.returncode == 0,
            "output": output_name,
            "status": get_output_status(),
        }

    if output_name == "snapcast_hd":
        results = []

        if action == "start":
            results.append(run(["sudo", "systemctl", "restart", "snapserver.service"]))
            results.append(run(["sudo", "systemctl", "reset-failed", "shuffle-snapfifo-feed.service"]))
            results.append(run(["sudo", "systemctl", "restart", "shuffle-snapfifo-feed.service"]))

        elif action == "stop":
            results.append(run(["sudo", "systemctl", "stop", "shuffle-snapfifo-feed.service"]))
            results.append(run(["sudo", "systemctl", "stop", "snapserver.service"]))

        elif action == "restart":
            results.append(run(["sudo", "systemctl", "restart", "snapserver.service"]))
            results.append(run(["sudo", "systemctl", "reset-failed", "shuffle-snapfifo-feed.service"]))
            results.append(run(["sudo", "systemctl", "restart", "shuffle-snapfifo-feed.service"]))

        ok = all(r.returncode == 0 for r in results)
        return {
            "ok": ok,
            "output": output_name,
            "status": get_output_status(),
        }

    return {"ok": False, "error": f"bad output: {output_name}"}


def mpv_command(command):
    msg = json.dumps({"command": command}) + "\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(MPV_SOCKET)
        s.sendall(msg.encode("utf-8"))


def read_nowplaying():
    if not os.path.exists(NOWPLAYING_JSON):
        return {
            "artist": "",
            "title": "",
            "album": "",
            "text": "Nothing loaded",
            "art_url": "",
        }

    try:
        with open(NOWPLAYING_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {
            "artist": "",
            "title": "",
            "album": "",
            "text": f"Now playing read error: {e}",
            "art_url": "",
        }

    artist = str(data.get("artist", "")).strip()
    title = str(data.get("title", "")).strip()
    album = str(data.get("album", "")).strip()

    if artist and title:
        text = f"{artist} — {title}"
    else:
        text = title or artist or "Nothing loaded"

    return {
        "artist": artist,
        "title": title,
        "album": album,
        "text": text,
        "art_url": get_nowplaying_art(data),
    }


def get_library_stats():
    db = "/home/dan/jukebox.db"
    music_root = "/mnt/lossless"

    result = {
        "db_path": db,
        "music_root": music_root,
        "track_count": None,
    }

    if not os.path.exists(db):
        return result

    try:
        import sqlite3
        con = sqlite3.connect(db)
        cur = con.cursor()
        result["track_count"] = cur.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
        con.close()
    except Exception:
        pass

    return result


DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Shuffle Control</title>

<style>
body{
  background:#0f1117;
  color:#e6e6e6;
  font-family:system-ui;
  margin:40px;
}
h1{ margin-bottom:30px; }
.grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(320px,1fr));
  gap:20px;
}
.card{
  background:#1b1f2a;
  padding:20px;
  border-radius:12px;
}
.card-wide{ grid-column:1 / -1; }
button{
  background:#2b3142;
  border:none;
  color:white;
  padding:10px 14px;
  border-radius:6px;
  margin:4px;
  cursor:pointer;
}
button:hover{ background:#3a4156; }
.ok{ color:#00ff99; font-weight:bold; }
.bad{ color:#ff4d4d; font-weight:bold; }
.warn{ color:#ffd166; font-weight:bold; }
.muted{ opacity:.8; }
.link{ color:#4db6ff; text-decoration:none; }
.link:hover{ text-decoration:underline; }
.value{ margin-top:8px; font-size:1.05rem; }
.small{ font-size:.92rem; opacity:.85; margin-top:6px; }
.output-block{
  margin-top:14px;
  padding-top:10px;
  border-top:1px solid rgba(255,255,255,.08);
}
#libraryResult{
  margin-top:12px;
  white-space:pre-wrap;
  font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size:.92rem;
  opacity:.92;
}
.nowplaying-wrap{
  display:flex;
  gap:20px;
  align-items:flex-start;
  flex-wrap:wrap;
}
.cover-wrap{
  width:160px;
  height:160px;
  border-radius:12px;
  overflow:hidden;
  background:#111622;
  border:1px solid rgba(255,255,255,.08);
  flex:0 0 160px;
  position:relative;
}
.cover-wrap img{
  width:100%;
  height:100%;
  object-fit:cover;
  display:none;
}
.cover-placeholder{
  width:100%;
  height:100%;
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:3rem;
  opacity:.35;
}
.np-meta{
  flex:1 1 320px;
  min-width:260px;
}
.vu-wrap{
  margin-top:16px;
}
.vu-row{
  display:grid;
  grid-template-columns:36px 1fr 46px;
  gap:10px;
  align-items:center;
  margin-top:8px;
}
.vu-label{
  font-size:.85rem;
  opacity:.85;
}
.vu-bar{
  width:100%;
  height:14px;
  background:#0d1017;
  border-radius:999px;
  overflow:hidden;
  border:1px solid rgba(255,255,255,.08);
}
.vu-fill{
  height:100%;
  width:0%;
  background:linear-gradient(90deg,#00ff99,#ffd166,#ff4d4d);
  transition:width .08s linear;
}
.vu-value{
  text-align:right;
  font-size:.85rem;
  opacity:.8;
}
</style>
</head>

<body>
<h1>Shuffle Control</h1>

<div class="grid">

  <div class="card card-wide">
    <h3>Now Playing</h3>
    <div class="nowplaying-wrap">
      <div class="cover-wrap">
        <img id="coverArt" alt="Album art">
        <div id="coverPlaceholder" class="cover-placeholder">♪</div>
      </div>

      <div class="np-meta">
        <div id="npText" class="value">Loading…</div>
        <div id="npAlbum" class="small"></div>

        <div class="vu-wrap">
          <div class="small">Level</div>

          <div class="vu-row">
            <div class="vu-label">L</div>
            <div class="vu-bar"><div id="vuLeft" class="vu-fill"></div></div>
            <div id="vuLeftVal" class="vu-value">0%</div>
          </div>

          <div class="vu-row">
            <div class="vu-label">R</div>
            <div class="vu-bar"><div id="vuRight" class="vu-fill"></div></div>
            <div id="vuRightVal" class="vu-value">0%</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    <h3>Everything</h3>
    <button onclick="grp('start','everything')">Start Everything</button>
    <button onclick="grp('stop','everything')">Stop Everything</button>
    <button onclick="grp('restart','everything')">Restart Everything</button>
    <div id="everything" class="value"></div>
  </div>

  <div class="card">
    <h3>Shuffle Player</h3>
    <button onclick="shuffleAll()">Shuffle All</button>
    <button onclick="nextTrack()">Next Track</button>
    <button onclick="prevTrack()">Previous Track</button>
  </div>

  <div class="card">
    <h3>Icecast</h3>
    <button onclick="act('start','icecast')">Start</button>
    <button onclick="act('stop','icecast')">Stop</button>
    <button onclick="act('restart','icecast')">Restart</button>
    <div id="icecast" class="value"></div>
  </div>

  <div class="card">
    <h3>Library</h3>
    <button onclick="updateLibrary()">Update Music Library</button>
    <button onclick="updateLibrary()">Clean Missing Tracks</button>
    <button disabled>Rebuild Database</button>

    <div class="small">Music root: <span id="musicRoot" class="muted"></span></div>
    <div class="small">Database: <span id="dbPath" class="muted"></span></div>
    <div class="small">Tracks indexed: <span id="trackCount" class="muted">—</span></div>

    <div id="libraryResult"></div>
  </div>

  <div class="card">
    <h3>Outputs</h3>

    <div class="output-block">
      <div><strong>Snapserver HD</strong></div>
      <button onclick="outputCtl('start','snapcast_hd')">Start</button>
      <button onclick="outputCtl('stop','snapcast_hd')">Stop</button>
      <button onclick="outputCtl('restart','snapcast_hd')">Restart</button>
      <div id="snapcastStatus" class="value">Checking…</div>
      <div id="snapcastDetail" class="small"></div>
      <div class="small" style="margin-top:8px;">
        <a class="link" href="https://github.com/judasshuffle/shuffle-player" target="_blank">
          Download Windows HD Player
        </a>
      </div>
    </div>

    <div class="output-block">
      <div><strong>MP3 Stream</strong></div>
      <button onclick="outputCtl('start','mp3_stream')">Start</button>
      <button onclick="outputCtl('stop','mp3_stream')">Stop</button>
      <button onclick="outputCtl('restart','mp3_stream')">Restart</button>
      <div id="mp3Status" class="value">Checking…</div>
      <div id="mp3Detail" class="small"></div>
    </div>
  </div>

  <div class="card">
    <h3>System</h3>
    <button onclick="systemCtl('restart_icecast')">Restart Icecast</button>
    <button onclick="systemCtl('reboot')">Reboot Pi</button>
    <button onclick="systemCtl('shutdown')">Shutdown Pi</button>
  </div>

  <div class="card">
    <a class="link" href="/index.html" target="_blank">Open Shufflizer</a>
  </div>

</div>

<script>
async function refreshStatus(){
  const r = await fetch('/api/status');
  const j = await r.json();

  for(const k in j){
    const el = document.getElementById(k);
    if(!el) continue;
    el.textContent = j[k] ? 'running' : 'stopped';
    el.className = 'value ' + (j[k] ? 'ok' : 'bad');
  }

  const all = !!j.icecast;
  const elAll = document.getElementById('everything');
  elAll.textContent = all ? 'running' : 'stopped';
  elAll.className = 'value ' + (all ? 'ok' : 'bad');
}

async function refreshNowPlaying(){
  const r = await fetch('/api/nowplaying');
  const j = await r.json();

  document.getElementById('npText').textContent = j.text || 'Nothing loaded';
  document.getElementById('npAlbum').textContent = j.album ? ('Album: ' + j.album) : '';

  const img = document.getElementById('coverArt');
  const placeholder = document.getElementById('coverPlaceholder');

  if(j.art_url){
    img.src = j.art_url + (j.art_url.includes('?') ? '&' : '?') + 't=' + Date.now();
    img.style.display = 'block';
    placeholder.style.display = 'none';
  } else {
    img.removeAttribute('src');
    img.style.display = 'none';
    placeholder.style.display = 'flex';
  }
}

async function refreshVu(){
  try {
    const r = await fetch('/api/vu');
    const j = await r.json();

    const l = Math.max(0, Math.min(100, j.left || 0));
    const rr = Math.max(0, Math.min(100, j.right || 0));

    document.getElementById('vuLeft').style.width = l + '%';
    document.getElementById('vuRight').style.width = rr + '%';
    document.getElementById('vuLeftVal').textContent = l + '%';
    document.getElementById('vuRightVal').textContent = rr + '%';
  } catch(e) {
    document.getElementById('vuLeft').style.width = '0%';
    document.getElementById('vuRight').style.width = '0%';
    document.getElementById('vuLeftVal').textContent = '0%';
    document.getElementById('vuRightVal').textContent = '0%';
  }
}

async function refreshLibraryStats(){
  const r = await fetch('/api/library/stats');
  const j = await r.json();

  document.getElementById('musicRoot').textContent = j.music_root || '';
  document.getElementById('dbPath').textContent = j.db_path || '';
  document.getElementById('trackCount').textContent =
    (j.track_count === null || j.track_count === undefined) ? '—' : j.track_count;
}

async function refreshOutputs(){
  const r = await fetch('/api/outputs');
  const j = await r.json();

  const mp3Status = document.getElementById('mp3Status');
  const mp3Detail = document.getElementById('mp3Detail');
  const snapStatus = document.getElementById('snapcastStatus');
  const snapDetail = document.getElementById('snapcastDetail');

  if(j.mp3_stream){
    mp3Status.textContent = 'RUNNING';
    mp3Status.className = 'value ok';
    mp3Detail.textContent = 'Icecast /stream.mp3 is live';
  } else {
    mp3Status.textContent = 'STOPPED';
    mp3Status.className = 'value bad';
    mp3Detail.textContent = 'Icecast /stream.mp3 not currently mounted';
  }

  if(j.snapcast_state === 'running'){
    snapStatus.textContent = 'RUNNING';
    snapStatus.className = 'value ok';
    snapDetail.textContent = 'snapserver + fifo feed running';
  } else if(j.snapcast_state === 'partial'){
    snapStatus.textContent = 'PARTIAL';
    snapStatus.className = 'value warn';
    snapDetail.textContent = 'snapserver and fifo feed are not both running';
  } else {
    snapStatus.textContent = 'STOPPED';
    snapStatus.className = 'value bad';
    snapDetail.textContent = 'snapserver + fifo feed stopped';
  }
}

async function refreshAll(){
  await refreshStatus();
  await refreshNowPlaying();
  await refreshLibraryStats();
  await refreshOutputs();
}

async function act(action,key){
  await fetch('/api/' + action + '/' + key);
  refreshStatus();
}

async function grp(action,group){
  await fetch('/api/group/' + action + '/' + group);
  refreshStatus();
}

async function outputCtl(action, output){
  const r = await fetch('/api/output/' + action + '/' + output, {method:'POST'});
  const j = await r.json();

  if(!j.ok){
    alert('Output control failed: ' + (j.error || 'Unknown error'));
  }

  await refreshOutputs();
  await refreshStatus();
}

async function shuffleAll(){
  await fetch('/control/shuffle', {method:'POST'});
}

async function nextTrack(){
  await fetch('/control/next', {method:'POST'});
}

async function prevTrack(){
  await fetch('/control/prev', {method:'POST'});
}

async function updateLibrary(){
  const out = document.getElementById('libraryResult');
  out.textContent = 'Running library update…';

  const r = await fetch('/api/library/resync', {method:'POST'});
  const j = await r.json();

  out.textContent = j.ok ? j.output : ('Error: ' + (j.error || 'Unknown error'));
  await refreshLibraryStats();
}

async function systemCtl(action){
  if(action === 'restart_icecast'){
    const r = await fetch('/api/system/restart-icecast', {method:'POST'});
    const j = await r.json();
    if(!j.ok){
      alert('Restart Icecast failed');
    }
    await refreshStatus();
    return;
  }

  if(action === 'reboot'){
    if(confirm('Reboot the Raspberry Pi?')){
      await fetch('/api/system/reboot', {method:'POST'});
    }
    return;
  }

  if(action === 'shutdown'){
    if(confirm('Shutdown the Raspberry Pi now?')){
      await fetch('/api/system/shutdown', {method:'POST'});
    }
  }
}

refreshAll();
setInterval(refreshAll, 3000);
setInterval(refreshVu, 250);
</script>
</body>
</html>
"""


class Handler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        u = urlparse(self.path)

        try:
            if u.path == "/control/next":
                mpv_command(["playlist-next", "force"])
                return self._json({"ok": True})

            if u.path == "/control/prev":
                mpv_command(["playlist-prev", "force"])
                return self._json({"ok": True})

            if u.path == "/control/shuffle":
                mpv_command(["playlist-shuffle"])
                return self._json({"ok": True})

            if u.path == "/api/library/resync":
                if not os.path.exists(RESYNC_SCRIPT):
                    return self._json({"ok": False, "error": f"Script not found: {RESYNC_SCRIPT}"}, 500)

                r = run([RESYNC_SCRIPT])
                ok = (r.returncode == 0)
                text = (r.stdout or "").strip()
                err = (r.stderr or "").strip()

                if ok:
                    return self._json({"ok": True, "output": text or "Library update complete."})

                return self._json({"ok": False, "error": err or text or "Library update failed."}, 500)

            if u.path == "/api/system/restart-icecast":
                r = run(["sudo", "systemctl", "restart", "icecast2.service"])
                return self._json({"ok": r.returncode == 0})

            if u.path == "/api/system/reboot":
                run(["sudo", "reboot"])
                return self._json({"ok": True})

            if u.path == "/api/system/shutdown":
                run(["sudo", "shutdown", "-h", "now"])
                return self._json({"ok": True})

            if u.path.startswith("/api/output/"):
                parts = u.path.strip("/").split("/")
                if len(parts) != 4:
                    return self._json({"ok": False, "error": "bad output path"}, 400)

                _, _, action, output_name = parts
                result = control_output(output_name, action)
                return self._json(result, 200 if result.get("ok") else 500)

        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)

        return self.send_error(404)

    def do_GET(self):
        u = urlparse(self.path)

        if u.path == "/api/status":
            status = {k: is_active(v) for k, v in SERVICES.items()}
            return self._json(status)

        if u.path == "/api/outputs":
            return self._json(get_output_status())

        if u.path == "/api/nowplaying":
            return self._json(read_nowplaying())

        if u.path == "/api/vu":
            return self._json(get_vu_levels())

        if u.path == "/api/library/stats":
            return self._json(get_library_stats())

        if u.path.startswith("/api/") and not u.path.startswith("/api/group/") and not u.path.startswith("/api/output/"):
            parts = u.path.strip("/").split("/")

            if len(parts) != 3:
                return self._json({"error": "bad path"}, 400)

            _, action, key = parts

            if key not in SERVICES:
                return self._json({"error": "bad key"}, 400)

            if action not in ("start", "stop", "restart"):
                return self._json({"error": "bad action"}, 400)

            svc = SERVICES[key]
            r = run(["sudo", "systemctl", action, svc])

            return self._json({"ok": r.returncode == 0, "active": is_active(svc)})

        if u.path.startswith("/api/group/"):
            parts = u.path.strip("/").split("/")

            if len(parts) != 4:
                return self._json({"error": "bad group path"}, 400)

            _, _, action, group = parts

            if group not in GROUPS:
                return self._json({"error": "bad group"}, 400)

            if action not in ("start", "stop", "restart"):
                return self._json({"error": "bad action"}, 400)

            ok = True

            for key in GROUPS[group]:
                svc = SERVICES[key]
                r = run(["sudo", "systemctl", action, svc])
                if r.returncode != 0:
                    ok = False

            return self._json({"ok": ok, "group": group}, 200 if ok else 500)

        if u.path == "/" or u.path == "/control":
            data = DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        return super().do_GET()


if __name__ == "__main__":
    os.chdir(ROOT)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()