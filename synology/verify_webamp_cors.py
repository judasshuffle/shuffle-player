"""Check the actual Webamp anonymous-audio contract on LAN and public radio."""
import json
import subprocess
import time
from urllib.request import Request, urlopen

PUBLIC = 'http://shuffle.tplinkdns.com:8001/stream.mp3'
LAN = 'http://192.168.68.81:8001/stream.mp3'


def request(url, method, headers):
    return urlopen(Request(url, method=method, headers=headers), timeout=15)


deadline = time.monotonic() + 60
while True:
    try:
        with request(LAN, 'HEAD', {'Origin':'null'}) as response:
            ready = response.headers.get('Access-Control-Allow-Origin') == '*'
        if ready: break
    except OSError:
        pass
    if time.monotonic() > deadline: raise RuntimeError('Deployed radio CORS fix is not ready')
    time.sleep(1)

for url in (LAN, PUBLIC):
    for origin in ('null', 'https://darkride.example'):
        with request(url, 'HEAD', {'Origin':origin}) as response:
            assert response.status == 200
            assert response.headers['Content-Type'] == 'audio/mpeg'
            assert response.headers['Access-Control-Allow-Origin'] == '*'
            assert 'Access-Control-Allow-Credentials' not in response.headers
            assert 'Content-Length' not in response.headers
        with request(url, 'OPTIONS', {'Origin':origin, 'Access-Control-Request-Method':'GET',
                'Access-Control-Request-Headers':'icy-metadata, range'}) as response:
            assert response.status == 204
            assert response.headers['Access-Control-Allow-Origin'] == '*'
            allowed = response.headers['Access-Control-Allow-Headers'].lower()
            assert 'icy-metadata' in allowed and 'range' in allowed
    with request(url, 'GET', {'Origin':'null', 'Icy-MetaData':'1'}) as response:
        assert response.headers['Access-Control-Allow-Origin'] == '*'
        assert len(response.read(16384)) == 16384
    print('Webamp anonymous/qrc-origin HEAD, GET and preflight:', url, 'OK', flush=True)

probe = subprocess.run(['ffprobe', '-v', 'error', '-headers', 'Origin: null\r\n',
    '-show_entries', 'stream=codec_name,sample_rate,channels,bit_rate', '-of', 'json',
    '-read_intervals', '%+2', PUBLIC], capture_output=True, check=True, timeout=30)
stream = json.loads(probe.stdout)['streams'][0]
assert (stream['codec_name'], stream['sample_rate'], stream['channels'], stream['bit_rate']) == ('mp3', '44100', 2, '256000')
print('Public radio encoding unchanged:', json.dumps(stream), flush=True)
print('Protocol checks passed; actual DarkRide audible playback still requires its own retry.', flush=True)
