"""Linux preview guard checks. Run in the container through Python stdin."""
from contextlib import closing
import hashlib
import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest

module_path = Path('/app/sources.py')
if not module_path.exists():
    module_path = Path(__file__).resolve().parents[1] / 'synology/sources.py'
spec = importlib.util.spec_from_file_location('sources', module_path)
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)


@unittest.skipUnless(os.name == 'posix', 'Linux persistent file locks')
class GuardTests(unittest.TestCase):
    def test_seed_once_keeps_backup_and_working_changes(self):
        with tempfile.TemporaryDirectory(dir='/cache') as temp:
            root = Path(temp)
            backup = root / 'backup.db'
            with closing(sqlite3.connect(backup)) as db:
                db.execute('CREATE TABLE tracks(path TEXT PRIMARY KEY)')
                db.execute('INSERT INTO tracks VALUES (?)', ('original',))
                db.commit()
            before = hashlib.sha256(backup.read_bytes()).hexdigest()
            working = sources.seed_index(backup, root / 'working')
            with closing(sqlite3.connect(working)) as db:
                db.execute('INSERT INTO tracks VALUES (?)', ('new',))
                db.commit()
            sources.seed_index(backup, root / 'working')
            with closing(sqlite3.connect(working)) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM tracks').fetchone()[0], 2)
            self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), before)

    def test_unavailable_root_and_cross_process_lock_stop_before_backup(self):
        import fcntl
        with tempfile.TemporaryDirectory(dir='/cache') as temp:
            root = Path(temp)
            music = root / 'music'
            music.mkdir()
            scanner = sources.Scanner(root, SimpleNamespace(music=music), None)
            with self.assertRaises(ValueError): scanner.start()
            self.assertIn('NAS folder unavailable', scanner.status['error'])
            (music / 'album').mkdir()
            with (root / 'scan.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(ValueError): scanner.start()
            self.assertFalse((root / 'backups').exists())
            self.assertFalse(scanner.status['running'])
            self.assertFalse(scanner.guard.locked())


if __name__ == '__main__':
    unittest.main(verbosity=2)
