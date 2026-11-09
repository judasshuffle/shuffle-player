"""Read-only indexed library and browser media service. No indexing endpoints."""
from contextlib import closing
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent


def interpret(query):
    text = query.strip()
    command = re.match(r"^(play|queue)\s+", text, re.I)
    if command:
        text = text[command.end():].strip()
    decade = re.match(r"^(\d{2}|\d{4})s(?:\s+|$)", text, re.I)
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
                 "available": self.resolve(r["path"]).is_file()} for r in rows]

    def shuffle_batch(self, after=0):
        # Keyset pagination reads indexed rows only; it does not enumerate folders.
        with self.connect() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute("SELECT rowid AS id,path,artist,album,title FROM tracks "
                               "WHERE rowid>? ORDER BY rowid LIMIT 501", (after,)).fetchall()
        return {"tracks": self.describe(rows[:500]), "has_more": len(rows) > 500,
                "after": rows[499]["id"] if len(rows) >= 500 else after}

    def search(self, query="", offset=0):
        text, decade, artist_only = interpret(query)
        # Escape LIKE metacharacters; values always use bound parameters.
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = "%" + escaped + "%"
        where = "artist LIKE ? ESCAPE '\\'" if artist_only else (
            "(artist LIKE ? ESCAPE '\\' OR album LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\')")
        values = [pattern] if artist_only else [pattern] * 3
        info = {"artist": text if artist_only else None, "decade": decade,
                "message": f"Artist contains ‘{text}’; years {decade}–{decade + 9}. Review matches before playback."
                           if decade else "Review matches before playback."}
        with self.connect() as con:
            con.row_factory = sqlite3.Row
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

    def track(self, ident):
        with self.connect() as con:
            row = con.execute("SELECT path FROM tracks WHERE rowid=?", (ident,)).fetchone()
        return self.resolve(row[0]) if row else None


class Handler(SimpleHTTPRequestHandler):
    library = None
    visuals = None

    def end_headers(self):
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
        self.send_error(405, "Indexing and system controls are disabled")

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        if path in ("/api/search", "/api/shuffle"):
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
            return self.media(path)
        if path in ("/", "/app.js"):
            return self.content((HERE / ("index.html" if path == "/" else "app.js")).read_bytes(),
                                "text/html; charset=utf-8" if path == "/" else "text/javascript")
        if path == "/visualizer/index.html":
            text = (self.visuals / "index.html").read_text().replace('src="/js/main.js"', 'src="/visualizer/js/main.js"')
            text = re.sub(r'src="http[^\"]+"', '', text)
            text = text.replace('</head>', '<style>#audio,.audio-options{display:none!important}</style></head>')
            return self.content(text, "text/html; charset=utf-8")
        if path == "/visualizer/js/main.js":
            text = (self.visuals / "js/main.js").read_text()
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
        if path.startswith("/visualizer/"):
            asset = (self.visuals / path.removeprefix("/visualizer/")).resolve()
            if asset.is_relative_to(self.visuals.resolve()) and asset.is_file() and asset.suffix in (".js", ".css"):
                return self.content(asset.read_bytes(), "text/javascript" if asset.suffix == ".js" else "text/css")
        return self.send_error(404)

    def media(self, route):
        try:
            ident = int(route.removeprefix("/media/"))
            if not 0 < ident < 2**63: raise ValueError()
            path = self.library.track(ident)
            if path is None: return self.send_error(404)
            file = path.open("rb")
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
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
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
    Handler.library = Library(os.environ.get("JUKEBOX_DB_PATH", "/data/jukebox.db"), os.environ.get("JUKEBOX_MUSIC_ROOT", "/mnt/lossless"))
    Handler.visuals = Path(os.environ.get("SHUFFLIZER_ROOT", "/app/visualizer"))
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
