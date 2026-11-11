"""Local-only real station for the browser EOF regression."""
import sys, tempfile, pathlib, sqlite3, wave, math, struct, threading, json
from contextlib import closing
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'synology'))
import server
from radio import LibraryRadio

with tempfile.TemporaryDirectory() as directory:
    rolling = '--rolling' in sys.argv
    tones = [(i, 220+i*220, 2) for i in range(1,7)] if rolling else [(1,440,3),(2,880,30)]
    root = pathlib.Path(directory)
    music = root / 'music'
    music.mkdir()
    db = root / 'jukebox.db'
    with closing(sqlite3.connect(db)) as con:
        con.execute('CREATE TABLE tracks(path TEXT, artist TEXT, album TEXT, title TEXT, duration REAL)')
        for ident, frequency, duration in tones:
            path = music / f'{ident}.wav'
            with wave.open(str(path), 'wb') as output:
                output.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
                output.writeframes(b''.join(struct.pack('<h', int(7000*math.sin(2*math.pi*frequency*i/44100))) for i in range(duration*44100)))
            con.execute('INSERT INTO tracks VALUES(?,?,?,?,?)', ('/mnt/lossless/'+path.name, f'Artist {ident}', f'Album {ident}', str(ident), duration))
        con.commit()
    class Handler(server.Handler):
        visuals = pathlib.Path(__file__).resolve().parents[1] / 'web/shufflizer'
        library = server.Library(db, music)
        radio = LibraryRadio(library, target_seconds=4 if rolling else 3600)
        armed = True
        def log_message(self, *args): pass
        def do_GET(self):
            if self.path == '/stream.mp3' and type(self).armed:
                type(self).armed = False
                self.radio.control('toggle', {})
            if self.path == '/test-state':
                body = json.dumps({**self.radio.snapshot(), 'completed':len(self.radio.recent)}).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
            elif self.path == '/test-toggle':
                self.radio.control('toggle', {})
                self.send_response(204); self.end_headers()
            else: super().do_GET()
    # Include known lengths as real tagged files do, exercising clock and EOF.
    if not rolling: Handler.radio.control('replace', {'ids':[1,2]})
    Handler.radio.control('toggle', {})  # Start the short track when Edge joins.
    httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    print(httpd.server_port, flush=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try: sys.stdin.readline()
    finally:
        Handler.radio.close()
        httpd.shutdown()
        httpd.server_close()
        thread.join()
