"""Isolated synthetic preview. No database, scanner, service or IPC access."""
import io
import json
import math
from pathlib import Path
import sqlite3
import struct
import subprocess
import threading
import urllib.request
import wave
from urllib.parse import urlparse

import control_server as dashboard
from library_setup import SetupDemo

setup_demo = None
setup_lock = threading.Lock()

def forbidden(*args, **kwargs):
    raise RuntimeError("Production interfaces are disabled in this preview")


# Defense in depth: never allow the imported production handlers to execute I/O.
sqlite3.connect = forbidden
subprocess.run = forbidden
subprocess.Popen = forbidden
urllib.request.urlopen = forbidden
urllib.request.OpenerDirector.open = forbidden
dashboard.mpv_command = forbidden
dashboard.run = forbidden
dashboard.ROOT = "/app/visualizer"

services = {service: True for service in dashboard.SERVICES.values()}
track = 1


def nowplaying():
    return {"artist": "Preview Synth", "title": f"Synthetic Track {track}",
            "album": "Local Test Data", "text": f"Preview Synth â€” Synthetic Track {track}",
            "art_url": "/preview-cover.svg", "ts": track}


def outputs():
    snap = services["snapserver.service"]
    feed = services["shuffle-snapfifo-feed.service"]
    return {"mp3_stream": services["shuffle-radio.service"], "snapserver": snap,
            "snapfifo_feed": feed,
            "snapcast_state": "running" if snap and feed else "partial" if snap or feed else "stopped"}


buffer = io.BytesIO()
with wave.open(buffer, "wb") as audio:
    audio.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
    audio.writeframes(b"".join(struct.pack("<h", int(10000 * math.sin(2 * math.pi * 220 * n / 22050)
                       * (0.35 + 0.65 * max(0, math.sin(2 * math.pi * 2 * n / 22050))))
                       if n % (22050 * 4) < 22050 * 3 else 0)
                       for n in range(22050 * 12)))
tone = buffer.getvalue()


class PreviewHandler(dashboard.Handler):
    def end_headers(self):
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                         "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
                         "media-src 'self'; frame-src 'self'")
        super().end_headers()

    def content(self, data, content_type):
        if isinstance(data, str):
            data = data.encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/setup":
            return self.content(Path(__file__).with_name("setup.html").read_text(encoding="utf-8"),
                                "text/html; charset=utf-8")
        if path in ("/api/nowplaying", "/nowplaying.json"):
            return self._json(nowplaying())
        if path == "/voice_last.json":
            return self._json({})
        if path == "/api/status":
            return self._json({key: services[value] for key, value in dashboard.SERVICES.items()})
        if path == "/api/outputs":
            return self._json(outputs())
        if path == "/api/library/stats":
            return self._json({"track_count": 3, "db_path": "Preview fixture â€” no database",
                               "music_root": "Synthetic audio â€” no library mounted"})
        if path == "/preview-tone.wav":
            return self.content(tone, "audio/wav")
        if path == "/preview-cover.svg":
            return self.content('<svg xmlns="http://www.w3.org/2000/svg" width="280" height="280">'
                                '<rect width="280" height="280" fill="#192c30"/>'
                                '<circle cx="140" cy="120" r="70" fill="#00aa66"/>'
                                '<text x="140" y="235" text-anchor="middle" fill="white" '
                                'font-family="sans-serif">PREVIEW SYNTH</text></svg>', "image/svg+xml")
        if path == "/js/main.js":
            text = Path(dashboard.ROOT, "js/main.js").read_text()
            start = text.index("// Use the page host")
            end = text.index("const ui = initUI();")
            text = text[:start] + 'audioEl.src = "/preview-tone.wav"; audioEl.loop = true; audioEl.load();\n' + text[end:]
            return self.content(text, "text/javascript")
        if path == "/index.html":
            text = Path(dashboard.ROOT, "index.html").read_text().replace(
                "http://192.168.68.57:8001/stream.mp3", "/preview-tone.wav")
            return self.content(text, "text/html; charset=utf-8")
        if path.startswith("/api/group/") or (path.startswith("/api/") and len(path.split("/")) == 4):
            return self.mock_control(path)
        if path.startswith("/api/"):
            return self.send_error(404)
        if path in ("/", "/control"):
            description = "Audio and library information are synthetic. The tone pulses twice per second, with a quiet gap every four seconds."
            html = dashboard.DASHBOARD_HTML.replace('<h1>Shuffle Control</h1>',
                '<h1>Shuffle Control Â· Local Preview</h1><p>All controls are simulated. '
                + description + '</p><p><a href="/setup">Connect your music library — safe demo</a></p>')
            return self.content(html, "text/html; charset=utf-8")
        return super().do_GET()

    def mock_control(self, path):
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[1] in ("start", "stop", "restart") and parts[2] in dashboard.SERVICES:
            services[dashboard.SERVICES[parts[2]]] = parts[1] != "stop"
        elif len(parts) == 4 and parts[1] == "group" and parts[3] in dashboard.GROUPS:
            for key in dashboard.GROUPS[parts[3]]:
                services[dashboard.SERVICES[key]] = parts[2] != "stop"
        elif len(parts) == 4 and parts[1] == "output":
            names = ["shuffle-radio.service"] if parts[3] == "mp3_stream" else ["snapserver.service", "shuffle-snapfifo-feed.service"]
            for name in names:
                services[name] = parts[2] != "stop"
        else:
            return self.send_error(404)
        return self._json({"ok": True, "simulated": True})

    def do_POST(self):
        global track, setup_demo
        path = urlparse(self.path).path
        if path in ("/api/setup/validate", "/api/setup/confirm"):
            if self.headers.get("Content-Type") != "application/json":
                return self._json({"ok": False, "error": "JSON required"}, 415)
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host"):
                return self._json({"ok": False, "error": "Same-origin request required"}, 403)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError("Invalid request length")
                request = json.loads(self.rfile.read(length))
                if not isinstance(request, dict):
                    raise ValueError("Expected object")
                with setup_lock:
                    if setup_demo is None:
                        setup_demo = SetupDemo()
                    result = setup_demo.validate(request) if path.endswith("validate") else setup_demo.confirm(request)
                return self._json(result)
            except (ValueError, TypeError):
                return self._json({"ok": False, "error": "Invalid setup request"}, 400)
        if path == "/api/library/resync":
            return self._json({"ok": True, "output": "Preview only: no scan executed; 3 synthetic tracks unchanged."})
        if path in ("/control/next", "/control/prev", "/control/shuffle"):
            track = (track % 3 + 1) if path != "/control/prev" else ((track - 2) % 3 + 1)
            return self._json({"ok": True, "simulated": True})
        if path.startswith("/api/system/"):
            return self._json({"ok": True, "simulated": True})
        return self.mock_control(path)


if __name__ == "__main__":
    dashboard.ThreadingHTTPServer(("0.0.0.0", 8092), PreviewHandler).serve_forever()
