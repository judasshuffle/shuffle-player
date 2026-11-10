"""Verify NAS listeners and preserved public addresses before router cutover."""
import hashlib
import json
import subprocess
import time
from urllib.request import Request, urlopen

BASE = 'http://192.168.68.81:8001'
PUBLIC = 'http://shuffle.tplinkdns.com:8001'
deadline = time.monotonic() + 60
while True:
    try:
        with urlopen(BASE + '/api/listening', timeout=5) as response:
            addresses = json.load(response)
        break
    except OSError:
        if time.monotonic() > deadline: raise
        time.sleep(1)
assert addresses['mp3_radio'] == PUBLIC + '/stream.mp3'
assert addresses['player'] == PUBLIC + '/'
assert addresses['lossless_track'] == PUBLIC + '/media/{id}?quality=original'
with urlopen(Request(BASE + '/', headers={'Host':'shuffle.tplinkdns.com:8001'}), timeout=15) as response:
    html = response.read()
    assert b'id="quality"' in html and b'id="originalLink"' in html
    assert PUBLIC.encode() + b'/stream.mp3' in html
with urlopen(Request(BASE + '/stream.mp3', method='HEAD'), timeout=15) as response:
    assert response.headers['Content-Type'] == 'audio/mpeg'
print('Preserved public address, player and direct MP3 listener: OK')

# Both clients join the same on-demand station; neither needs a browser or the Pi.
first = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', BASE + '/stream.mp3',
    '-t', '8', '-f', 'null', '-'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
try:
    time.sleep(1)
    joined = subprocess.run(['ffmpeg', '-v', 'error', '-i', BASE + '/stream.mp3',
        '-t', '3', '-f', 'null', '-'], capture_output=True, timeout=30)
    assert joined.returncode == 0, joined.stderr.decode(errors='replace')
    _, errors = first.communicate(timeout=30)
    assert first.returncode == 0, errors.decode(errors='replace')
finally:
    if first.poll() is None:
        first.kill(); first.wait()
print('Continuous MP3 decode and second listener joining midstream: OK')

digest = hashlib.sha256()
with urlopen(BASE + '/media/1134?quality=original', timeout=30) as response:
    assert response.headers['Content-Type'] == 'audio/flac'
    while chunk := response.read(1024 * 1024): digest.update(chunk)
assert digest.hexdigest() == '73213176644d35c839a23711708cdf22816679f78af0a4d2148e399e6d837762'
with urlopen(Request(BASE + '/media/1134?quality=original', headers={'Range':'bytes=0-4095'}), timeout=15) as response:
    assert response.status == 206 and response.read()[:4] == b'fLaC'
print('Direct original FLAC bytes and seeking through port 8001: OK')
with urlopen('http://192.168.68.81:8094/api/search?q=Dylan', timeout=15) as response:
    assert json.load(response)['tracks']
print('Existing LAN player on port 8094 retained: OK')
