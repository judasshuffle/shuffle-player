#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import json, os, subprocess

ROOT = "/home/dan/shuffle-player/web/public"
PORT = 8090

SERVICES = {
    "icecast": "icecast2.service",
    "radio": "shuffle-radio.service",
    "player": "shuffle-player.service",
}

GROUPS = {
    "everything": ["icecast", "radio", "player"],
}

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def is_active(service):
    r = run(["systemctl", "is-active", service])
    return (r.returncode == 0) and (r.stdout.strip() == "active")

class Handler(SimpleHTTPRequestHandler):
    def _json(self, obj, code=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)

        if u.path == "/api/cmd/shuffle":
            try:
                fifo = "/tmp/shuffle_cmd.fifo"
                msg = "shuffle all\n".encode("utf-8")

                fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
                try:
                    os.write(fd, msg)
                finally:
                    os.close(fd)
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)


        if u.path == "/api/status":
            status = {k: is_active(v) for k, v in SERVICES.items()}
            return self._json(status)

        if u.path.startswith("/api/") and not u.path.startswith("/api/group/"):
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

        if u.path == "/" or u.path == "/index.html":
            html = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Shuffle Control</title>
<style>
body{font-family:system-ui;margin:20px}
button{padding:10px;margin:5px}
.ok{color:green}
.bad{color:red}
</style>
</head>
<body>
<h2>Shuffle Control</h2>

<h3>Everything</h3>
<button onclick="grp('start','everything')">Start Everything</button>
<button onclick="grp('stop','everything')">Stop Everything</button>
<button onclick="grp('restart','everything')">Restart Everything</button>
<span id="everything"></span>

<hr>

<h3>Shuffle Player</h3>
<button onclick="cmdShuffle()">Shuffle All</button>

<button onclick="act('start','player')">Start</button>
<button onclick="act('stop','player')">Stop</button>
<button onclick="act('restart','player')">Restart</button>
<span id="player"></span>

<h3>Icecast</h3>
<button onclick="act('start','icecast')">Start</button>
<button onclick="act('stop','icecast')">Stop</button>
<button onclick="act('restart','icecast')">Restart</button>
<span id="icecast"></span>

<h3>Radio Encoder</h3>
<button onclick="act('start','radio')">Start</button>
<button onclick="act('stop','radio')">Stop</button>
<button onclick="act('restart','radio')">Restart</button>
<span id="radio"></span>

<hr>
<a href="/shufflizer/" target="_blank">Open Shufflizer</a>

<script>
async function refresh(){
  const r = await fetch('/api/status');
  const j = await r.json();

  for (const k in j){
    const el = document.getElementById(k);
    el.textContent = j[k] ? ' running' : ' stopped';
    el.className = j[k] ? 'ok' : 'bad';
  }

  const all = (j.icecast && j.radio && j.player);
  const elAll = document.getElementById('everything');
  elAll.textContent = all ? ' running' : ' stopped';
  elAll.className = all ? 'ok' : 'bad';
}

async function act(action,key){
  await fetch('/api/'+action+'/'+key);
  refresh();
}

async function cmdShuffle(){
  await fetch('/api/cmd/shuffle');
  refresh();
}

async function grp(action,group){
  await fetch('/api/group/'+action+'/'+group);
  refresh();
}

refresh();
setInterval(refresh,3000);
</script>

</body>
</html>
"""
            data = html.encode()
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
