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
