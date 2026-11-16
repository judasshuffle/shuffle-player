import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
import wave
import time
import shutil
import subprocess
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'synology'/filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
server = load('program_server', 'server.py')
radio = load('program_radio', 'radio.py')
deployment = load('music_deployment', 'deploy-music-feed.py')

class QuietRadio(radio.LibraryRadio):
    def start(self): pass

class ProgrammingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.music = self.root/'music'; self.music.mkdir()
        with wave.open(str(self.music/'tone.wav'), 'wb') as out:
            out.setparams((1,2,44100,0,'NONE','not compressed'))
            import math, struct
            out.writeframes(b''.join(struct.pack('<h',int(6000*math.sin(2*math.pi*440*i/44100))) for i in range(22050)))
        self.db = self.root/'index.db'
        con = sqlite3.connect(self.db)
        con.execute('CREATE TABLE tracks(path TEXT,artist TEXT,album TEXT,title TEXT,duration REAL,year INTEGER,discnumber INTEGER,tracknumber INTEGER)')
        for i in range(120):
            artist = 'Bob Dylan' if i < 24 else f'Artist {i%8}'
            con.execute('INSERT INTO tracks VALUES(?,?,?,?,?,?,?,?)',('/mnt/lossless/tone.wav',artist,f'Album {i%6}',str(i),300,1975 if i<24 else 1985,1,i+1))
        con.commit(); con.close()
        self.library = server.Library(self.db,self.music)
        self.station = QuietRadio(self.library)
    def tearDown(self):
        self.station.close(); self.temp.cleanup()

    def test_hour_full_library_diversity_and_bounded_history(self):
        state = self.station.snapshot()
        self.assertGreaterEqual(state['queued_seconds'],3599)
        self.assertLess(state['queued_seconds'],3900)
        first = self.station.ids.copy()
        self.assertLess(len(first),20)
        heard=[]
        for _ in range(60):
            ident=self.station.ids[self.station.index]
            if heard:
                self.assertNotEqual(self.station.catalog[heard[-1]]['artist'],self.station.catalog[ident]['artist'])
                self.assertNotEqual(self.station.catalog[heard[-1]]['album'],self.station.catalog[ident]['album'])
            self.assertNotIn(ident,heard[-50:])
            heard.append(ident)
            self.station.advance()
            self.assertTrue(self.station.playing)
            self.assertLessEqual(len(self.station.ids),23)
        self.assertTrue(set(heard)-set(first))
        self.assertTrue(any(ident>24 for ident in heard))

    def test_filtered_mix_survives_many_topups(self):
        ids,album=self.library.program('play 70s Bob Dylan')
        self.station.control('program',{'ids':ids,'album':album,'query':'play 70s Bob Dylan'})
        for _ in range(40):
            self.assertEqual(self.station.mode,'filter')
            self.assertTrue(set(self.station.ids[self.station.index:]) <= set(ids))
            current=self.station.ids[self.station.index]
            following=self.station.ids[self.station.index+1]
            self.assertNotEqual(self.station.catalog[current]['album'],self.station.catalog[following]['album'])
            self.station.advance()

    def test_owner_recovery_preserves_queue_and_filter(self):
        query = 'play 70s Bob Dylan'
        ids, album = self.library.program(query)
        saved = [ids[5], ids[3], ids[9], ids[1]]
        self.station.control('replace', {'ids':saved, 'resume_program':{'mode':'filter', 'query':query}})
        self.assertEqual(self.station.ids[:4], saved)
        self.assertEqual(self.station.mode, 'filter')
        self.assertEqual(self.station.filter_query, query)
        self.assertEqual(set(self.station.pool), set(ids))
        for _ in range(30):
            self.assertTrue(set(self.station.ids[self.station.index:]) <= set(ids))
            self.station.advance()
        previous = self.station.ids.copy()
        with self.assertRaises(ValueError):
            self.station.control('replace', {'ids':saved, 'resume_program':{'mode':'invalid'}})
        self.assertEqual(self.station.ids, previous)

    def test_recovery_snapshot_kinds_follow_queue_slice(self):
        for _ in range(14):
            self.station.advance()
        saved = self.station.snapshot()
        start = saved['queue_start']
        self.assertEqual(saved['queue_kinds'], self.station.kinds[start:start+100])
        self.assertEqual(len(saved['queue_kinds']), len(saved['queue']))
        saved['queue_kinds'][0] = 'recovered'
        self.assertNotEqual(self.station.kinds[start], 'recovered', 'Snapshot must be a copy')
        unchanged = self.station.snapshot(since=saved['version'])
        self.assertNotIn('queue', unchanged)
        self.assertNotIn('queue_kinds', unchanged)

    def test_recovery_captured_kinds_and_cursor_preserve_request_priority(self):
        query = 'play 70s Bob Dylan'
        ids, _ = self.library.program(query)
        self.station.control('program', {'ids':ids, 'query':query})
        for _ in range(7):
            self.station.advance()
        self.station.control('append', {'ids':[119]})
        self.station.control('seek', {'position':200})
        self.station.control('toggle', {})
        saved = self.station.snapshot()
        self.assertIn('random', saved['queue_kinds'])
        self.assertIn('request', saved['queue_kinds'])
        deployment.restore(saved, lambda action, **payload: self.station.control(action, payload))
        restored = self.station.snapshot()
        self.assertEqual(deployment.verify_recovery(saved, restored), [])
        self.assertAlmostEqual(restored['position'], saved['position'], places=3)
        self.station.control('append', {'ids':[120]})
        self.assertEqual(self.station.ids[self.station.index+1:self.station.index+3], [119, 120])
        self.assertFalse(self.station.playing)

    def test_recovery_unknown_kinds_retain_tracks_behind_new_requests(self):
        saved = [1, 2, 3, 4]
        self.station.control('replace', {'ids':saved, 'resume_program':{'mode':'library'}})
        self.assertEqual(self.station.kinds[:4], ['recovered'] * 4)
        self.station.control('append', {'ids':[119]})
        self.station.control('append', {'ids':[120]})
        self.assertEqual(self.station.ids[:6], [1, 119, 120, 2, 3, 4])
        self.assertEqual(self.station.kinds[:6], ['recovered', 'request', 'request'] + ['recovered'] * 3)
        saved_state = self.station.snapshot()
        saved_state.pop('queue_kinds')
        deployment.restore(saved_state, lambda action, **payload: self.station.control(action, payload))
        limitations = deployment.verify_recovery(saved_state, self.station.snapshot())
        self.assertIn('not captured', limitations[0])

    def test_recovery_unknown_album_finishes_before_library_fallback(self):
        self.station.control('replace', {'ids':[1, 2, 3],
                                        'resume_program':{'mode':'album', 'query':'saved album'}})
        for ident in [1, 2, 3]:
            self.assertEqual(self.station.mode, 'album')
            self.assertEqual(self.station.ids[self.station.index], ident)
            self.station.advance()
        self.assertEqual(self.station.mode, 'library')
        self.assertTrue(self.station.playing)

    def test_recovery_invalid_kinds_or_cursor_do_not_mutate_station(self):
        before = (self.station.ids.copy(), self.station.kinds.copy(), self.station.index,
                  self.station.mode, self.station.pool.copy(), self.station.version)
        for hint in ({'kinds':['random']}, {'kinds':['random', 'invented']},
                     {'kinds':None}, {'kinds':'random'}, {'kinds':['random', {}]},
                     {'index':True}, {'index':2}, {'position':float('nan')},
                     {'position':float('inf')}, {'position':10**1000}, {'position':-1}):
            with self.subTest(hint=hint), self.assertRaises(ValueError):
                self.station.control('replace', {'ids':[1, 2],
                                                'resume_program':dict(mode='library', **hint)})
            self.assertEqual((self.station.ids, self.station.kinds, self.station.index,
                              self.station.mode, self.station.pool, self.station.version), before)

    def test_recovery_legacy_filter_reports_limitation_without_reprogramming(self):
        query = 'play 70s Bob Dylan'
        ids, _ = self.library.program(query)
        self.station.control('program', {'ids':ids, 'query':query})
        self.station.control('visualizer', {'bank':'VLM', 'preset':'Echo Loom'})
        saved = self.station.snapshot()
        saved.pop('queue_kinds')
        actions = []

        def old_control(action, **payload):
            actions.append(action)
            payload.pop('resume_program', None)
            result = self.station.control(action, payload)
            result.pop('queue_kinds', None)
            return result

        deployment.restore(saved, old_control)
        final = self.station.snapshot()
        final.pop('queue_kinds')
        limitations = deployment.verify_recovery(saved, final, allow_legacy=True)
        self.assertTrue(any('cannot retain the saved filter' in item for item in limitations))
        self.assertNotIn('program', actions)
        self.assertNotIn('shuffle', actions)
        with self.assertRaisesRegex(RuntimeError, 'mode or filter'):
            deployment.verify_recovery(saved, final)
        for key, value in [('current', None), ('visualizer', {'bank':'Default', 'preset':'Tempest MVP'})]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                deployment.verify_recovery(saved, dict(final, **{key:value}), allow_legacy=True)

    def test_recovery_legacy_album_keeps_mode_and_intended_order(self):
        self.station.control('replace', {'ids':[1, 2, 3], 'album':True})
        self.station.control('visualizer', {'bank':'VLM', 'preset':'Echo Loom'})
        saved = self.station.snapshot()
        saved.pop('queue_kinds')

        def old_control(action, **payload):
            payload.pop('resume_program', None)
            result = self.station.control(action, payload)
            result.pop('queue_kinds', None)
            return result

        deployment.restore(saved, old_control)
        final = self.station.snapshot()
        final.pop('queue_kinds')
        self.assertEqual(final['mode'], 'album')
        self.assertTrue(deployment.verify_recovery(saved, final, allow_legacy=True))

    def test_recovery_deployment_images_and_rollback_pin(self):
        first, rollback = deployment.deployment_images(self.root/'incoming-music-feed-one')
        second, _ = deployment.deployment_images(self.root/'incoming-music-feed-two')
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, rollback)
        compose = self.root/'compose.yaml'
        source = ('name: shuffle-player\nservices:\n  player:\n    image: shuffle-player:old\n'
                  '    read_only: true\n  unrelated:\n    image: keep:this\n')
        compose.write_text(deployment.compose_with_image(source, first))
        self.assertIn('    image: ' + first, compose.read_text())
        with patch.object(deployment.subprocess, 'run') as run:
            deployment.pin_rollback_image('sha256:captured-old-image', rollback, compose)
        run.assert_called_once_with([deployment.DOCKER, 'tag', 'sha256:captured-old-image', rollback], check=True)
        self.assertEqual(compose.read_text(), deployment.compose_with_image(source, rollback))
        self.assertIn('    image: keep:this', compose.read_text())
        with self.assertRaises(ValueError):
            deployment.compose_with_image('services:\n  unrelated:\n    image: keep:this\n', first)

    def test_requests_take_priority_and_pause_stays_paused(self):
        startup = QuietRadio(self.library, start_paused=True)
        self.assertFalse(startup.playing)
        self.assertGreater(len(startup.ids),0)
        self.station.control('toggle',{})
        paused=self.station.position()
        request=self.station.ids[self.station.index+3]
        self.station.control('append',{'ids':[request,119]})
        self.station.control('append',{'ids':[118]})
        self.assertEqual(self.station.ids[self.station.index+1:self.station.index+4],[request,119,118])
        self.station.top_up()
        self.assertFalse(self.station.playing)
        self.assertEqual(self.station.position(),paused)
        self.station.control('replace',{'ids':[120,119]})
        self.assertEqual(self.station.ids[:2],[120,119])
        self.assertTrue(self.station.playing)

    def test_album_disc_track_order_over_hour_then_library(self):
        con=sqlite3.connect(self.db)
        for ident,disc,track in [(1,2,1),(2,1,2),(3,1,1)]:
            con.execute('UPDATE tracks SET album=?,duration=1500,discnumber=?,tracknumber=? WHERE rowid=?',('Blonde on Blonde',disc,track,ident))
        con.commit();con.close()
        self.library=server.Library(self.db,self.music)
        self.station=QuietRadio(self.library)
        ids,album=self.library.program('Play the album Blonde on Blonde')
        self.assertTrue(album);self.assertEqual(ids,[3,2,1])
        state=self.station.control('program',{'ids':ids,'album':True,'query':'play the album Blonde on Blonde'})
        self.assertGreater(state['queued_seconds'],3600)
        heard=[]
        for _ in range(3):
            heard.append(self.station.ids[self.station.index]);self.station.advance()
        self.assertEqual(heard,[3,2,1])
        self.assertEqual(self.station.mode,'library')
        self.assertTrue(self.station.playing)
        self.assertGreater(len(self.station.ids[self.station.index:]),0)

    def test_clock_advances_and_tops_up_without_listeners(self):
        now=[1000.0]
        with patch.object(radio.time,'monotonic',lambda:now[0]):
            station=QuietRadio(self.library,target_seconds=600)
            initial=station.ids.copy()
            for _ in range(8):
                now[0]+=301
                station.settle()
            self.assertTrue(station.playing)
            self.assertTrue(set(station.ids)-set(initial))
            station.control('toggle',{})
            position=station.position();now[0]+=10000;station.settle()
            self.assertFalse(station.playing);self.assertEqual(station.position(),position)

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
    def test_real_short_tracks_continue_beyond_first_batch_without_next(self):
        con=sqlite3.connect(self.db);con.execute('UPDATE tracks SET duration=0.5');con.commit();con.close()
        station=radio.LibraryRadio(server.Library(self.db,self.music),target_seconds=0.9)
        first=station.ids.copy();self.assertEqual(len(first),2)
        listener=station.subscribe();data=bytearray();deadline=time.monotonic()+12
        try:
            while len(station.recent)<7 and time.monotonic()<deadline:
                chunk=listener.get(timeout=5)
                self.assertIsNotNone(chunk);data.extend(chunk)
            self.assertGreaterEqual(len(station.recent),7)
            self.assertTrue(station.playing)
            self.assertTrue(set(station.recent)-set(first))
            self.assertIn(listener,station.listeners,'Same subscriber survives all natural EOFs')
            decoded=subprocess.run(['ffmpeg','-v','error','-f','mp3','-i','pipe:0','-f','s16le','pipe:1'],input=data,capture_output=True,timeout=10)
            self.assertEqual(decoded.returncode,0)
            self.assertTrue(any(decoded.stdout),'Real decoded audio, not only a moving queue clock')
        finally: station.close()

if __name__=='__main__': unittest.main()
