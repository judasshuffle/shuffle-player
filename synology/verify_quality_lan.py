"""Verify real, seekable MP3 compatibility delivery without modifying source data."""
import json
import subprocess
import time
from urllib.request import Request, urlopen

BASE = 'http://192.168.68.81:8094'
original = BASE + '/media/1134'
mp3 = original + '?quality=mp3'
deadline = time.monotonic() + 60
while True:
    try:
        with urlopen(BASE + '/', timeout=5) as response:
            html = response.read()
        assert b'id="quality"' in html and b'Lossless / original' in html
        break
    except OSError:
        if time.monotonic() > deadline:
            raise
        time.sleep(1)
with urlopen(Request(original, method='HEAD'), timeout=30) as response:
    assert response.headers['Content-Type'] == 'audio/flac'
print('Default lossless delivery: original FLAC')
started = time.monotonic()
with urlopen(Request(mp3, headers={'Range': 'bytes=0-4095'}), timeout=240) as response:
    prefix = response.read()
    assert response.status == 206 and len(prefix) == 4096
    assert response.headers['Content-Type'] == 'audio/mpeg'
    size = int(response.headers['Content-Range'].split('/')[-1])
print('Real MP3 conversion and range delivery:', size, 'bytes;', round(time.monotonic() - started, 2), 'seconds')
with urlopen(mp3, timeout=30) as response:
    data = response.read()
assert len(data) == size and data[:4096] == prefix
with urlopen(Request(mp3, headers={'Range':'bytes=-1024'}), timeout=30) as response:
    assert response.status == 206 and response.read() == data[-1024:]
with urlopen(Request(mp3, method='HEAD'), timeout=30) as response:
    assert int(response.headers['Content-Length']) == size

def probe(url):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
        'stream=codec_name,sample_rate,channels:format=duration', '-of', 'json', url],
        capture_output=True, check=True, timeout=60)
    return json.loads(result.stdout)

source, encoded = probe(original), probe(mp3)
stream = encoded['streams'][0]
assert (stream['codec_name'], stream['sample_rate'], stream['channels']) == ('mp3', '44100', 2)
assert abs(float(source['format']['duration']) - float(encoded['format']['duration'])) < .2
subprocess.run(['ffmpeg', '-v', 'error', '-ss', '90', '-i', mp3, '-t', '5', '-f', 'null', '-'],
               check=True, timeout=60)
print('MP3 codec, full duration, repeat/range requests and decoding from 90 seconds: OK')
