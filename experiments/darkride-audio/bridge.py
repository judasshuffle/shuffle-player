"""Live Icecast -> bounded in-memory WAV chunks; localhost only, no Pi writes."""
import argparse
import collections
import io
import json
import pathlib
import subprocess
import threading
import time
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

SOURCE = 'http://shuffle.tplinkdns.com:8001/stream.mp3'
ROOT = pathlib.Path(__file__).parent
RATE, SECONDS, KEEP = 24000, 2, 12


class Live:
    def __init__(self):
        self.lock = threading.Lock()
        self.chunks = collections.OrderedDict()
        self.session = uuid.uuid4().hex
        self.seq = 0
        self.last = 0
        self.restarts = 0
        self.started = time.time()
        self.stop = threading.Event()
        self.process = None

    def publish(self, pcm):
        out = io.BytesIO()
        with wave.open(out, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm)
        with self.lock:
            self.seq += 1
            self.chunks[self.seq] = out.getvalue()
            self.last = time.time()
            while len(self.chunks) > KEEP:
                self.chunks.popitem(last=False)
        print(json.dumps({'chunk': self.seq, 'bytes': len(pcm), 'at': self.last}), flush=True)

    def receive(self, ffmpeg):
        args = [ffmpeg, '-nostdin', '-nostats', '-hide_banner', '-loglevel', 'info',
                '-rw_timeout', '10000000', '-re', '-i', SOURCE,
                '-vn', '-ac', '1', '-ar', str(RATE), '-f', 's16le', 'pipe:1']
        while not self.stop.is_set():
            try:
                self.process = subprocess.Popen(args, stdout=subprocess.PIPE,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                buf = bytearray()
                while not self.stop.is_set():
                    part = self.process.stdout.read(RATE * 2 * SECONDS - len(buf))
                    if not part:
                        break
                    buf.extend(part)
                    if len(buf) == RATE * 2 * SECONDS:
                        self.publish(bytes(buf))
                        buf.clear()
            except OSError as e:
                print(str(e), flush=True)
            finally:
                if self.process:
                    if self.process.poll() is None:
                        self.process.terminate()
                    self.process.wait()
                    if self.process.stdout:
                        self.process.stdout.close()
            with self.lock:
                self.chunks.clear()
                self.restarts += 1
            self.stop.wait(2)


def handler(live):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            path = urlsplit(self.path).path
            body, kind, code = b'', 'application/json', 200
            with live.lock:
                if path == '/manifest.json':
                    body = json.dumps({'session': live.session, 'seconds': SECONDS,
                        'ids': list(live.chunks), 'age': time.time() - live.last,
                        'restarts': live.restarts, 'uptime': time.time() - live.started}).encode()
                elif path.startswith('/chunk/' + live.session + '/') and path.endswith('.wav'):
                    try:
                        body = live.chunks.get(int(path.rsplit('/', 1)[1][:-4]), b'')
                    except ValueError:
                        pass
                    kind = 'audio/wav'
                    code = 200 if body else 404
                elif path == '/speaker.js':
                    body = (ROOT / 'speaker.js').read_bytes()
                    kind = 'application/javascript'
                else:
                    code = 404
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
    return Handler


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--ffmpeg')
    p.add_argument('--port', type=int, default=18791)
    p.add_argument('--run-seconds', type=int, default=0)
    opts = p.parse_args()
    binaries = list((ROOT / '.runtime/imageio_ffmpeg/binaries').glob('ffmpeg*.exe'))
    ffmpeg = opts.ffmpeg or (str(binaries[0]) if binaries else 'ffmpeg')
    live = Live()
    server = ThreadingHTTPServer(('127.0.0.1', opts.port), handler(live))
    worker = threading.Thread(target=live.receive, args=(ffmpeg,), daemon=True)
    worker.start()
    if opts.run_seconds:
        threading.Timer(opts.run_seconds, server.shutdown).start()
    print('Bridge: http://127.0.0.1:%d/speaker.js' % opts.port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        live.stop.set()
        if live.process and live.process.poll() is None:
            live.process.terminate()
        worker.join(timeout=12)
        server.server_close()


if __name__ == '__main__':
    main()
