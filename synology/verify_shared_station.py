"""Live shared-station check; changes only the in-memory radio queue/playback."""
import json
import subprocess
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import numpy as np

LAN = 'http://192.168.68.81:8094'
PUBLIC = 'http://shuffle.tplinkdns.com:8001'

def get(base, route):
    with urlopen(base + route, timeout=45) as response:
        return json.load(response)

deadline = time.monotonic() + 90
while True:
    try:
        state = get(LAN, '/api/station')
        assert state['can_control']
        break
    except (OSError, AssertionError):
        if time.monotonic() > deadline: raise
        time.sleep(1)
token = state['control_token']

def command(action, **payload):
    body = json.dumps({'action':action, **payload}).encode()
    request = Request(LAN + '/api/station/control', data=body,
        headers={'Content-Type':'application/json', 'X-Shuffle-Control':token, 'Origin':LAN})
    with urlopen(request, timeout=45) as response: return json.load(response)

public = get(PUBLIC, '/api/station')
assert not public['can_control'] and 'control_token' not in public
try:
    urlopen(Request(PUBLIC + '/api/station/control', data=b'{"action":"next"}',
        headers={'Content-Type':'application/json','X-Shuffle-Control':token}), timeout=15)
    raise AssertionError('Public control must be rejected')
except HTTPError as error: assert error.code == 403

tracks, offset = [], 0
while True:
    result = get(LAN, '/api/search?q=play%2070s%20Bob%20Dylan&offset=' + str(offset))
    tracks.extend(track for track in result['tracks'] if track['available'])
    if not result['has_more']: break
    offset += 50
ids = [1134] + [track['id'] for track in tracks if track['id'] != 1134]
state = command('replace', ids=ids)
assert state['current']['id'] == 1134 and state['playing'] and state['queue_count'] == len(ids)
state = command('seek', position=30)
assert 30 <= state['position'] < 32

def pcm(url, seconds, start=None):
    args = ['ffmpeg','-hide_banner','-loglevel','error']
    if start is not None: args += ['-ss',str(start)]
    args += ['-i',url,'-t',str(seconds),'-vn','-ac','1','-af','lowpass=f=40','-ar','500','-f','s16le','pipe:1']
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=55, check=True)
    return np.frombuffer(result.stdout, dtype='<i2').astype(np.float64)

def verify_audio():
    before = get(LAN, '/api/station')
    ident = before['current']['id']
    capture = pcm(PUBLIC + '/stream.mp3', 6)
    start = max(0, before['position'] - 8)
    reference = pcm(LAN + '/media/' + str(ident), 24, start)
    assert len(capture) > 2500 and np.std(capture) > 10, 'Public stream must contain audible music'
    scores = np.correlate(reference, capture, mode='valid')
    energy = np.convolve(reference ** 2, np.ones(len(capture)), mode='valid')
    normalized = scores / np.sqrt(np.maximum(energy * np.sum(capture ** 2), 1))
    similarity = float(np.max(normalized))
    assert similarity > .80, f'Public audio does not match selected original: {similarity}'
    print('Public audio matches selected library track:', ident, before['current']['title'], 'correlation', round(similarity,4))
    remote = get(PUBLIC, '/api/station')
    assert remote['current']['id'] == ident

verify_audio()
state = command('next')
assert state['current']['id'] == ids[1]
command('seek', position=30)
verify_audio()
paused = command('toggle')
assert not paused['playing']
time.sleep(.2)
assert abs(get(LAN, '/api/station')['position'] - paused['position']) < .01
command('toggle')
state = command('select', index=0)
print('Ready:', LAN, 'current:', state['current']['title'], 'queue:',state['queue_count'])
print('Public stream preserved; public controls rejected; NAS queue, seek, next and pause verified.')
