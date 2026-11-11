"""Authoritative in-memory station queue and continuous, shared MP3 output."""
import queue
import random
import subprocess
import threading
import time
import math
from collections import deque


class LibraryRadio:
    def __init__(self, library, binary='ffmpeg', listener_limit=16, target_seconds=3600, start_paused=False):
        self.library, self.binary, self.listener_limit = library, binary, listener_limit
        self.condition = threading.Condition()
        self.listeners = set()
        self.thread = self.process = None
        self.closed = False
        if hasattr(library, 'station_catalog'):
            self.catalog = {track['id']:track for track in library.station_catalog()}
        else:
            with library.connect() as con:
                self.catalog = {row[0]:{'id':row[0]} for row in con.execute('SELECT rowid FROM tracks')}
        self.target_seconds = target_seconds
        self.recent = deque(maxlen=50)
        self.pool = list(self.catalog)
        self.mode, self.filter_query = 'library', ''
        self.ids, self.kinds, self.index = [], [], -1
        self.playing = bool(self.pool)
        self.offset, self.started = 0.0, time.monotonic()
        self.version = self.generation = 1
        self.info_cache = {}
        self.error = ''
        self.top_up()
        if self.ids: self.index = 0
        self.playing = bool(self.ids) and not start_paused

    def length(self, ident):
        value = self.info(ident).get('duration') or 240
        try: value = float(value)
        except (ValueError, TypeError): value = 240
        return value if math.isfinite(value) and value > 0 else 240

    def top_up(self):
        # Retain a little Previous history; queue only a rolling hour of future
        # tracks. Explicit requests stay intact even when longer than the target.
        if self.index > 10:
            cut = self.index - 10
            del self.ids[:cut]; del self.kinds[:cut]
            self.index -= cut
        start = max(0, self.index)
        total = sum(self.length(ident) for ident in self.ids[start:])
        if self.index >= 0: total -= min(self.position(), self.length(self.ids[self.index]))
        # Requests inserted ahead of random tracks replace excess random tail.
        while len(self.ids) > start + 1 and self.kinds[-1] == 'random' and total - self.length(self.ids[-1]) >= self.target_seconds:
            total -= self.length(self.ids.pop()); self.kinds.pop()
        candidates = set(self.pool) - set(self.ids[start:])
        while total < self.target_seconds and candidates:
            previous = self.catalog.get(self.ids[-1], {}) if self.ids else {}
            choices = list(candidates)
            different_artist = [ident for ident in choices if str(self.catalog[ident].get('artist') or '').casefold() != str(previous.get('artist') or '').casefold()]
            if different_artist: choices = different_artist
            fresh = [ident for ident in choices if ident not in self.recent]
            if fresh: choices = fresh
            elif self.recent:
                # Reuse the oldest heard entry first when a small pool runs out.
                ages = {ident:index for index,ident in enumerate(self.recent)}
                oldest = min(ages.get(ident,-1) for ident in choices)
                choices = [ident for ident in choices if ages.get(ident,-1)==oldest]
            different_album = [ident for ident in choices if str(self.catalog[ident].get('album') or '').casefold() != str(previous.get('album') or '').casefold()]
            if different_album: choices = different_album
            ident = random.choice(choices)
            candidates.remove(ident)
            if not self.info(ident)['available']: continue
            self.ids.append(ident); self.kinds.append('random')
            total += self.length(ident)
        if self.ids and self.index < 0: self.index = 0

    def start(self):
        with self.condition:
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self.run, daemon=True)
                self.thread.start()

    def info(self, ident):
        if ident not in self.info_cache:
            if hasattr(self.library, 'station_track'):
                result = self.library.station_track(ident)
            else:
                path = self.library.track(ident)
                result = {'id':ident, 'title':path.stem if path else '', 'artist':'', 'album':'',
                          'available':bool(path and path.is_file()), 'duration':0, 'mime_type':'audio/wav'}
            result = result or {'id':ident, 'title':'Unavailable track', 'artist':'', 'album':'', 'available':False, 'duration':0}
            if result['available'] and not result.get('duration'):
                try:
                    import mutagen
                    with self.library.track(ident).open('rb') as source:
                        audio = mutagen.File(source)
                    result['duration'] = float(audio.info.length) if audio else 0
                except (OSError, ValueError, mutagen.MutagenError):
                    result['duration'] = 0
            self.info_cache[ident] = result
        return self.info_cache[ident]

    def position(self):
        return self.offset + (time.monotonic() - self.started if self.playing else 0)

    def advance(self):
        if self.index >= 0: self.recent.append(self.ids[self.index])
        if self.index + 1 < len(self.ids):
            self.index += 1
        else:
            self.ids, self.kinds, self.index = [], [], -1
        self.offset, self.started = 0.0, time.monotonic()
        self.top_up()
        if self.mode == 'album' and 'request' not in self.kinds[max(0,self.index):]:
            self.mode = 'library'
        if self.index < 0: self.playing = False
        self.version += 1
        self.generation += 1

    def settle(self):
        # Encoder EOF owns advancement while streaming. With no encoder the
        # station clock still advances and replenishes the queue automatically.
        if self.process is not None: return
        for _ in range(1000):
            if not self.playing or self.index < 0: return
            duration, elapsed = self.length(self.ids[self.index]), self.position()
            if self.info(self.ids[self.index])['available'] and elapsed < duration: return
            remainder = max(0, elapsed-duration)
            self.advance()
            if self.playing: self.offset = remainder
        self.error = 'Station clock is catching up.'

    def snapshot(self, since=None):
        self.start()
        with self.condition:
            self.settle()
            current = self.info(self.ids[self.index]).copy() if self.index >= 0 else None
            state = {'version':self.version, 'index':self.index, 'playing':self.playing,
                     'position':self.position(), 'current':current, 'queue_count':len(self.ids),
                     'listeners':len(self.listeners), 'error':self.error,
                     'mode':self.mode, 'filter_query':self.filter_query,
                     'queued_seconds':sum(self.length(ident) for ident in self.ids[max(0,self.index):]) - (self.position() if self.index >= 0 else 0)}
            if since != self.version:
                start = max(0, self.index - 10)
                state['queue_start'] = start
                state['queue'] = [self.info(ident).copy() for ident in self.ids[start:start+100]]
            return state

    def validate_ids(self, ids):
        if not isinstance(ids, list) or not ids or len(ids) > 50000:
            raise ValueError('Choose between 1 and 50,000 indexed tracks.')
        if any(type(ident) is not int or not 0 < ident < 2**63 for ident in ids):
            raise ValueError('Invalid indexed track ID.')
        found = set()
        with self.library.connect() as con:
            for offset in range(0, len(ids), 400):
                batch = ids[offset:offset+400]
                found.update(row[0] for row in con.execute('SELECT rowid FROM tracks WHERE rowid IN (' + ','.join('?' for _ in batch) + ')', batch))
        if set(ids) - found: raise ValueError('An indexed track no longer exists.')

    def control(self, action, payload):
        if action in ('replace', 'append', 'program'): self.validate_ids(payload.get('ids'))
        self.start()
        with self.condition:
            self.settle()
            elapsed = self.position()
            previous_id = self.ids[self.index] if self.index >= 0 else None
            interrupt = True
            if action in ('replace', 'program', 'shuffle'):
                if previous_id is not None: self.recent.append(previous_id)
                self.pool = list(payload['ids']) if action == 'program' and not payload.get('album') else list(self.catalog)
                self.mode = 'album' if payload.get('album') else ('filter' if action == 'program' else 'library')
                self.filter_query = payload.get('query','') if action == 'program' else ''
                self.ids = payload['ids'].copy() if action == 'replace' or payload.get('album') else []
                self.kinds = ['request'] * len(self.ids)
                self.index, self.offset, self.playing = (0 if self.ids else -1), 0.0, True
                self.started = time.monotonic()
                self.top_up()
                self.playing = bool(self.ids)
            elif action == 'append':
                if len(self.ids) + len(payload['ids']) > 50000: raise ValueError('Station queue is full.')
                # The current song finishes, then pending user requests, then
                # random picks. Adding requests never resumes a deliberate Pause.
                for pos in range(len(self.ids)-1, self.index, -1):
                    if self.kinds[pos] == 'random':
                        self.ids.pop(pos); self.kinds.pop(pos)
                insertion = max(0,self.index+1)
                while insertion < len(self.ids) and self.kinds[insertion] == 'request': insertion += 1
                self.ids[insertion:insertion] = payload['ids']
                self.kinds[insertion:insertion] = ['request'] * len(payload['ids'])
                if self.index < 0: self.index = 0
                self.top_up()
                interrupt = False
            elif action == 'toggle':
                self.offset = elapsed
                if not self.playing and self.ids:
                    duration = float(self.info(self.ids[self.index]).get('duration') or 0)
                    if duration and self.offset >= duration:
                        self.index, self.offset = 0, 0.0
                self.playing = not self.playing if self.ids else False
            elif action in ('next', 'previous', 'select'):
                target = payload.get('index') if action == 'select' else self.index + (1 if action == 'next' else -1)
                if type(target) is not int or not 0 <= target < len(self.ids):
                    raise ValueError('That queue position is unavailable.')
                if previous_id is not None: self.recent.append(previous_id)
                self.index, self.offset, self.playing = target, 0.0, True
            elif action == 'seek':
                target = payload.get('position')
                if type(target) not in (int, float) or not 0 <= target <= 86400 or self.index < 0:
                    raise ValueError('Invalid playback position.')
                duration = float(self.info(self.ids[self.index]).get('duration') or 0)
                self.offset = min(float(target), max(0, duration - .05)) if duration else float(target)
            elif action == 'remove':
                target = payload.get('index')
                if type(target) is not int or not 0 <= target < len(self.ids): raise ValueError('Invalid queue position.')
                self.ids.pop(target)
                self.kinds.pop(target)
                if not self.ids:
                    self.index, self.offset, self.playing = -1, 0.0, False
                elif target == self.index:
                    if previous_id is not None: self.recent.append(previous_id)
                    self.index, self.offset = min(self.index, len(self.ids)-1), 0.0
                else:
                    if target < self.index: self.index -= 1
                    interrupt = False
            else:
                raise ValueError('Unknown station command.')
            self.top_up()
            self.version += 1
            self.error = ''
            if interrupt:
                self.started = time.monotonic()
                self.generation += 1
                for listener in self.listeners:
                    while not listener.empty():
                        try: listener.get_nowait()
                        except queue.Empty: break
                if self.process and self.process.poll() is None: self.process.terminate()
            self.condition.notify_all()
        return self.snapshot()

    def subscribe(self):
        with self.condition:
            if self.closed or len(self.listeners) >= self.listener_limit:
                return None
            listener = queue.Queue(maxsize=64)
            self.listeners.add(listener)
            self.start()
            self.condition.notify_all()
            return listener

    def unsubscribe(self, listener):
        with self.condition:
            self.listeners.discard(listener)
            if not self.listeners and self.process and self.process.poll() is None:
                self.process.terminate()

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()
            if self.process and self.process.poll() is None:
                self.process.terminate()
            for listener in self.listeners:
                self.finish(listener)
            self.listeners.clear()
        if self.thread:
            self.thread.join(timeout=10)

    @staticmethod
    def finish(listener):
        while not listener.empty():
            try: listener.get_nowait()
            except queue.Empty: break
        listener.put_nowait(None)

    def broadcast(self, chunk):
        with self.condition:
            for listener in list(self.listeners):
                try:
                    listener.put_nowait(chunk)
                except queue.Full:
                    self.listeners.remove(listener)
                    self.finish(listener)
            return bool(self.listeners) and not self.closed

    def run(self):
        try:
            while True:
                with self.condition:
                    self.settle()
                    if self.closed: return
                    if not self.listeners:
                        self.condition.wait(timeout=.2)
                        continue
                    generation, playing = self.generation, self.playing
                    ident = self.ids[self.index] if self.index >= 0 else None
                    offset = self.position()
                    if playing and not self.info(ident)['available']:
                        self.advance()
                        continue
                path = self.library.track(ident) if playing else None
                command = [self.binary, '-nostdin', '-hide_banner', '-loglevel', 'error',
                    '-re']
                if playing:
                    command += ['-ss', str(max(0, offset)), '-protocol_whitelist', 'file,pipe', '-i', str(path)]
                else:
                    command += ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo']
                command += [
                    '-map', '0:a:0', '-vn', '-sn', '-dn', '-map_metadata', '-1',
                    '-c:a', 'libmp3lame', '-b:a', '256k', '-ar', '44100', '-ac', '2',
                    '-threads', '1', '-id3v2_version', '0', '-write_xing', '0', '-f', 'mp3', 'pipe:1']
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
                with self.condition:
                    self.process = process
                    if self.closed or not self.listeners or self.generation != generation:
                        process.terminate()
                produced = False
                try:
                    while chunk := process.stdout.read(4096):
                        produced = True
                        with self.condition:
                            if self.generation != generation:
                                process.terminate()
                                break
                        if not self.broadcast(chunk):
                            process.terminate()
                            break
                finally:
                    process.stdout.close()
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    with self.condition:
                        self.process = None
                        if generation == self.generation and self.listeners and playing:
                            if not produced: self.error = 'A queued track could not be played; moving to the next entry.'
                            self.advance()
        except (OSError, ValueError):
            pass
        finally:
            with self.condition:
                for listener in self.listeners:
                    self.finish(listener)
                self.listeners.clear()

