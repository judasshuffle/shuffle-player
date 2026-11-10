"""A shared, on-demand MP3 radio output from the existing read-only index."""
import queue
import random
import subprocess
import threading


class LibraryRadio:
    def __init__(self, library, binary='ffmpeg', listener_limit=16):
        self.library, self.binary, self.listener_limit = library, binary, listener_limit
        self.condition = threading.Condition()
        self.listeners = set()
        self.thread = self.process = None
        self.closed = False

    def subscribe(self):
        with self.condition:
            if self.closed or len(self.listeners) >= self.listener_limit:
                return None
            listener = queue.Queue(maxsize=64)
            self.listeners.add(listener)
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self.run, daemon=True)
                self.thread.start()
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
            with self.library.connect() as con:
                ids = [row[0] for row in con.execute('SELECT rowid FROM tracks')]
            remaining, failures = [], 0
            while ids and failures < len(ids):
                with self.condition:
                    self.condition.wait_for(lambda: self.closed or self.listeners)
                    if self.closed: return
                if not remaining:
                    remaining = ids.copy()
                    random.shuffle(remaining)
                ident = remaining.pop()
                path = self.library.track(ident)
                if path is None or not path.is_file():
                    failures += 1
                    continue
                # No metadata headers between tracks; MPEG frames continue across files.
                command = [self.binary, '-nostdin', '-hide_banner', '-loglevel', 'error',
                    '-re', '-protocol_whitelist', 'file,pipe', '-i', str(path),
                    '-map', '0:a:0', '-vn', '-sn', '-dn', '-map_metadata', '-1',
                    '-c:a', 'libmp3lame', '-b:a', '256k', '-ar', '44100', '-ac', '2',
                    '-threads', '1', '-id3v2_version', '0', '-write_xing', '0', '-f', 'mp3', 'pipe:1']
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
                with self.condition:
                    self.process = process
                    if self.closed or not self.listeners:
                        process.terminate()
                produced = False
                try:
                    while chunk := process.stdout.read(4096):
                        produced = True
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
                failures = 0 if produced else failures + 1
        except (OSError, ValueError):
            pass
        finally:
            with self.condition:
                for listener in self.listeners:
                    self.finish(listener)
                self.listeners.clear()

