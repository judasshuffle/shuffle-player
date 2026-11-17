"""Run inside the isolated preview only. Never controls the production station."""
import concurrent.futures
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = 'http://127.0.0.1:8081'
KEY = Path('/run/shuffle-owner/owner-key').read_text().strip()


def call(route, payload=None, signed=True):
    body = json.dumps(payload).encode() if payload is not None else b''
    headers = {'Content-Type': 'application/json'}
    method = 'POST' if payload is not None else 'GET'
    if signed:
        epoch = json.load(urlopen(BASE + '/api/owner-challenge'))['epoch']
        stamp, nonce = str(int(time.time())), secrets.token_hex(16)
        message = '\n'.join((method, route, epoch, stamp, nonce, hashlib.sha256(body).hexdigest())).encode()
        headers.update({'X-Shuffle-Epoch': epoch, 'X-Shuffle-Time': stamp, 'X-Shuffle-Nonce': nonce,
                        'X-Shuffle-Signature': hmac.new(KEY.encode(), message, hashlib.sha256).hexdigest()})
    return json.load(urlopen(Request(BASE + route, data=body if payload is not None else None, headers=headers), timeout=25))


def scan():
    call('/api/scan', {})
    for _ in range(600):
        result = call('/api/scan')
        if not result['running']:
            assert not result.get('error'), result
            print('scan', json.dumps(result), flush=True)
            return result
        time.sleep(1)
    raise AssertionError('Scan did not finish within ten minutes')


def audio():
    command = ['ffmpeg', '-nostdin', '-v', 'error', '-i', BASE + '/stream.mp3',
               '-t', '3', '-f', 's16le', '-ac', '1', '-ar', '8000', 'pipe:1']
    result = subprocess.run(command, capture_output=True, timeout=20)
    assert result.returncode == 0 and len(result.stdout) >= 40000, result.stderr.decode()
    import array
    samples = array.array('h', result.stdout)
    assert max(abs(x) for x in samples) > 100, 'Silent stream'
    return {'decoded_bytes': len(result.stdout), 'peak': max(abs(x) for x in samples)}


def main():
    assert Path('/working/jukebox.db').is_file(), 'Preview working index required'
    backup = Path('/data/jukebox.db')
    before = hashlib.sha256(backup.read_bytes()).hexdigest()
    with sqlite3.connect(backup.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        assert db.execute('SELECT COUNT(*) FROM tracks').fetchone()[0] == 17623
    try:
        call('/api/sources', {'action':'select', 'id':'library'}, signed=False)
        raise AssertionError('Unsigned source change accepted')
    except HTTPError as error:
        assert error.code == 403
    call('/api/sources', {'action':'select', 'id':'library'})
    print('library audio', audio(), flush=True)
    saved = call('/api/sources', {'action':'save', 'name':'Radio Paradise · preview',
                                'url':'https://stream.radioparadise.com/mp3-192'})
    ident = saved['stations'][-1]['id']
    assert call('/api/station')['source'] == 'library', 'Saving changed playback'
    try:
        call('/api/sources', {'action':'test', 'name':'Invalid station', 'url':BASE + '/sources'})
        raise AssertionError('HTML passed audio test')
    except HTTPError as error:
        assert error.code == 400
        assert b'Current source is still playing' in error.read()
    assert call('/api/station')['source'] == 'library'
    # Keep two actual HTTP listeners connected through both switches.
    with urlopen(BASE + '/stream.mp3', timeout=25) as one, urlopen(BASE + '/stream.mp3', timeout=25) as two:
        assert one.read(4096) and two.read(4096)
        call('/api/sources', {'action':'select', 'id':ident})
        assert call('/api/station')['source'] == ident
        print('external audio', audio(), flush=True)
        assert one.read(4096) and two.read(4096)
        call('/api/sources', {'action':'select', 'id':'library'})
        assert one.read(4096) and two.read(4096)
        print('returned library audio', audio(), flush=True)
    call('/api/station/control', {'action':'shuffle'})
    initial = call('/api/station')['current']['id']
    call('/api/station/control', {'action':'next'})
    assert call('/api/station')['current']['id'] != initial
    assert call('/api/search?q=Bob%20Dylan')['tracks']
    first = scan()
    sample = call('/api/search?q=Shuffle%20Preview%20Sample')['tracks']
    assert len(sample) == 2, sample
    second = scan()
    assert second['added'] == second['updated'] == 0, second
    with sqlite3.connect('/working/jukebox.db') as db:
        assert not db.execute('SELECT path FROM tracks GROUP BY path HAVING COUNT(*) > 1').fetchall()
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == before
    print('PASS: source switching, two continuous listeners, non-silent decode, failed test isolation, owner auth, search/shuffle/skip, two scans, backup preserved', flush=True)


if __name__ == '__main__':
    main()
