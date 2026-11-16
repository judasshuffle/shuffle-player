"""Local Echo Loom /dr-screen preview with synthetic audio only."""
import io
import json
import math
import pathlib
import struct
import wave
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse


ROOT = pathlib.Path(__file__).resolve().parents[1]
VISUALS = ROOT / "web" / "shufflizer"
DR_SCREEN = ROOT / "synology" / "dr-screen.html"
DR_SCRIPT = ROOT / "synology" / "dr-screen.js"


def make_tone():
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        frames = []
        for sample in range(22050 * 60):
            seconds = sample / 22050
            pulse = max(0.0, math.sin(seconds * math.pi * 2 * 1.8))
            frequency = 180 + 420 * max(0.0, math.sin(seconds * math.pi * 2 * 0.22))
            level = 0.10 + 0.65 * pulse
            frames.append(struct.pack("<h", int(15000 * level * math.sin(seconds * frequency * math.pi * 2))))
        audio.writeframes(b"".join(frames))
    return output.getvalue()


TONE = make_tone()


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def send_bytes(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/dr-screen", "/dr-screen/"):
            return self.send_bytes(DR_SCREEN.read_bytes(), "text/html; charset=utf-8")
        if path == "/dr-screen.js":
            return self.send_bytes(DR_SCRIPT.read_bytes(), "text/javascript")
        if path == "/stream.mp3":
            return self.send_bytes(TONE, "audio/wav")
        if path == "/api/station":
            body = {"version": 1, "playing": True, "current": {"id": 1},
                    "visualizer": {"bank": "VLM", "preset": "Echo Loom"},
                    "queue_count": 1, "position": 0, "can_control": False}
            return self.send_bytes(json.dumps(body).encode(), "application/json")
        if path in ("/api/nowplaying", "/nowplaying.json"):
            return self.send_bytes(json.dumps({"artist": "Preview Synth", "title": "Echo Loom Test"}).encode(),
                                   "application/json")
        if path in ("/voice_last.json", "/visualizer/voice_last.json"):
            return self.send_bytes(b"{}", "application/json")
        if path == "/visualizer/index.html":
            text = (VISUALS / "index.html").read_text(encoding="utf-8")
            text = text.replace('src="/js/main.js"', 'src="/visualizer/js/main.js"')
            text = text.replace('src="http://192.168.68.57:8001/stream.mp3"', '')
            text = text.replace("</head>", '<style>#audio,.audio-options{display:none!important}</style></head>')
            return self.send_bytes(text.encode(), "text/html; charset=utf-8")
        if path == "/visualizer/js/main.js":
            text = (VISUALS / "js" / "main.js").read_text(encoding="utf-8")
            start = text.index("// Use the page host")
            end = text.index("const ui = initUI();", start)
            text = text[:start] + text[end:]
            text = text.replace('const audioEl = document.getElementById("audio");',
                                'const audioEl = window.parent.document.getElementById("player");')
            text = text.replace('const audio = initAudio(audioEl, { startMuted: ui.state.muted });',
                                'ui.els.muted.checked = false; ui.state.muted = false; const audio = window.parent.playerAudio;')
            return self.send_bytes(text.encode(), "text/javascript")
        if path.startswith("/visualizer/"):
            asset = (VISUALS / path.removeprefix("/visualizer/")).resolve()
            if asset.is_relative_to(VISUALS.resolve()) and asset.is_file():
                content_type = "text/javascript" if asset.suffix == ".js" else "text/css"
                return self.send_bytes(asset.read_bytes(), content_type)
        return super().do_GET()


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8093), Handler).serve_forever()
