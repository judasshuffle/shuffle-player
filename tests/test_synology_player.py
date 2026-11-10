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
import shutil
import time

PROJECT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, PROJECT / "synology" / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = load("synology_server", "server.py")
radio_module = load('synology_radio', 'radio.py')
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
        self.playback_temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.playback_temp.cleanup)
        handler = type("TestHandler", (server.Handler,), dict(
            library=self.library, visuals=PROJECT / "web/shufflizer",
            mp3_cache=server.Mp3Cache(self.playback_temp.name),
            radio=radio_module.LibraryRadio(self.library)))
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def snapshot(self):
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in Path(self.temp.name).rglob("*") if p.is_file()}

    def tearDown(self):
        self.httpd.RequestHandlerClass.radio.close()
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

    def test_shared_station_queue_clock_and_lan_authorization(self):
        handler = self.httpd.RequestHandlerClass
        radio = handler.radio
        state = radio.control('replace', {'ids':[1,2]})
        self.assertEqual(state['current']['id'], 1)
        self.assertEqual(state['queue_count'], 2)
        time.sleep(.08)
        self.assertGreater(radio.snapshot()['position'], state['position'])
        paused = radio.control('toggle', {})
        time.sleep(.08)
        self.assertAlmostEqual(radio.snapshot()['position'], paused['position'], places=3)
        radio.control('append', {'ids':[3]})
        self.assertFalse(radio.snapshot()['playing'])
        self.assertEqual(radio.snapshot()['queue_count'], 3)
        radio.control('seek', {'position':3})
        self.assertEqual(radio.snapshot()['position'], 3)
        self.assertEqual(radio.control('next', {})['current']['id'], 2)
        self.assertEqual(radio.control('remove', {'index':0})['current']['id'], 2)
        with self.assertRaises(ValueError): radio.control('replace', {'ids':[999999]})
        self.assertEqual(radio.snapshot()['current']['id'], 2)

        def post(token='', origin=None):
            client = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
            headers = {'Content-Type':'application/json', 'X-Shuffle-Control':token}
            if origin: headers['Origin'] = origin
            client.request('POST', '/api/station/control', json.dumps({'action':'replace','ids':[1,3]}), headers)
            response = client.getresponse(); data = response.read(); client.close()
            return response.status, data
        self.assertNotIn('control_token', json.loads(self.request('/api/station')[2]))
        self.assertEqual(post(handler.control_token)[0], 403, 'Public listener port cannot control even with a token')
        handler.control_access = True
        try:
            token = json.loads(self.request('/api/station')[2])['control_token']
            self.assertEqual(post()[0], 403)
            self.assertEqual(post(token, 'http://hostile.example')[0], 403)
            status, data = post(token)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(data)['current']['id'], 1)
        finally: handler.control_access = False

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')
    def test_station_controls_keep_existing_stream_connection(self):
        radio = self.httpd.RequestHandlerClass.radio
        radio.control('replace', {'ids':[1,2]})
        client = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=10)
        client.request('GET', '/stream.mp3')
        response = client.getresponse()
        try:
            self.assertEqual(len(response.read(4096)), 4096)
            radio.control('toggle', {})
            self.assertFalse(radio.snapshot()['playing'])
            self.assertEqual(len(response.read(4096)), 4096, 'Pause emits silence without closing Webamp stream')
            radio.control('next', {})
            self.assertEqual(radio.snapshot()['current']['id'], 2)
            self.assertEqual(len(response.read(8192)), 8192, 'Skip keeps the same HTTP stream alive')
        finally: client.close()

    def test_missing_track_retained_and_routes_disabled(self):
        tracks = self.library.search()['tracks']
        self.assertEqual(len(tracks), 10)
        missing = next(t for t in tracks if not t['available'])
        self.assertEqual(self.request('/media/' + str(missing['id']))[0], 404)
        for route in ('/api/library/resync', '/api/system/reboot'):
            self.assertEqual(self.request(route, 'POST')[0], 405)
        self.assertEqual(len(self.library.search()['tracks']), 10)

    def test_decade_artist_commands_and_unknown_years(self):
        for decade in ("80's", '80s', '1980s', '80’s'):
            result80 = self.library.search('play ' + decade + ' Dylan')
            self.assertEqual(result80['decade'], 1980)
            self.assertEqual([t['title'] for t in result80['tracks']], ['Demo 1980'])
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

    def test_styles_families_subgenres_decades_and_artist_escape(self):
        database = Path(self.temp.name) / 'genres.db'
        con = server.sqlite3.connect(database)
        con.execute('CREATE TABLE tracks(path TEXT,artist TEXT,album TEXT,title TEXT,genre TEXT,year INTEGER)')
        rows = [('Blues Rock', 1975), ('Jazz; Bossa Nova', 1982), ('Disco, Funk', 1978),
                ('Hip-Hop', 1995), ('R&B/Soul', 1985), ('Dubstep', 2010), (None, 1973)]
        con.executemany('INSERT INTO tracks VALUES(?,?,?,?,?,?)',
            [('/mnt/lossless/Copper Pulse.wav', 'Pop', 'Styles', str(i), genre, year)
             for i, (genre, year) in enumerate(rows)])
        con.commit(); con.close()
        before = hashlib.sha256(database.read_bytes()).hexdigest()
        try:
            library = server.Library(database, self.music)
            for command in ('play blues', 'play genre blues', "play 70's genre blues", 'play genre 1970s blues'):
                self.assertEqual([t['title'] for t in library.search(command)['tracks']], ['0'])
            self.assertEqual(library.search('play 80s genre blues')['tracks'], [])
            self.assertEqual([t['title'] for t in library.search('play jazz')['tracks']], ['1'])
            self.assertEqual([t['title'] for t in library.search('queue genre R&B')['tracks']], ['4'])
            self.assertEqual([t['title'] for t in library.search('play rap')['tracks']], ['3'])
            self.assertEqual(library.search('play genre dub')['tracks'], [], 'Dub must not match Dubstep')
            self.assertEqual(library.search("genre: ' OR 1=1 --")['tracks'], [])
            self.assertEqual(len(library.search('play artist Pop')['tracks']), 7)
            styles = library.styles()
            self.httpd.RequestHandlerClass.library = library
            self.assertEqual(json.loads(self.request('/api/styles')[2])['tagged'], 6)
            self.assertEqual(len(json.loads(self.request('/api/search?q=play%20genre%20blues')[2])['tracks']), 1)
            self.assertEqual((styles['tagged'], styles['untagged']), (6, 1))
            counts = {s['name']: s['count'] for s in styles['styles']}
            self.assertEqual(counts['Blues'], 1)
            self.assertEqual(counts['Bossa Nova'], 1)
            self.assertEqual(counts['Reggae'], 0)
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
            self.assertIn('no genre', self.library.search('play blues')['error'])
        finally:
            database.unlink()

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

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required for real MP3 conversion')
    def test_mp3_conversion_ranges_cache_and_original_unchanged(self):
        ident = self.library.search('Copper')['tracks'][0]['id']
        route = '/media/' + str(ident) + '?quality=mp3'
        status, headers, data = self.request(route)
        self.assertEqual((status, headers['Content-Type']), (200, 'audio/mpeg'))
        probe = server.subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
            'stream=codec_name,sample_rate,channels', '-of', 'json', '-i', 'pipe:0'],
            input=data, capture_output=True, check=True)
        stream = json.loads(probe.stdout)['streams'][0]
        self.assertEqual((stream['codec_name'], stream['sample_rate'], stream['channels']), ('mp3', '44100', 2))
        from unittest.mock import patch
        with patch.object(server.subprocess, 'run', side_effect=AssertionError('Cached MP3 should not re-encode')):
            partial = self.request(route, headers={'Range':'bytes=100-199'})
            self.assertEqual(partial[0], 206)
            self.assertEqual(partial[2], data[100:200])
            self.assertEqual(self.request(route, 'HEAD')[1]['Content-Length'], str(len(data)))
        self.assertEqual(self.request('/media/' + str(ident) + '?quality=original')[2], self.library.track(ident).read_bytes())
        self.assertEqual(self.request('/media/' + str(ident) + '?quality=bad')[0], 400)
        self.assertEqual(self.snapshot(), self.before)

    def test_mp3_failure_keeps_source_and_index(self):
        self.httpd.RequestHandlerClass.mp3_cache.binary = 'nonexistent-shuffle-encoder'
        ident = self.library.search('Copper')['tracks'][0]['id']
        self.assertEqual(self.request('/media/' + str(ident) + '?quality=mp3')[0], 503)
        self.assertEqual(list(Path(self.playback_temp.name).iterdir()), [])
        self.assertEqual(self.request('/media/' + str(ident))[0], 200)

    def test_preserved_public_addresses_and_radio_head(self):
        addresses = json.loads(self.request('/api/listening')[2])
        self.assertEqual(addresses['mp3_radio'], 'http://shuffle.tplinkdns.com:8001/stream.mp3')
        self.assertEqual(addresses['player'], 'http://shuffle.tplinkdns.com:8001/')
        self.assertEqual(addresses['lossless_track'], 'http://shuffle.tplinkdns.com:8001/media/{id}?quality=original')
        status, headers, data = self.request('/stream.mp3', 'HEAD')
        self.assertEqual((status, headers['Content-Type'], data), (200, 'audio/mpeg', b''))
        self.assertIsNone(self.httpd.RequestHandlerClass.radio.thread, 'HEAD must not start an encoder')
        self.httpd.RequestHandlerClass.radio.listener_limit = 0
        self.assertEqual(self.request('/stream.mp3')[0], 503)

    def test_webamp_cross_origin_radio_and_preflight(self):
        for origin in ('null', 'https://darkride.example'):
            status, headers, data = self.request('/stream.mp3?diagnostic=cors', 'HEAD', {'Origin':origin})
            self.assertEqual((status, headers['Content-Type'], data), (200, 'audio/mpeg', b''))
            self.assertEqual(headers.get('Access-Control-Allow-Origin'), '*')
            self.assertNotIn('Access-Control-Allow-Credentials', headers)
            status, headers, data = self.request('/stream.mp3', 'OPTIONS', {
                'Origin':origin, 'Access-Control-Request-Method':'GET',
                'Access-Control-Request-Headers':'icy-metadata, range'})
            self.assertEqual((status, data), (204, b''))
            self.assertEqual(headers['Access-Control-Allow-Origin'], '*')
            self.assertIn('GET', headers['Access-Control-Allow-Methods'])
            self.assertIn('Icy-MetaData', headers['Access-Control-Allow-Headers'])
            self.assertIn('Range', headers['Access-Control-Allow-Headers'])
        self.assertIsNone(self.httpd.RequestHandlerClass.radio.thread)
        self.assertNotIn('Access-Control-Allow-Origin', self.request('/')[1])
        self.assertEqual(self.request('/api/search', 'OPTIONS')[0], 405)
        self.httpd.RequestHandlerClass.radio.listener_limit = 0
        self.assertEqual(self.request('/stream.mp3', headers={'Origin':'null'})[1]['Access-Control-Allow-Origin'], '*')

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required for live radio checks')
    def test_shared_radio_continues_across_tracks_and_joins_midstream(self):
        import sqlite3
        from contextlib import closing
        root = Path(self.playback_temp.name)
        short = root / 'short.wav'
        with wave.open(str(short), 'wb') as output:
            output.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
            output.writeframes(bytes(22050 // 5 * 2))

        class TinyLibrary:
            def connect(self):
                con = sqlite3.connect(':memory:')
                con.execute('CREATE TABLE tracks(path TEXT)')
                con.execute('INSERT INTO tracks VALUES(?)', (str(short),))
                return closing(con)
            def track(self, ident): return short

        self.httpd.RequestHandlerClass.radio = radio_module.LibraryRadio(TinyLibrary())
        first = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=10)
        second = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=10)
        try:
            first.request('GET', '/stream.mp3', headers={'Origin':'null'})
            live = first.getresponse()
            self.assertEqual(live.status, 200)
            self.assertEqual(live.getheader('Access-Control-Allow-Origin'), '*')
            self.assertTrue(live.read(4096))
            second.request('GET', '/stream.mp3')
            joined = second.getresponse()
            data = joined.read(32768)  # More than four short tracks' encoded audio.
            decoded = server.subprocess.run(['ffmpeg', '-v', 'error', '-f', 'mp3', '-i', 'pipe:0',
                '-t', '0.2', '-f', 'null', '-'], input=data, capture_output=True, timeout=10)
            self.assertEqual(decoded.returncode, 0, decoded.stderr.decode(errors='replace'))
            self.assertEqual(len(self.httpd.RequestHandlerClass.radio.listeners), 2)
        finally:
            first.close(); second.close()

    def test_artwork_embedded_nearby_and_fallback(self):
        from mutagen.wave import WAVE
        from mutagen.id3 import APIC
        from mutagen.flac import Picture
        ident = self.library.search('Copper')['tracks'][0]['id']
        path = self.library.track(ident)
        original = path.read_bytes()
        png = b'\x89PNG\r\n\x1a\n' + b'embedded-test'
        nearby = self.music / 'cover.jpg'
        try:
            self.assertEqual(self.request('/artwork/' + str(ident))[0], 302)
            self.assertEqual(self.request('/artwork/fallback.svg')[1]['Content-Type'], 'image/svg+xml')
            nearby.write_bytes(b'\xff\xd8\xffnearby-test')
            self.assertEqual(self.request('/artwork/' + str(ident))[2], nearby.read_bytes())
            audio = WAVE(path)
            audio.add_tags()
            audio.tags.add(APIC(mime='image/png', type=3, data=png))
            audio.save()
            unchanged = self.snapshot()
            status, headers, data = self.request('/artwork/' + str(ident))
            self.assertEqual((status, headers['Content-Type'], data), (200, 'image/png', png))
            self.assertEqual(self.request('/artwork/' + str(ident), 'HEAD')[2], b'')
            self.assertEqual(self.snapshot(), unchanged)
            picture = Picture()
            picture.type, picture.mime, picture.data = 3, 'image/png', png
            block = picture.write()
            # Minimal FLAC metadata fixture: STREAMINFO followed by a last PICTURE block.
            streaminfo = bytes(10) + ((44100 << 44) | (15 << 36) | 44100).to_bytes(8, 'big') + bytes(16)
            from unittest.mock import patch
            flac = self.music / 'artwork-test.flac'
            try:
                flac.write_bytes(b'fLaC' + b'\x00\x00\x00\x22' + streaminfo
                                 + b'\x86' + len(block).to_bytes(3, 'big') + block)
                with patch.object(self.library, 'track', return_value=flac):
                    self.assertEqual(self.request('/artwork/' + str(ident))[2], png)
            finally:
                flac.unlink(missing_ok=True)
            self.assertEqual(self.request('/artwork/999999999999999999999')[0], 302)
        finally:
            path.write_bytes(original)
            nearby.unlink(missing_ok=True)

    def test_visualizer_and_shared_audio(self):
        self.assertIn(b'embedded', self.request('/visualizer/index.html?embed=1')[2])
        script = self.request('/visualizer/js/main.js')[2].decode()
        self.assertTrue(script.startswith('import "/palette.js";'))
        self.assertNotIn('Ember test', script)
        self.assertNotIn('window.SHUF = Object.assign', script)
        self.assertIn(b'SHUF_PRESETS', self.request('/palette.js')[2])
        self.assertNotIn(b'/control/next', self.request('/visualizer/js/ui.js')[2])
        self.assertIn(b'const document = window.parent.document;', self.request('/visualizer/js/ui.js')[2])
        page = self.request('/')[2].decode('utf-8')
        self.assertLess(page.index('id="findMusic"'), page.index('id="visualizerControls"'))
        self.assertLess(page.index('id="visualizerControls"'), page.index('id="searchResults"'))
        self.assertEqual(page.count('id="ui"'), 1)
        self.assertIn('id="bank"', page)
        self.assertNotIn(b'id="ui"', self.request('/visualizer/index.html?embed=1')[2])
        self.assertNotIn('id="audio"', page)
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
