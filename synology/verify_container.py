"""Read-only checks run inside the deployed container."""
import hashlib
from pathlib import Path
import sqlite3

database = Path('/data/jukebox.db')
con = sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True)
print('Indexed tracks:', con.execute('SELECT COUNT(*) FROM tracks').fetchone()[0])
path, year = con.execute('SELECT path,year FROM tracks WHERE rowid=1134').fetchone()
digest = hashlib.sha256()
with Path(path).open('rb') as source:
    while chunk := source.read(1024 * 1024):
        digest.update(chunk)
print('Hurricane source year:', year, 'SHA256:', digest.hexdigest())
print('Database SHA256:', hashlib.sha256(database.read_bytes()).hexdigest())
