"""Setup dialogue demonstration: all filesystem access stays in generated fixtures.

No production scanner is imported or executed. Confirmation simulates a job only.
"""
from contextlib import closing
import hashlib
import json
from pathlib import Path, PurePosixPath
import secrets
import sqlite3
import tempfile
import wave

CONNECT = sqlite3.connect
REQUIRED = {"path", "artist", "album", "title", "tracknumber", "year", "genre",
            "duration", "bitrate", "samplerate", "channels", "mtime", "size",
            "ext", "added_at", "updated_at"}


class SetupDemo:
    def __init__(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="shuffle-setup-demo-")
        self.root = Path(self.temporary.name)
        self.music = self.root / "music"
        self.music.mkdir()
        (self.music / ".preview-library-id").write_text("synthetic-library")
        for name in ("unchanged.wav", "changed.wav", "new.wav"):
            with wave.open(str(self.music / name), "wb") as audio:
                audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                audio.writeframes(b"\0\0" * 800)
        self.pending = {}
        self.create_fixture("existing", "/music")
        self.create_fixture("different-path", "/mnt/lossless")
        self.create_fixture("incompatible", "/music", incompatible=True)

    def close(self):
        self.temporary.cleanup()

    def create_fixture(self, name, prefix, incompatible=False):
        # Creation occurs ONLY in this newly allocated temporary directory.
        with closing(CONNECT(self.root / (name + ".db"))) as con:
            if incompatible:
                con.execute("CREATE TABLE tracks(path TEXT PRIMARY KEY)")
            else:
                columns = ', '.join('"' + c + '" ' + ("INTEGER" if c in
                    {"mtime", "size", "added_at", "updated_at"} else "TEXT") for c in sorted(REQUIRED))
                con.execute("CREATE TABLE tracks (" + columns + ")")
                for filename in ("unchanged.wav", "changed.wav", "missing.wav"):
                    file = self.music / filename
                    stat = file.stat() if file.exists() else None
                    con.execute("INSERT INTO tracks(path,mtime,size,added_at) VALUES(?,?,?,?)",
                                (prefix + "/" + filename,
                                 int(stat.st_mtime) if stat and filename == "unchanged.wav" else 0,
                                 stat.st_size if stat else 0, 123))
            con.commit()

    def validate(self, selection):
        mode = selection.get("mode")
        fixture = selection.get("fixture", "existing")
        container_path = selection.get("music_path", "/music")
        if mode not in ("existing", "new") or fixture not in ("existing", "different-path", "incompatible"):
            return {"ok": False, "error": "Choose an offered demo index and mode."}
        path = PurePosixPath(container_path)
        if not path.is_absolute() or ".." in path.parts or str(path) == "/":
            return {"ok": False, "error": "Use a specific absolute container path, such as /music."}
        try:
            available = self.music.is_dir() and (self.music / ".preview-library-id").read_text() == "synthetic-library"
        except OSError:
            available = False
        if selection.get("unavailable") or not available:
            return {"ok": False, "error": "Library unavailable or identity check failed. No scan or index change permitted."}
        db = self.root / (fixture + ".db")
        report = {"ok": True, "demo": True, "mode": mode, "schema_changed": False,
                  "scan_started": False, "missing_policy": "Retain all missing-track entries."}
        fingerprint = None
        if mode == "existing":
            # immutable prevents journal/lock creation. Never use on an active WAL database.
            # A real adapter must require a consistent, quiescent snapshot first.
            if any(Path(str(db) + suffix).exists() for suffix in ("-wal", "-journal")):
                return {"ok": False, "error": "Active journal detected. Validation requires a consistent offline snapshot; no files changed."}
            fingerprint = hashlib.sha256(db.read_bytes()).hexdigest()
            with closing(CONNECT(db.as_uri() + "?mode=ro&immutable=1", uri=True)) as con:
                con.execute("PRAGMA query_only=ON")
                columns = {row[1] for row in con.execute("PRAGMA table_info(tracks)")}
                if not REQUIRED.issubset(columns):
                    return {"ok": False, "error": "Index schema incompatible. No migration or rebuild offered.",
                            "missing_columns": sorted(REQUIRED - columns)}
                rows = con.execute("SELECT path,mtime,size FROM tracks").fetchall()
            mismatches = [value for value, _, _ in rows if not isinstance(value, str) or
                          not PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts or
                          not PurePosixPath(value).is_relative_to(path)]
            if mismatches:
                return {"ok": False, "error": "Stored paths do not match the container music path. Change the mount target; do not rewrite the index.",
                        "example_stored_path": mismatches[0], "scan_started": False}
            counts = dict(unchanged=0, changed=0, new=0, missing_retained=0)
            indexed = set()
            for value, mtime, size in rows:
                relative = PurePosixPath(value).relative_to(path)
                actual = self.music.joinpath(*relative.parts)
                indexed.add(relative.as_posix())
                if not actual.exists():
                    counts["missing_retained"] += 1
                else:
                    stat = actual.stat()
                    counts["unchanged" if mtime != 0 and int(stat.st_mtime) == mtime and stat.st_size == size else "changed"] += 1
            counts["new"] = sum(p.name not in indexed for p in self.music.glob("*.wav"))
            report.update(track_count=len(rows), plan=counts, sha256=fingerprint)
        else:
            report["message"] = "New-library mode selected. No index created. First indexing requires explicit confirmation; this demo only simulates it."
        token = secrets.token_urlsafe(24)
        self.pending[token] = (dict(selection), fingerprint)
        report["confirmation_token"] = token
        return report

    def confirm(self, request):
        if request.get("confirmed") is not True:
            return {"ok": False, "error": "Explicit confirmation is required. Nothing started."}
        pending = self.pending.pop(request.get("token"), None)
        if pending is None:
            return {"ok": False, "error": "Validate again before confirming."}
        selection, fingerprint = pending
        result = self.validate(selection)
        self.pending.pop(result.get("confirmation_token"), None)
        if not result["ok"]:
            return result
        if fingerprint and result.get("sha256") != fingerprint:
            return {"ok": False, "error": "Index changed since validation. Validate again."}
        return {"ok": True, "simulated": True, "scan_started": False,
                "message": "Confirmation accepted for demonstration. No scanner executed and no database created or changed."}
