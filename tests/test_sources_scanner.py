"""Incremental scanner regression tests; no NAS writes."""
from contextlib import closing
import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
spec = importlib.util.spec_from_file_location('incremental', ROOT / 'scripts/update_index_sqlite.py')
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


class IncrementalTests(unittest.TestCase):
    def test_add_skip_change_retain_and_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            music = root / 'music'
            music.mkdir()
            track = music / 'sample.flac'
            track.write_bytes(b'first')
            database = root / 'working.db'
            with closing(sqlite3.connect(database)) as db:
                scanner.ensure_schema(db)
                db.commit()
            tags = {'artist':'Sample artist', 'album':'Sample album', 'title':'First title',
                    'tracknumber':1, 'year':2026, 'genre':'Test', 'duration':30,
                    'bitrate':1000, 'samplerate':44100, 'channels':1}
            with patch.object(scanner, 'read_tags', return_value=tags) as read:
                self.assertEqual(scanner.scan(database, music)['added'], 1)
                read.reset_mock()
                again = scanner.scan(database, music)
                self.assertEqual((again['added'], again['updated'], again['unchanged']), (0,0,1))
                read.assert_not_called()
                track.write_bytes(b'changed audio and tags')
                tags['title'] = 'Changed title'
                self.assertEqual(scanner.scan(database, music)['updated'], 1)
                with closing(sqlite3.connect(database)) as db:
                    self.assertEqual(db.execute('SELECT title FROM tracks').fetchone()[0], 'Changed title')
                track.unlink()
                self.assertEqual(scanner.scan(database, music)['total'], 1)
                track.write_bytes(b'reappeared')
                with patch.object(scanner, 'read_tags', side_effect=OSError('NAS disconnected')):
                    with self.assertRaises(OSError): scanner.scan(database, music)
                with closing(sqlite3.connect(database)) as db:
                    self.assertEqual(db.execute('SELECT title FROM tracks').fetchone()[0], 'Changed title')


if __name__ == '__main__':
    unittest.main()
