import hashlib
import http.client
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import wave

PROJECT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, PROJECT / "synology" / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = load("synology_server", "server.py")
fixtures = load("synology_fixtures", "fixtures.py")


class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.db, self.music = root / "data/jukebox.db", root / "music"
        fixtures.generate(self.music, self.db)
        self.before = self.snapshot()
        self.library = server.Library(self.db, self.music)
        handler = type("TestHandler", (server.Handler,), dict(
            library=self.library, visuals=PROJECT / "web/shufflizer"))
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def snapshot(self):
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in Path(self.temp.name).rglob("*") if p.is_file()}

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()
        self.assertEqual(self.before, self.snapshot(), "Player modified library or index")

    def request(self, path, method="GET", headers=None):
        client = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=5)
        client.request(method, path, headers=headers or {})
        response = client.getresponse()
        data = response.read()
        result = response.status, dict(response.getheaders()), data
        client.close()
        return result

    def test_search_and_sql_values(self):
        result = json.loads(self.request("/api/search?q=Copper")[2])
        self.assertEqual(len(result["tracks"]), 1)
        self.assertEqual(result["tracks"][0]["title"], "Copper Pulse")
        self.assertTrue(result["tracks"][0]["available"])
        self.assertEqual(self.library.search("%")['tracks'], [])
        self.assertEqual(self.library.search("' OR 1=1 --")['tracks'], [])
        self.assertEqual(self.request('/api/search?offset=-1')[0], 400)

    def test_missing_track_retained_and_routes_disabled(self):
        tracks = self.library.search()['tracks']
        self.assertEqual(len(tracks), 10)
        missing = next(t for t in tracks if not t['available'])
        self.assertEqual(self.request('/media/' + str(missing['id']))[0], 404)
        for route in ('/api/library/resync', '/api/system/reboot'):
            self.assertEqual(self.request(route, 'POST')[0], 405)
        self.assertEqual(len(self.library.search()['tracks']), 10)

    def test_decade_artist_commands_and_unknown_years(self):
        result = self.library.search('play 70s Bob Dylan')
        self.assertEqual({t['title'] for t in result['tracks']}, {'Demo 1970', 'Demo 1979'})
        self.assertEqual(result['decade'], 1970)
        self.assertEqual(result['unknown_years_excluded'], 1)
        self.assertEqual(self.library.search('queue 1970s Bob Dylan')['tracks'], result['tracks'])
        self.assertIn('no usable', self.library.search('play 70s Undated Artist')['error'])
        self.assertEqual(self.library.search('play 70s Nonexistent Artist')['tracks'], [])

    def test_shuffle_reads_index_and_retains_unavailable(self):
        result = self.library.shuffle_batch()
        self.assertEqual(len(result['tracks']), 10)
        self.assertEqual(sum(t['available'] for t in result['tracks']), 9)
        self.assertFalse(result['has_more'])
        self.assertEqual(self.request('/api/shuffle')[0], 200)

    def test_missing_year_column_fails_without_schema_changes(self):
        # A second, newly created temporary database deliberately lacks year data.
        database = Path(self.temp.name) / 'no-years.db'
        con = server.sqlite3.connect(database)
        con.execute('CREATE TABLE tracks(path TEXT,artist TEXT,album TEXT,title TEXT)')
        con.commit(); con.close()
        try:
            library = server.Library(database, self.music)
            self.assertIn('no year column', library.search('play 70s Bob Dylan')['error'])
            self.assertEqual(library.search('Bob Dylan')['tracks'], [])
        finally:
            database.unlink()

    def test_shuffle_paginates_without_dropping_tracks(self):
        database = Path(self.temp.name) / 'many.db'
        con = server.sqlite3.connect(database)
        con.execute('CREATE TABLE tracks(path TEXT,artist TEXT,album TEXT,title TEXT)')
        con.executemany('INSERT INTO tracks VALUES(?,?,?,?)',
            [('/mnt/lossless/Copper Pulse.wav', 'Demo', 'Many', str(i)) for i in range(550)])
        con.commit(); con.close()
        try:
            library = server.Library(database, self.music)
            first = library.shuffle_batch()
            second = library.shuffle_batch(first['after'])
            self.assertTrue(first['has_more'])
            self.assertFalse(second['has_more'])
            ids = [track['id'] for track in first['tracks'] + second['tracks']]
            self.assertEqual(len(set(ids)), 550)
        finally:
            database.unlink()

    def test_browser_audio_and_seek(self):
        ident = self.library.search('Copper')['tracks'][0]['id']
        route = '/media/' + str(ident)
        status, headers, data = self.request(route)
        self.assertEqual(status, 200)
        with wave.open(io.BytesIO(data)) as wav:
            self.assertEqual(wav.getnframes(), 22050 * 16)
        status, headers, partial = self.request(route, headers={'Range': 'bytes=10-99'})
        self.assertEqual(status, 206)
        self.assertEqual(partial, data[10:100])
        self.assertTrue(headers['Content-Range'].startswith('bytes 10-99/'))
        self.assertEqual(self.request(route, headers={'Range': 'bytes=-16'})[2], data[-16:])
        self.assertEqual(self.request(route, headers={'Range': 'bytes=99999999-'})[0], 416)
        self.assertEqual(self.request(route, 'HEAD')[2], b'')

    def test_visualizer_and_shared_audio(self):
        self.assertIn(b'embedded', self.request('/visualizer/index.html?embed=1')[2])
        script = self.request('/visualizer/js/main.js')[2].decode()
        self.assertIn('window.parent.playerAudio', script)
        self.assertIn('startEngine(canvas, audio.analyser, ui.state)', script)
        self.assertNotIn('192.168.', script)
        self.assertNotIn('voice_last.json', script)
        for path in ('/', '/app.js', '/visualizer/js/engine.js', '/visualizer/css/style.css'):
            self.assertEqual(self.request(path)[0], 200)

    def test_path_escape_rejected(self):
        for path in ('/etc/passwd', '/mnt/lossless/../secret.wav', '/mnt/lossless-other/test.wav'):
            with self.assertRaises(ValueError):
                self.library.resolve(path)
        self.assertEqual(self.request('/media/99999999999999999999999')[0], 404)


if __name__ == '__main__':
    unittest.main()
