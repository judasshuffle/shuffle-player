#!/usr/bin/env python3

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import json
import os
import subprocess
import socket

ROOT = "/home/dan/shuffle-player/web/shufflizer"
PORT = 8091
MPV_SOCKET = "/tmp/radio_mpv.sock"
NOWPLAYING_JSON = "/home/dan/shuffle-player/web/shufflizer/nowplaying.json"
RESYNC_SCRIPT = "/home/dan/shuffle-player/scripts/resync_jukebox_db.sh"

SERVICES = {
    "icecast": "icecast2.service",
    "mp3_stream": "shuffle-radio.service",
    "snapserver": "snapserver.service",
    "snapfifo_feed": "shuffle-snapfifo-feed.service",
}

GROUPS = {
    "everything": ["icecast"],
}


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def is_active(service):
    r = run(["sudo", "systemctl", "is-active", service])
    return (r.returncode == 0) and (r.stdout.strip() == "active")


def get_output_status():
    mp3_on = is_active("shuffle-radio.service")
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
        return {"artist": "", "title": "", "album": "", "text": "Nothing loaded"}

    try:
        with open(NOWPLAYING_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {"artist": "", "title": "", "album": "", "text": f"Now playing read error: {e}"}

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
</style>
</head>

<body>
<h1>Shuffle Control</h1>

<div class="grid">

  <div class="card card-wide">
    <h3>Now Playing</h3>
    <div id="npText" class="value">Loading…</div>
    <div id="npAlbum" class="small"></div>
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
    <button>Restart Icecast</button>
    <button>Reboot Pi</button>
    <button>Shutdown Pi</button>
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
    mp3Detail.textContent = 'shuffle-radio.service running';
  } else {
    mp3Status.textContent = 'STOPPED';
    mp3Status.className = 'value bad';
    mp3Detail.textContent = 'shuffle-radio.service stopped';
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
  await fetch('/api/'+action+'/'+key);
  refreshStatus();
}

async function grp(action,group){
  await fetch('/api/group/'+action+'/'+group);
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
  await fetch('/control/shuffle',{method:'POST'});
}

async function nextTrack(){
  await fetch('/control/next',{method:'POST'});
}

async function prevTrack(){
  await fetch('/control/prev',{method:'POST'});
}

async function updateLibrary(){
  const out = document.getElementById('libraryResult');
  out.textContent = 'Running library update…';

  const r = await fetch('/api/library/resync', {method:'POST'});
  const j = await r.json();

  out.textContent = j.ok ? j.output : ('Error: ' + (j.error || 'Unknown error'));
  await refreshLibraryStats();
}

refreshAll();
setInterval(refreshAll, 3000);
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