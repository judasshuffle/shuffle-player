"""Persistent source settings and guarded working-index scans."""
from contextlib import closing
import json
import ipaddress
import os
from pathlib import Path
import sqlite3
import subprocess
import threading
import time
import uuid
from urllib.parse import urlsplit


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as out:
        json.dump(value, out)
        out.flush()
        os.fsync(out.fileno())
    temporary.replace(path)


def seed_index(backup, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / 'jukebox.db'
    import fcntl
    with (directory / 'scan.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not target.exists():
            temporary = directory / 'seed.tmp'
            with closing(sqlite3.connect(Path(backup).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as source, closing(sqlite3.connect(temporary)) as dest:
                source.backup(dest)
                if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Backup integrity check failed')
            temporary.replace(target)
        # Recover any interrupted working-index transaction before opening read-only readers.
        with closing(sqlite3.connect(target)) as working:
            if working.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Working index check failed; retained backup must be restored manually.')
    return target


class ConnectionSettings:
    """Private installation addresses; never part of the distributed assets."""
    def __init__(self, directory):
        self.path = Path(directory) / 'connection.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {'stream_url': '', 'screen_url': ''}

    def snapshot(self):
        with self.lock:
            return self.data.copy()

    @staticmethod
    def public_address(value):
        if not isinstance(value, str): raise ValueError('Enter your public player address.')
        value = value.strip().rstrip('/')
        if not value: return ''
        parsed = urlsplit(value)
        if (len(value) > 2048 or parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or any(ord(char) < 33 for char in value) or '\\' in value):
            raise ValueError('Use http:// or https:// followed by your public address and port, without a query or password.')
        try:
            if parsed.port == 0: raise ValueError()
        except ValueError: raise ValueError('The port must be a number between 1 and 65535.')
        host = parsed.hostname.lower().rstrip('.')
        local = host == 'localhost' or host.endswith(('.localhost', '.local', '.lan', '.home', '.home.arpa'))
        try: local = local or not ipaddress.ip_address(host).is_global
        except ValueError:
            # Single-label machine names are home-network names, not public DNS.
            local = local or '.' not in host
        if local:
            raise ValueError('That is a home-network address. It can work at home, but people outside your home need your public address or domain name.')
        if parsed.path.endswith(('/stream.mp3', '/dr-screen')):
            raise ValueError('Enter the player address without /stream.mp3 or /dr-screen; those links are generated for you.')
        return value

    def save(self, payload):
        values = {}
        public = self.public_address(payload['public_base']) if 'public_base' in payload else None
        for field in ('stream_url', 'screen_url'):
            value = (public + ('/stream.mp3' if field == 'stream_url' else '/dr-screen')) if public else payload.get(field, '')
            if not isinstance(value, str): raise ValueError('Enter an HTTP or HTTPS address.')
            value = value.strip()
            parsed = urlsplit(value)
            if value and (len(value) > 2048 or parsed.scheme not in ('http', 'https') or not parsed.hostname
                          or parsed.username or parsed.password or parsed.fragment
                          or any(ord(char) < 33 for char in value)):
                raise ValueError('Use a complete HTTP or HTTPS URL without spaces, credentials or fragments.')
            values[field] = value
        with self.lock:
            if public is not None:
                same = public and public == self.data.get('public_base') and all(values[field] == self.data.get(field) for field in values)
                values['public_base'] = public
                values['internet_confirmed_at'] = self.data.get('internet_confirmed_at', 0) if same else 0
                if payload.get('confirm_internet') is True:
                    if not same: raise ValueError('Save your public address first, then test it with Wi-Fi off before confirming.')
                    values['internet_confirmed_at'] = int(time.time())
            atomic_json(self.path, values)
            self.data = values
            return values.copy()


class Sources:
    def __init__(self, directory, radio):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'sources.json'
        self.radio = radio
        self.lock = threading.RLock()
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {'active': 'library', 'stations': []}
        active = next((s for s in self.data['stations'] if s['id'] == self.data['active']), None)
        if active:
            radio.select_source(active)

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.data))

    def test(self, url):
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or len(url) > 2048:
            raise ValueError('Use a direct HTTP or HTTPS audio stream URL without credentials.')
        try:
            result = subprocess.run([self.radio.binary, '-nostdin', '-v', 'error', '-rw_timeout', '8000000',
                '-protocol_whitelist', 'http,https,tcp,tls,crypto', '-i', url,
                '-t', '2', '-map', '0:a:0', '-vn', '-f', 's16le', '-ac', '1', '-ar', '8000', 'pipe:1'],
                capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError('Station test timed out or the decoder is unavailable. Current source is still playing.')
        if result.returncode or len(result.stdout) < 8000:
            raise ValueError('Station test failed: no decodable audio within 15 seconds. Check the direct stream URL; playlists and web pages are not supported. Current source is still playing.')

    def command(self, payload):
        with self.lock:
            action = payload.get('action')
            if action in ('test', 'save'):
                name, url = str(payload.get('name', '')).strip(), str(payload.get('url', '')).strip()
                if not name or len(name) > 120: raise ValueError('Enter a station name (up to 120 characters).')
                self.test(url)
                if action == 'test': return {'ok': True, 'message': 'Audio test passed. Current source is unchanged.'}
                station = {'id': uuid.uuid4().hex, 'name': name, 'url': url}
                self.data['stations'].append(station)
                atomic_json(self.path, self.data)
            elif action == 'select':
                ident = payload.get('id')
                station = next((s for s in self.data['stations'] if s['id'] == ident), None)
                if ident != 'library' and not station: raise ValueError('Unknown source')
                if station: self.test(station['url'])
                previous = self.data['active']
                self.data['active'] = ident
                try: atomic_json(self.path, self.data)
                except OSError:
                    self.data['active'] = previous
                    raise
                self.radio.select_source(station)
            else: raise ValueError('Unknown source command')
            return self.snapshot()


class Scanner:
    def __init__(self, directory, library, radio):
        self.directory, self.library, self.radio = Path(directory), library, radio
        self.status_file = self.directory / 'scan.json'
        self.status = json.loads(self.status_file.read_text()) if self.status_file.exists() else {}
        self.status['running'] = False
        self.guard = threading.Lock()

    def start(self):
        import fcntl
        if not self.guard.acquire(False): raise ValueError('Library scan already running.')
        lock = (self.directory / 'scan.lock').open('a')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Require readable, nonempty NAS mount; never interpret an outage as an empty library.
            if not self.library.music.is_dir() or not any(self.library.music.iterdir()):
                raise ValueError('Scan stopped: NAS music folder is unavailable or empty.')
        except Exception:
            self.status = {**self.status, 'running': False, 'error': 'Scan stopped: NAS folder unavailable or another scan holds the lock.'}
            try:
                atomic_json(self.status_file, self.status)
            finally:
                lock.close()
                self.guard.release()
            raise ValueError('Scan stopped: NAS folder unavailable or another scan holds the lock.')
        self.status = {**self.status, 'running': True, 'error': '', 'started_at': int(time.time())}
        threading.Thread(target=self.run, args=(lock,), daemon=True).start()
        return self.status.copy()

    def run(self, lock):
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
            from update_index_sqlite import scan
            backups = self.directory / 'backups'
            backups.mkdir(exist_ok=True)
            backup = backups / ('jukebox-' + str(time.time_ns()) + '.db')
            with closing(sqlite3.connect(self.library.database)) as source, closing(sqlite3.connect(backup)) as dest:
                source.backup(dest)
            result = scan(self.library.database, self.library.music)
            self.library.refresh_metadata()
            self.radio.refresh_catalog()
            self.status = {**result, 'running': False, 'error': '', 'backup': backup.name}
        except Exception as error:
            self.status = {**self.status, 'running': False, 'error': 'Scan stopped: ' + str(error)}
        finally:
            try:
                atomic_json(self.status_file, self.status)
            finally:
                lock.close()
                self.guard.release()
