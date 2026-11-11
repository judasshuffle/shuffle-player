"""Read-only indexed library and browser media service. No indexing endpoints."""
from contextlib import closing
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import hashlib
import subprocess
import tempfile
import threading
from collections import OrderedDict
from urllib.parse import parse_qs, urlparse
import queue
import secrets
import hmac
import time

# Minimal container images may lack the OS MIME database.
for extension, kind in {'.flac': 'audio/flac', '.mp3': 'audio/mpeg',
                        '.m4a': 'audio/mp4', '.ogg': 'audio/ogg',
                        '.opus': 'audio/ogg', '.wav': 'audio/wav'}.items():
    mimetypes.add_type(kind, extension)

HERE = Path(__file__).resolve().parent


class OwnerAuth:
    """One privately provisioned owner key; signed requests expire and cannot replay."""
    def __init__(self, key=''):
        if key and not re.fullmatch(r'[0-9a-f]{64}', key):
            raise ValueError('Owner key must contain 64 lowercase hex characters')
        self.key = key.encode('ascii')
        self.epoch = secrets.token_hex(16)
        self.used = {}
        self.lock = threading.Lock()

    def verify(self, method, path, headers, body=b''):
        if not self.key: return False  # No configured key never means open access.
        stamp = headers.get('X-Shuffle-Time', '')
        nonce = headers.get('X-Shuffle-Nonce', '')
        signature = headers.get('X-Shuffle-Signature', '')
        if headers.get('X-Shuffle-Epoch', '') != self.epoch: return False
        if not re.fullmatch(r'\d{10}', stamp) or not re.fullmatch(r'[a-zA-Z0-9{}-]{16,80}', nonce): return False
        now = time.time()
        if abs(now - int(stamp)) > 120 or not re.fullmatch(r'[0-9a-f]{64}', signature): return False
        message = '\n'.join((method, path, self.epoch, stamp, nonce, hashlib.sha256(body).hexdigest())).encode()
        expected = hmac.new(self.key, message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature): return False
        with self.lock:
            self.used = {key:expiry for key, expiry in self.used.items() if expiry > now}
            if nonce in self.used or len(self.used) >= 10000: return False
            self.used[nonce] = now + 240
        return True

# Families match existing tags only; no classification is inferred from audio.
STYLE_FAMILIES = {
    'Blues': ('blues', 'rhythm and blues'), 'Jazz': ('jazz', 'bebop', 'swing', 'bossa nova'),
    'Disco': ('disco',), 'Rock': ('rock', 'rockabilly'), 'Pop': ('pop', 'synthpop', 'britpop'),
    'Soul': ('soul', 'motown', 'northern soul'), 'Funk': ('funk',),
    'R&B': ('r and b', 'rhythm and blues'), 'Hip-hop': ('hip hop', 'rap'),
    'Electronic': ('electronic', 'electronica', 'ambient', 'techno', 'house', 'trance', 'drum and bass', 'dubstep', 'synthpop'),
    'Dance': ('dance', 'disco', 'house', 'techno', 'trance', 'edm'),
    'Folk': ('folk',), 'Country': ('country', 'americana', 'bluegrass'),
    'Classical': ('classical', 'baroque', 'romantic', 'chamber', 'orchestral', 'opera'),
    'Reggae': ('reggae', 'dub', 'ska'), 'Punk': ('punk',), 'Metal': ('metal',),
    'Alternative': ('alternative', 'alt rock', 'indie'), 'Indie': ('indie',),
    'Progressive rock': ('progressive rock', 'prog rock'), 'Classic rock': ('classic rock',),
    'Hard rock': ('hard rock',), 'Psychedelic': ('psychedelic',),
    'Garage rock': ('garage rock',), 'Glam rock': ('glam',),
    'New wave': ('new wave', 'new romantic'), 'Post-punk': ('post punk',),
    'Synth-pop': ('synthpop', 'synth pop'), 'Britpop': ('britpop', 'brit pop'),
    'Singer-songwriter': ('singer songwriter', 'singer and songwriter'),
    'Americana': ('americana',), 'Bluegrass': ('bluegrass',), 'Gospel': ('gospel',),
    'World': ('world',), 'Latin': ('latin', 'salsa', 'bossa nova', 'samba', 'tango'),
    'Afrobeat': ('afrobeat', 'afrobeats'), 'Ska': ('ska',), 'Dub': ('dub',),
    'Ambient': ('ambient',), 'House': ('house',), 'Techno': ('techno',),
    'Trance': ('trance',), 'Drum and bass': ('drum and bass', 'drum n bass', 'dnb'),
    'Trip-hop': ('trip hop',), 'Experimental': ('experimental', 'avant garde'),
    'Soundtrack': ('soundtrack', 'score', 'film music'), 'Musical theatre': ('musical', 'musicals', 'show tunes'),
    'Easy listening': ('easy listening', 'lounge'), 'Vocal': ('vocal',),
    'Christmas': ('christmas', 'holiday'), 'Comedy': ('comedy', 'funny'),
    'Spoken word': ('spoken word',), 'New age': ('new age',),
}


def style_key(text):
    return re.sub(r'\s+', ' ', re.sub(r'[-_/\\]+', ' ', text.casefold()).replace('&', ' and ')).strip()


def style_matches(genre, terms):
    value = style_key(genre or '')
    return any(re.search(r'(?<!\w)' + re.escape(style_key(term)) + r'(?!\w)', value) for term in terms)


def interpret(query):
    text = query.strip()
    command = re.match(r"^(play|queue)\s+", text, re.I)
    if command:
        text = text[command.end():].strip()
    decade = re.match(r"^(\d{2}|\d{4})['’]?s(?:\s+|$)", text, re.I)
    if decade:
        year = int(decade[1])
        if len(decade[1]) == 2:
            year += 2000 if year < 30 else 1900
        if year % 10 or not 1000 <= year <= 2090:
            raise ValueError("Use a decade such as 70s or 1970s, not a single year.")
        return text[decade.end():].strip(), year, True
    return text, None, bool(command)


class Library:
    def __init__(self, database, music):
        self.database, self.music = Path(database).resolve(), Path(music).resolve()
        if not self.database.is_file() or not self.music.is_dir():
            raise ValueError("Existing copied index and music mount required. Nothing will be created.")
        if any(Path(str(self.database) + suffix).exists() for suffix in ("-wal", "-journal")):
            raise ValueError("Use a consistent standalone SQLite backup without active journal files.")
        with self.connect() as con:
            columns = {r[1] for r in con.execute("PRAGMA table_info(tracks)")}
            self.columns = columns
            self.has_genre = 'genre' in columns
            self.genre_counts = con.execute('SELECT genre,COUNT(*) FROM tracks GROUP BY genre').fetchall() if self.has_genre else []
            if not {"path", "artist", "album", "title"}.issubset(columns):
                raise ValueError("Incompatible index; no migration is permitted.")
            for row in con.execute("SELECT path FROM tracks"):
                self.resolve(row[0])  # Validate every stored prefix without walking the music library.

    def connect(self):
        # Only a closed, consistent backup is supported. Immutable prevents sidecar writes.
        return closing(sqlite3.connect(self.database.as_uri() + "?mode=ro&immutable=1", uri=True))

    def resolve(self, stored):
        path = PurePosixPath(stored)
        if ".." in path.parts or not path.is_relative_to(PurePosixPath("/mnt/lossless")):
            raise ValueError("Index paths must be under /mnt/lossless; mount there without rewriting the index.")
        resolved = self.music.joinpath(*path.relative_to("/mnt/lossless").parts).resolve()
        if not resolved.is_relative_to(self.music):
            raise ValueError("Track escapes the music mount")
        return resolved

    def describe(self, rows):
        return [{**{k: r[k] for k in ("id", "artist", "album", "title")},
                 "mime_type": mimetypes.guess_type(r['path'])[0] or 'application/octet-stream',
                 "available": self.resolve(r["path"]).is_file()} for r in rows]

    def station_track(self, ident):
        with self.connect() as con:
            con.row_factory = sqlite3.Row
            extra = ',duration' if 'duration' in self.columns else ''
            row = con.execute('SELECT rowid AS id,path,artist,album,title' + extra + ' FROM tracks WHERE rowid=?', (ident,)).fetchone()
        return {**self.describe([row])[0], 'duration':row['duration'] if extra else 0} if row else None

    def station_catalog(self):
        # Metadata only: read the existing index, never enumerate music folders.
        with self.connect() as con:
            con.row_factory = sqlite3.Row
            fields = [name for name in ('duration','tracknumber','discnumber') if name in self.columns]
            rows = con.execute('SELECT rowid AS id,path,artist,album,title' + ''.join(','+name for name in fields) + ' FROM tracks').fetchall()
        return [dict(row) for row in rows]

    def program(self, query):
        tracks, cursor = [], 0
        while True:
            result = self.search(query, cursor)
            if result.get('error'): raise ValueError(result['error'])
            tracks.extend(track['id'] for track in result['tracks'] if track['available'])
            if not result['has_more']: break
            cursor += 50
        if not tracks: raise ValueError('No available matches. Queue unchanged.')
        return tracks, bool(result.get('album_request'))

    def shuffle_batch(self, after=0):
        # Keyset pagination reads indexed rows only; it does not enumerate folders.
        with self.connect() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute("SELECT rowid AS id,path,artist,album,title FROM tracks "
                               "WHERE rowid>? ORDER BY rowid LIMIT 501", (after,)).fetchall()
        return {"tracks": self.describe(rows[:500]), "has_more": len(rows) > 500,
                "after": rows[499]["id"] if len(rows) >= 500 else after}

    def search(self, query="", offset=0):
        album_command = re.match(r'^(?:(?:play|queue)\s+)?(?:the\s+)?album\s+(.+)$', query.strip(), re.I)
        if album_command:
            name = album_command[1].strip().strip('"')
            with self.connect() as con:
                con.row_factory = sqlite3.Row
                rows = con.execute('SELECT rowid AS id,path,artist,album,title FROM tracks WHERE album = ? COLLATE NOCASE', (name,)).fetchall()
            wanted = {row['id'] for row in rows}
            catalog = {track['id']:track for track in self.station_catalog() if track['id'] in wanted}
            import mutagen
            def order(row):
                data = catalog[row['id']]
                disc, track = data.get('discnumber'), data.get('tracknumber')
                if not disc or not track:
                    with self.resolve(row['path']).open('rb') as source:
                        tags = mutagen.File(source, easy=True)
                    tags = tags or {}
                    disc = disc or (tags.get('discnumber') or ['1'])[0]
                    track = track or (tags.get('tracknumber') or [''])[0]
                def number(value):
                    match = re.match(r'^(\d+)', str(value))
                    if not match: raise ValueError('Album track order is missing; cannot play this release in order.')
                    return int(match[1])
                return number(disc), number(track)
            try:
                ordered = [(order(row), row) for row in rows]
                if len({key for key,row in ordered}) != len(ordered):
                    raise ValueError('Several releases share this album title and track numbers; choose a specific release.')
                rows = [row for key,row in sorted(ordered, key=lambda item:item[0])]
            except (OSError, ValueError, TypeError, mutagen.MutagenError) as error:
                return {'tracks':[], 'has_more':False, 'error':str(error)}
            return {'tracks':self.describe(rows[offset:offset+50]), 'has_more':len(rows)>offset+50,
                    'album_request':True, 'message':'Album in disc and track order; library shuffle resumes afterwards.'}
        text, decade, artist_only = interpret(query)
        explicit_style = re.match(r'^(?:genre|style)(?:\s*:\s*|\s+)', text, re.I)
        explicit_artist = re.match(r'^artist(?:\s*:\s*|\s+)', text, re.I)
        if explicit_artist:
            text = text[explicit_artist.end():].strip()
            artist_only = True
        if explicit_style:
            text = text[explicit_style.end():].strip()
            if decade is None:
                text, decade, _ = interpret(text)
        family = next((name for name in STYLE_FAMILIES if style_key(name) == style_key(text)), None)
        if style_key(text) in ('rap', 'hip hop'): family = 'Hip-hop'
        if style_key(text) == 'rhythm and blues': family = 'R&B'
        genre_search = not explicit_artist and bool(explicit_style or family)
        terms = STYLE_FAMILIES.get(family, (text,))
        if genre_search and not self.has_genre:
            return {'tracks': [], 'has_more': False, 'error': 'Style search unavailable: this index has no genre column.'}
        if genre_search and not text:
            return {'tracks': [], 'has_more': False, 'error': 'Choose a musical style, such as blues or jazz.'}
        # Escape LIKE metacharacters; values always use bound parameters.
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = "%" + escaped + "%"
        where = "artist LIKE ? ESCAPE '\\'" if artist_only else (
            "(artist LIKE ? ESCAPE '\\' OR album LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\')")
        values = [pattern] if artist_only else [pattern] * 3
        if genre_search:
            where, values = 'style_match(genre)=1', []
        info = {"artist": text if artist_only else None, "decade": decade,
                "message": f"Artist contains ‘{text}’; years {decade}–{decade + 9}. Review matches before playback."
                           if decade else "Review matches before playback."}
        with self.connect() as con:
            con.row_factory = sqlite3.Row
            if genre_search:
                matching_tags = {tag for tag, _ in self.genre_counts if style_matches(tag, terms)}
                con.create_function('style_match', 1, lambda genre: genre in matching_tags)
                info.update(artist=None, style=family or text,
                            message=f'Style: {family or text}' + (f'; years {decade}–{decade + 9}' if decade else '') + '. Matches existing genre tags; review before playback.')
            if decade is not None:
                columns = {r[1] for r in con.execute("PRAGMA table_info(tracks)")}
                if "year" not in columns:
                    return {"tracks": [], "has_more": False, "error": "Decade search unavailable: this index has no year column. No unfiltered tracks were substituted."}
                valid = "(length(trim(CAST(year AS TEXT)))=4 AND trim(CAST(year AS TEXT)) NOT GLOB '*[^0-9]*' AND CAST(year AS INTEGER) BETWEEN 1000 AND 2099)"
                missing = con.execute("SELECT COUNT(*) FROM tracks WHERE " + where + " AND (year IS NULL OR NOT " + valid + ")", values).fetchone()[0]
                known = con.execute("SELECT COUNT(*) FROM tracks WHERE " + where + " AND " + valid, values).fetchone()[0]
                if missing and not known:
                    return {"tracks": [], "has_more": False, "error": "Decade search unavailable: matching artist tracks have no usable four-digit year data. No unfiltered tracks were substituted."}
                info["unknown_years_excluded"] = missing
                if missing:
                    info["message"] += f" {missing} artist track(s) lack usable years and were excluded."
                where += " AND " + valid + " AND CAST(year AS INTEGER) BETWEEN ? AND ?"
                values += [decade, decade + 9]
            rows = con.execute("SELECT rowid AS id,path,artist,album,title FROM tracks WHERE " + where +
                " ORDER BY artist,album,title LIMIT 51 OFFSET ?", (*values, offset)).fetchall()
        return {"tracks": self.describe(rows[:50]), "has_more": len(rows) > 50, **info}

    def styles(self):
        if not self.has_genre:
            return {'styles': [], 'error': 'This index has no genre column.'}
        rows = self.genre_counts
        result = [{'name': name, 'count': sum(n for tag, n in rows if style_matches(tag, terms)), 'family': True}
                  for name, terms in STYLE_FAMILIES.items()]
        known = {style_key(item['name']) for item in result}
        # Expose every existing subgenre, including tags outside the family list.
        tags = sorted({part.strip() for tag, _ in rows if tag for part in re.split(r'[,;/\\]', tag) if part.strip()}, key=str.casefold)
        for tag in tags:
            key = style_key(tag)
            if key not in known:
                result.append({'name': tag, 'count': sum(n for raw, n in rows if style_matches(raw, (tag,))), 'family': False})
                known.add(key)
        return {'styles': result, 'tagged': sum(n for tag, n in rows if tag and tag.strip()),
                'untagged': sum(n for tag, n in rows if not tag or not tag.strip())}

    def track(self, ident):
        with self.connect() as con:
            row = con.execute("SELECT path FROM tracks WHERE rowid=?", (ident,)).fetchone()
        return self.resolve(row[0]) if row else None

    def artwork(self, ident):
        # On-demand metadata reads only. No cache and no directory traversal/scan.
        import base64
        import mutagen
        from mutagen.flac import Picture
        track = self.track(ident)
        if track is None or not track.is_file():
            return None
        candidates = []
        try:
            with track.open('rb') as source:
                audio = mutagen.File(source)
            if audio is not None:
                candidates.extend(sorted(getattr(audio, 'pictures', []), key=lambda p: p.type != 3))
                tags = audio.tags
                if tags:
                    if hasattr(tags, 'getall'):
                        candidates.extend(sorted(tags.getall('APIC'), key=lambda p: p.type != 3))
                    for encoded in tags.get('metadata_block_picture', []):
                        try:
                            candidates.append(Picture(base64.b64decode(encoded)))
                        except (ValueError, mutagen.MutagenError):
                            pass
                    candidates.extend(tags.get('covr', []))
        except (OSError, ValueError, mutagen.MutagenError):
            pass
        for picture in candidates:
            data = bytes(getattr(picture, 'data', picture))
            if image_type(data):
                return data, image_type(data)
        # Check exact conventional names in this album directory only.
        for name in ('cover', 'folder', 'front', 'Cover', 'Folder', 'Front'):
            for extension in ('.jpg', '.jpeg', '.png', '.webp', '.JPG', '.PNG'):
                path = (track.parent / (name + extension)).resolve()
                if not path.is_relative_to(self.music):
                    continue
                try:
                    with path.open('rb') as source:
                        data = source.read(16 * 1024 * 1024 + 1)
                    if image_type(data):
                        return data, image_type(data)
                except OSError:
                    pass
        return None


def image_type(data):
    if not 0 < len(data) <= 16 * 1024 * 1024:
        return None
    if data.startswith(b'\xff\xd8\xff'): return 'image/jpeg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'): return 'image/png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP': return 'image/webp'
    return None


class PlaybackConversionError(Exception):
    pass


class Mp3Cache:
    """Disposable playback files, bounded and isolated from the library/index."""
    def __init__(self, directory, binary='ffmpeg', max_bytes=256 * 1024 * 1024):
        self.directory = Path(directory)
        self.binary, self.max_bytes = binary, max_bytes
        self.files = OrderedDict()
        self.lock = threading.Lock()

    def open(self, source):
        stat = source.stat()
        key = hashlib.sha256(f'{source}:{stat.st_size}:{stat.st_mtime_ns}:mp3-256-v1'.encode()).hexdigest()
        # One encoder at a time; completed files can be served concurrently.
        with self.lock:
            if key in self.files:
                path = self.files.pop(key)
                self.files[key] = path
                return path.open('rb')
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.directory, suffix='.mp3', delete=False) as temporary:
                output = Path(temporary.name)
            try:
                result = subprocess.run([
                    self.binary, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                    '-protocol_whitelist', 'file,pipe', '-i', str(source), '-map', '0:a:0',
                    '-vn', '-sn', '-dn', '-map_metadata', '-1', '-c:a', 'libmp3lame',
                    '-b:a', '256k', '-ar', '44100', '-ac', '2', '-threads', '1',
                    '-f', 'mp3', str(output)
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180, check=False)
                size = output.stat().st_size
                if result.returncode or not size or size > self.max_bytes:
                    raise PlaybackConversionError('MP3 conversion unavailable. Try original playback.')
                total = sum(p.stat().st_size for p in self.files.values())
                while self.files and total + size > self.max_bytes:
                    _, old = self.files.popitem(last=False)
                    total -= old.stat().st_size
                    old.unlink()  # Only this process's disposable MP3 output, never source files.
                self.files[key] = output
                return output.open('rb')
            except (OSError, subprocess.SubprocessError, PlaybackConversionError) as error:
                output.unlink(missing_ok=True)
                raise PlaybackConversionError('MP3 conversion unavailable. Try original playback.') from error


class Handler(SimpleHTTPRequestHandler):
    library = None
    visuals = None
    mp3_cache = None
    radio = None
    control_access = False
    owner_auth = OwnerAuth()

    def station_state(self, since=None, owner=False):
        state = self.radio.snapshot(since)
        state['can_control'] = owner
        if not owner:
            for key in ('queue', 'queue_start'): state.pop(key, None)
        return state

    def trusted_control_host(self):
        return self.headers.get('Host', '').split(':')[0].lower() in ('192.168.68.81', 'greatatuin', 'localhost', '127.0.0.1')

    def visualizer_parts(self):
        source = (self.visuals / 'index.html').read_text(encoding='utf-8')
        start, end = source.index('<div id="ui">'), source.index('<script type="module"')
        controls = source[start:end]
        # Playback belongs to the parent's existing audio element, never a second stream.
        controls = re.sub(r'<audio\b.*?</audio>', '', controls, flags=re.S)
        return source[:start] + source[end:], controls

    def end_headers(self):
        if urlparse(self.path).path == '/stream.mp3':
            # Webamp uses an anonymous cross-origin audio element, including from
            # DarkRide's qrc: page (Origin: null). Direct browser playback alone
            # does not exercise this requirement. Scope it to the public radio.
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Icy-MetaData, Range')
            self.send_header('Access-Control-Expose-Headers', 'Content-Type, Content-Length, Content-Range, Accept-Ranges, icy-name')
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-src 'self'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def content(self, data, kind):
        if isinstance(data, str): data = data.encode()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD": self.wfile.write(data)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ('/api/station/control', '/api/dj'):
            return self.send_error(405, "Indexing and system controls are disabled")
        try:
            if path == '/api/station/control' and not self.control_access:
                return self.send_error(403, 'Use the signed DJ endpoint')
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 1048576 or self.headers.get_content_type() != 'application/json': raise ValueError()
            body = self.rfile.read(size)
            if not self.owner_auth.verify('POST', self.path, self.headers, body):
                return self.send_error(403, 'Owner signature required, expired or already used')
            payload = json.loads(body)
            if not isinstance(payload, dict): raise ValueError()
            if path == '/api/dj': return self.dj_command(payload)
            if payload.get('action') == 'program':
                query = payload.get('query', '')
                if not isinstance(query,str) or len(query)>200: raise ValueError('Invalid search')
                ids, album = self.library.program(query)
                payload = {'action':'program', 'ids':ids, 'query':query, 'album':album}
            self.radio.control(payload.get('action'), payload)
            return self.content(json.dumps(self.station_state(owner=True)), 'application/json')
        except (ValueError, TypeError) as error:
            return self.send_error(400, str(error) or 'Invalid station command')

    def dj_command(self, payload):
        action = payload.get('action')
        query = payload.get('query', '')
        if not isinstance(query, str) or len(query) > 200: raise ValueError('Search is too long')
        if action == 'search':
            offset = payload.get('offset', 0)
            if type(offset) is not int or not 0 <= offset <= 1000000: raise ValueError('Invalid offset')
            return self.content(json.dumps(self.library.search(query, offset)), 'application/json')
        if action in ('play', 'append', 'shuffle'):
            if action != 'shuffle' and not query.strip(): raise ValueError('Type a search first')
            if action == 'shuffle': self.radio.control('shuffle', {})
            else:
                ids, album = self.library.program(query)
                self.radio.control('append' if action == 'append' else 'program', {'ids':ids, 'album':album, 'query':query})
        elif action == 'next': self.radio.control('next', {})
        elif action != 'state': raise ValueError('Unknown DJ command')
        return self.content(json.dumps(self.station_state(owner=True)), 'application/json')

    def do_HEAD(self):
        self.do_GET()

    def do_OPTIONS(self):
        if urlparse(self.path).path != '/stream.mp3':
            return self.send_error(405, 'Preflight is available for the public radio only')
        self.send_response(204)
        self.send_header('Allow', 'GET, HEAD, OPTIONS')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        if path == '/api/owner-challenge':
            return self.content(json.dumps({'epoch': self.owner_auth.epoch, 'time': int(time.time())}), 'application/json')
        if path == '/api/station':
            if self.control_access and not self.trusted_control_host(): return self.send_error(403)
            try: since = int(parse_qs(url.query).get('since', ['0'])[0])
            except ValueError: return self.send_error(400)
            owner = self.owner_auth.verify('GET', self.path, self.headers)
            return self.content(json.dumps(self.station_state(since, owner)), 'application/json')
        if path == '/stream.mp3':
            return self.radio_stream()
        if path == '/api/listening':
            base = os.environ.get('PUBLIC_LISTENING_BASE', 'http://shuffle.tplinkdns.com:8001').rstrip('/')
            return self.content(json.dumps({'player': base + '/', 'mp3_radio': base + '/stream.mp3',
                'lossless_track': base + '/media/{id}?quality=original',
                'mp3_track': base + '/media/{id}?quality=mp3'}), 'application/json')
        if path == '/api/styles':
            if not self.control_access: return self.send_error(403)
            return self.content(json.dumps(self.library.styles()), 'application/json')
        if path == '/artwork/fallback.svg':
            return self.content('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300"><rect width="300" height="300" fill="#24343d"/><circle cx="150" cy="135" r="75" fill="#10151c"/><circle cx="150" cy="135" r="22" fill="#b8f0d2"/><text x="150" y="255" text-anchor="middle" fill="#b8f0d2" font-family="sans-serif" font-size="18">No album artwork</text></svg>', 'image/svg+xml')
        if path.startswith('/artwork/'):
            try:
                ident = int(path.removeprefix('/artwork/'))
                if not 0 < ident < 2**63: raise ValueError()
                art = self.library.artwork(ident)
            except (ValueError, OSError, sqlite3.Error):
                art = None
            if art:
                return self.content(*art)
            self.send_response(302)
            self.send_header('Location', '/artwork/fallback.svg')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if path in ("/api/search", "/api/shuffle"):
            if not self.control_access: return self.send_error(403, 'Use the owner DJ remote')
            query = parse_qs(url.query)
            try:
                offset = int(query.get("offset", ["0"])[0])
                if not 0 <= offset <= 1000000: raise ValueError()
                if path == "/api/shuffle":
                    after = int(query.get("after", ["0"])[0])
                    if not 0 <= after < 2**63: raise ValueError()
                    result = self.library.shuffle_batch(after)
                else:
                    result = self.library.search(query.get("q", [""])[0][:200], offset)
            except (ValueError, sqlite3.Error, OSError):
                return self.send_error(400, "Search unavailable")
            return self.content(json.dumps(result), "application/json")
        if path.startswith("/media/"):
            quality = parse_qs(url.query).get('quality', ['original'])[0]
            if quality not in ('original', 'mp3'):
                return self.send_error(400, 'Unknown playback quality')
            return self.media(path, quality)
        if path in ('/dr-screen', '/dr-screen/'):
            text = (HERE / 'dr-screen.html').read_text(encoding='utf-8')
            text = text.replace('<!-- SHUFFLIZER_CONTROLS -->', self.visualizer_parts()[1])
            return self.content(text, 'text/html; charset=utf-8')
        if path in ('/dr-remote', '/dr-remote/'):
            return self.content((HERE / 'dr-remote.html').read_bytes(), 'text/html; charset=utf-8')
        if path in ('/dr-screen.js', '/dr-screen-entity.js', '/dr-dj.js', '/dr-remote.js', '/owner.js', '/sha256.js'):
            return self.content((HERE / path.lstrip('/')).read_bytes(), 'text/javascript')
        if path in ("/", "/app.js", "/palette.js", "/station.js"):
            if not self.control_access and path != '/palette.js':
                if path != '/': return self.send_error(403, 'Dashboard is LAN-only')
                self.send_response(302)
                self.send_header('Location', '/dr-screen')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if path == '/':
                text = (HERE / 'index.html').read_text(encoding='utf-8')
                text = text.replace('<!-- SHUFFLIZER_CONTROLS -->', self.visualizer_parts()[1])
                return self.content(text, 'text/html; charset=utf-8')
            return self.content((HERE / ("index.html" if path == "/" else path.lstrip('/'))).read_bytes(),
                                "text/html; charset=utf-8" if path == "/" else "text/javascript")
        if path == "/visualizer/index.html":
            text = self.visualizer_parts()[0].replace('src="/js/main.js"', 'src="/visualizer/js/main.js"')
            text = re.sub(r'src="http[^\"]+"', '', text)
            text = text.replace('</head>', '<style>#audio,.audio-options{display:none!important}</style></head>')
            return self.content(text, "text/html; charset=utf-8")
        if path == "/visualizer/js/main.js":
            text = (self.visuals / "js/main.js").read_text()
            # Initialise palette state BEFORE ui.js mounts and captures the preset list.
            text = 'import "/palette.js";\n' + text
            start = text.index('// --- SHUFFLIZER_PALETTE_CORE ---')
            end = text.index('const audio = initAudio', start)
            text = text[:start] + text[end:]
            text = text.replace('const audioEl = document.getElementById("audio");', 'const audioEl = window.parent.document.getElementById("player");')
            start, end = text.index("// Use the page host"), text.index("const ui = initUI();")
            text = text[:start] + text[end:]
            text = text.replace('const audio = initAudio(audioEl, { startMuted: ui.state.muted });',
                'ui.els.muted.checked = false; ui.state.muted = false; const audio = window.parent.playerAudio;')
            # Parent owns playback and now-playing; no Pi or fixture polling.
            start = text.index("startNowPlaying({")
            end = text.index("// SHUFFLIZER_AUTOHIDE_UI", start)
            text = text[:start] + 'setInterval(() => { ui.state.trackTitle = window.parent.currentTrackTitle || ""; }, 500);\n' + text[end:]
            start = text.find("// --- Voice flash overlay")
            if start >= 0: text = text[:start]
            return self.content(text, "text/javascript")
        if path == '/visualizer/js/ui.js':
            text = (self.visuals / 'js/ui.js').read_text(encoding='utf-8')
            # Pi stream/remote skip controls have no role in this browser player.
            start, end = text.index('// STREAM_OVERRIDE_UI'), text.index('// WAVE_GAIN_UI')
            # Controls live in the player document; the renderer stays in its frame.
            return self.content('const document = window.parent.document;\n' + text[:start] + text[end:], 'text/javascript')
        if path.startswith("/visualizer/"):
            asset = (self.visuals / path.removeprefix("/visualizer/")).resolve()
            if asset.is_relative_to(self.visuals.resolve()) and asset.is_file() and asset.suffix in (".js", ".css"):
                return self.content(asset.read_bytes(), "text/javascript" if asset.suffix == ".js" else "text/css")
        return self.send_error(404)

    def radio_stream(self):
        if self.radio is None:
            return self.send_error(503, 'Radio output unavailable')
        listener = None if self.command == 'HEAD' else self.radio.subscribe()
        if self.command != 'HEAD' and listener is None:
            return self.send_error(503, 'Radio listener capacity reached')
        self.close_connection = True
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'audio/mpeg')
            self.send_header('Accept-Ranges', 'none')
            self.send_header('Connection', 'close')
            self.send_header('icy-name', 'Shuffle Library Radio')
            self.end_headers()
            if self.command == 'HEAD': return
            self.connection.settimeout(15)
            while True:
                try: chunk = listener.get(timeout=20)
                except queue.Empty: break
                if chunk is None: break
                self.wfile.write(chunk)
                self.wfile.flush()
        except OSError:
            pass
        finally:
            if listener is not None:
                self.radio.unsubscribe(listener)

    def media(self, route, quality='original'):
        try:
            ident = int(route.removeprefix("/media/"))
            if not 0 < ident < 2**63: raise ValueError()
            path = self.library.track(ident)
            if path is None: return self.send_error(404)
            if quality == 'mp3':
                if self.mp3_cache is None:
                    raise PlaybackConversionError('MP3 conversion unavailable')
                file = self.mp3_cache.open(path)
            else:
                file = path.open("rb")
        except PlaybackConversionError:
            return self.send_error(503, 'MP3 conversion unavailable. Try original playback.')
        except (ValueError, OSError):
            return self.send_error(404, "Track unavailable; index entry retained")
        with file:
            size = os.fstat(file.fileno()).st_size
            start, end = 0, size - 1
            header = self.headers.get("Range")
            if header:
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
                if not match or not any(match.groups()): return self.bad_range(size)
                a, b = match.groups()
                if a:
                    start, end = int(a), min(int(b), size - 1) if b else size - 1
                else:
                    start = max(0, size - int(b))
                if start > end or start >= size: return self.bad_range(size)
            self.send_response(206 if header else 200)
            self.send_header("Content-Type", 'audio/mpeg' if quality == 'mp3' else (mimetypes.guess_type(path.name)[0] or "application/octet-stream"))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if header: self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if self.command == "HEAD": return
            file.seek(start)
            remaining = end - start + 1
            try:
                while remaining:
                    chunk = file.read(min(65536, remaining))
                    if not chunk: break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError): pass

    def bad_range(self, size):
        self.send_response(416)
        self.send_header("Content-Range", f"bytes */{size}")
        self.send_header("Content-Length", "0")
        self.end_headers()


if __name__ == "__main__":
    from radio import LibraryRadio
    Handler.library = Library(os.environ.get("JUKEBOX_DB_PATH", "/data/jukebox.db"), os.environ.get("JUKEBOX_MUSIC_ROOT", "/mnt/lossless"))
    Handler.visuals = Path(os.environ.get("SHUFFLIZER_ROOT", "/app/visualizer"))
    Handler.mp3_cache = Mp3Cache(os.environ.get('PLAYBACK_CACHE', '/cache'), os.environ.get('FFMPEG_BINARY', 'ffmpeg'))
    Handler.radio = LibraryRadio(Handler.library, os.environ.get('FFMPEG_BINARY', 'ffmpeg'),
                                start_paused=os.environ.get('SHUFFLE_START_PAUSED') == '1')
    key_file = os.environ.get('SHUFFLE_OWNER_KEY_FILE')
    Handler.owner_auth = OwnerAuth(Path(key_file).read_text().strip() if key_file else '')
    class LanHandler(Handler):
        control_access = True
    lan = ThreadingHTTPServer(('0.0.0.0', 8081), LanHandler)
    threading.Thread(target=lan.serve_forever, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
