"""Run on NAS: verify persistence by restarting only the preview container."""
import json
from pathlib import Path
import subprocess
import time

DOCKER = '/usr/local/bin/docker'
NAME = 'shuffle-sources-preview-player-1'
ROOT = Path('/volume1/docker/shuffle-sources-preview')
verify = (ROOT / 'app/synology/verify_sources_preview.py').read_text()


def inside(code):
    script = "ns={'__name__':'verification'}\nexec(" + repr(verify) + ",ns)\ncall=ns['call']\n" + code
    return subprocess.check_output([DOCKER, 'exec', '-i', NAME, 'python', '-B', '-'], input=script, text=True)


for _ in range(60):
    try:
        inside("call('/api/sources')")
        break
    except subprocess.CalledProcessError:
        time.sleep(1)
else:
    raise RuntimeError('Preview is not ready')

before = json.loads(subprocess.check_output([DOCKER, 'inspect', 'shuffle-player-player-1'], text=True))[0]
working_hash = __import__('hashlib').sha256((ROOT / 'working/jukebox.db').read_bytes()).hexdigest()
print(inside("data=call('/api/sources')\nident=data['stations'][-1]['id']\ncall('/api/sources',{'action':'select','id':ident})\nprint('Saved external source selected')"), flush=True)
expected = json.loads((ROOT / 'settings/sources.json').read_text())['active']
subprocess.run([DOCKER, 'restart', NAME], check=True)
for _ in range(60):
    try:
        result = json.loads(inside("print(__import__('json').dumps(call('/api/station')))"))
        break
    except subprocess.CalledProcessError:
        time.sleep(1)
else:
    raise RuntimeError('Preview did not return after restart')
assert result['source'] == expected
assert __import__('hashlib').sha256((ROOT / 'working/jukebox.db').read_bytes()).hexdigest() == working_hash
print(inside("print('Restarted radio audio',ns['audio']())\ncall('/api/sources',{'action':'select','id':'library'})\nprint('Library audio',ns['audio']())"), flush=True)
after = json.loads(subprocess.check_output([DOCKER, 'inspect', 'shuffle-player-player-1'], text=True))[0]
assert (before['Id'], before['State']['StartedAt']) == (after['Id'], after['State']['StartedAt'])
mounts = json.loads(subprocess.check_output([DOCKER, 'inspect', NAME], text=True))[0]['Mounts']
assert all(not m['RW'] for m in mounts if m['Destination'] in ('/data', '/mnt/lossless', '/run/shuffle-owner'))
print('PASS: source restored after restart; working index unchanged; music/backup read-only; production container not restarted.')
