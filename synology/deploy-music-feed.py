"""Run on GreatATuin with one explicitly staged application directory argument.
Only replaces Compose service player. Never restarts NAS, Docker or DarkRide.
Existing owner key is read in place for signed queue recovery; never copied/logged.
"""
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path('/volume1/docker/shuffle-player')
DOCKER = '/usr/local/bin/docker'

def deployment_images(stage):
    suffix = hashlib.sha256(str(stage.resolve()).encode()).hexdigest()[:20]
    return ('shuffle-player:music-feed-' + suffix,
            'shuffle-player:music-feed-rollback-' + suffix)


def compose_with_image(text, image):
    """Replace only player.image in the staged/deployed Compose layout."""
    lines = text.splitlines(keepends=True)
    player = next((i for i, line in enumerate(lines)
                   if re.fullmatch(r'  player:\s*(?:#.*)?', line.rstrip('\r\n'))), None)
    if player is None:
        raise ValueError('Compose player service missing')
    matches = []
    for i in range(player + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line.lstrip().startswith('#'):
            if len(line) - len(line.lstrip(' ')) <= 2:
                break
        if re.match(r'^    image:', line):
            matches.append(i)
    if len(matches) != 1:
        raise ValueError('Expected one player image field')
    lines[matches[0]] = '    image: ' + image + '\n'
    return ''.join(lines)


def pin_rollback_image(old_image, rollback_image, compose):
    subprocess.run([DOCKER, 'tag', old_image, rollback_image], check=True)
    compose.write_text(compose_with_image(compose.read_text(), rollback_image))


def inspect(name):
    return json.loads(subprocess.check_output([DOCKER, 'inspect', name], text=True))[0]


def restore(saved, control):
    if not saved.get('queue'): return
    resume = {'mode':saved['mode'], 'query':saved.get('filter_query', ''),
              'index':saved['index'], 'position':saved['position']}
    if 'queue_kinds' in saved:
        resume['kinds'] = saved['queue_kinds']
    restored = control('replace', ids=[t['id'] for t in saved['queue']],
                       album=saved['mode'] == 'album', resume_program=resume)
    if 'queue_kinds' not in restored:
        # Previous APIs lack atomic cursor/kind recovery. Retain the intended
        # queue; never call program/shuffle to hide an unsupported filter hint.
        control('select', index=saved['index'])
        control('seek', position=saved['position'])
    visual=saved.get('visualizer', {})
    if visual.get('bank') and visual.get('preset'): control('visualizer', **visual)
    if not saved['playing']: control('toggle')


def verify_recovery(saved, final, allow_legacy=False):
    limitations = []
    if (final.get('current') != saved.get('current') or
            final['playing'] != saved['playing'] or final['visualizer'] != saved['visualizer']):
        raise RuntimeError('Recovery current track, playback state or preset mismatch')
    ids = lambda state: [track['id'] for track in state.get('queue', [])]
    if ids(final)[:len(saved.get('queue', []))] != ids(saved):
        raise RuntimeError('Recovery ordered queue mismatch')
    if final['mode'] != saved['mode'] or final['filter_query'] != saved['filter_query']:
        if (allow_legacy and 'queue_kinds' not in final and saved['mode'] == 'filter' and
                final['mode'] == 'library' and final['filter_query'] == ''):
            limitations.append('Previous API cannot retain the saved filter; ordered queue retained, '
                               'but future top-ups use the full library.')
        elif (allow_legacy and 'queue_kinds' not in final and saved['mode'] == final['mode'] == 'album' and
              final['filter_query'] == ''):
            limitations.append('Previous API retained album mode and queue but cannot retain the album query label.')
        else:
            raise RuntimeError('Recovery programme mode or filter mismatch')
    if 'queue_kinds' in final:
        expected = saved.get('queue_kinds', ['recovered'] * len(saved.get('queue', [])))
        if final['queue_kinds'][:len(expected)] != expected:
            raise RuntimeError('Recovery queue kinds mismatch')
        if 'queue_kinds' not in saved:
            limitations.append('Original queue kinds were not captured; entries restored as recovered.')
    elif allow_legacy:
        limitations.append('Previous API cannot retain queue kinds; retained entries may be treated as requests.')
    else:
        raise RuntimeError('Recovery API did not return queue kinds')
    return limitations


def main(stage):
    stage = stage.resolve()
    assert stage.parent == ROOT and stage.name.startswith('incoming-music-feed-'), 'Unexpected staging directory'
    image, rollback_image = deployment_images(stage)
    files = ['.dockerignore', 'compose.yaml', 'synology/Dockerfile', 'synology/server.py',
             'synology/radio.py', 'synology/dr-screen.html', 'synology/dr-screen.js',
             'synology/dr-screen-entity.js', 'synology/music-features.js', 'synology/music-telemetry.js']
    assert all((stage / name).is_file() for name in files), 'Incomplete staged update'
    compose = stage / 'compose.yaml'
    compose.write_text(compose_with_image(compose.read_text(), image))

    # Complete the build context from public application files only.
    dependencies = ['fixtures.py', 'index.html', 'app.js', 'palette.js', 'station.js',
                    'dr-remote.html', 'dr-remote.js', 'dr-dj.js', 'owner.js', 'sha256.js', 'sha256-LICENSE.txt']
    for name in dependencies:
        shutil.copy2(ROOT / 'synology' / name, stage / 'synology' / name)
    shutil.copytree(ROOT / 'web' / 'shufflizer', stage / 'web' / 'shufflizer')
    subprocess.run([DOCKER, 'build', '-t', image, '-f', 'synology/Dockerfile', '.'], cwd=stage, check=True)

    base = 'http://192.168.68.81:8094'
    key = (ROOT / 'secrets' / 'owner-key').read_text().strip()

    def signed(route, payload=None):
        with urlopen(base + '/api/owner-challenge', timeout=15) as response:
            epoch = json.load(response)['epoch']
        body = json.dumps(payload).encode() if payload is not None else b''
        method, stamp, nonce = ('POST' if payload is not None else 'GET'), str(int(time.time())), secrets.token_hex(16)
        canonical = '\n'.join((method, route, epoch, stamp, nonce, hashlib.sha256(body).hexdigest())).encode()
        headers = {'X-Shuffle-Epoch':epoch, 'X-Shuffle-Time':stamp, 'X-Shuffle-Nonce':nonce,
                   'X-Shuffle-Signature':hmac.new(key.encode(), canonical, hashlib.sha256).hexdigest()}
        if payload is not None: headers['Content-Type'] = 'application/json'
        with urlopen(Request(base + route, data=body if payload is not None else None, headers=headers, method=method), timeout=30) as response:
            return json.load(response)

    def wait():
        for _ in range(45):
            try: return signed('/api/station')
            except Exception: time.sleep(1)
        raise RuntimeError('Shufflizer did not return after restart')

    def control(action, **payload):
        return signed('/api/station/control', dict(action=action, **payload))

    old = inspect('shuffle-player-player-1')
    domain = inspect('darkride-synology')
    saved = signed('/api/station')
    assert saved.get('queue_start') == 0 and len(saved.get('queue', [])) == saved['queue_count'], 'Cannot capture complete queue; refusing restart'
    if 'queue_kinds' in saved:
        assert len(saved['queue_kinds']) == saved['queue_count'], 'Incomplete queue kinds; refusing restart'
    backup = ROOT / ('before-music-feed-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + image.rsplit('-', 1)[-1])
    backup.mkdir()
    (backup / 'station.json').write_text(json.dumps(saved))
    (backup / 'image.txt').write_text(old['Image'])
    (backup / 'darkride.json').write_text(json.dumps({'id':domain['Id'], 'started':domain['State']['StartedAt']}))
    for name in files:
        source = ROOT / name
        if source.exists():
            target = backup / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    print('BACKUP', backup, 'queue', saved['queue_count'], 'mode', saved['mode'], flush=True)

    try:
        for name in files:
            shutil.copy2(stage / name, ROOT / name)
        subprocess.run([DOCKER, 'compose', 'config', '--quiet'], cwd=ROOT, check=True)
        subprocess.run([DOCKER, 'compose', 'up', '-d', '--no-deps', '--no-build', 'player'], cwd=ROOT, check=True)
        wait()
        restore(saved, control)
        final = signed('/api/station')
        limitations = verify_recovery(saved, final)
        new = inspect('shuffle-player-player-1')
        assert new['HostConfig']['ReadonlyRootfs']
        assert new['HostConfig']['PortBindings'] == old['HostConfig']['PortBindings']
        mounts = lambda c: sorted((m['Source'], m['Destination'], m['RW']) for m in c['Mounts'])
        assert mounts(new) == mounts(old) and not any(m['RW'] for m in new['Mounts'])
        assert (ROOT / 'secrets' / 'owner-key').read_text().strip() == key
        for name in ['music-features.js', 'music-telemetry.js', 'dr-screen.js', 'dr-screen-entity.js']:
            with urlopen('http://192.168.68.81:8001/' + name, timeout=15) as response:
                assert hashlib.sha256(response.read()).digest() == hashlib.sha256((stage / 'synology' / name).read_bytes()).digest()
    except Exception:
        for name in files:
            if (backup / name).exists(): shutil.copy2(backup / name, ROOT / name)
            elif (ROOT / name).exists():
                target = backup / 'failed-new' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(ROOT / name), str(target))
        pin_rollback_image(old['Image'], rollback_image, ROOT / 'compose.yaml')
        subprocess.run([DOCKER, 'compose', 'up', '-d', '--no-deps', '--no-build', 'player'], cwd=ROOT, check=True)
        wait()
        restore(saved, control)
        rolled_back = signed('/api/station')
        rollback_limitations = verify_recovery(saved, rolled_back, allow_legacy=True)
        if inspect('shuffle-player-player-1')['Image'] != old['Image']:
            raise RuntimeError('Rollback image ID mismatch')
        print(json.dumps({'result':'ROLLED_BACK', 'image':old['Image'],
                          'limitations':rollback_limitations}), flush=True)
        raise
    finally:
        after = inspect('darkride-synology')
        assert (after['Id'], after['State']['StartedAt']) == (domain['Id'], domain['State']['StartedAt']) and after['State']['Running'], 'DarkRide uptime changed'

    print(json.dumps({'result':'DEPLOYED', 'image':new['Image'], 'backup':str(backup),
                      'queue_count':final['queue_count'], 'current':final['current']['title'],
                      'position':round(final['position'], 2), 'mode':final['mode'],
                      'filter_query':final['filter_query'], 'playing':final['playing'],
                      'limitations':limitations, 'darkrideUnchanged':True}), flush=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]))
