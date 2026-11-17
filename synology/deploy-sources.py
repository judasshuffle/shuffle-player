"""Promote Sources on GreatATuin, preserving a deliberately paused live station.

The caller must first verify/push the exact old code checkpoint to GitHub.
Only the live player is replaced; preview and DarkRide remain separate services.
"""
from contextlib import closing
import fcntl
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path('/volume1/docker/shuffle-player')
PREVIEW = Path('/volume1/docker/shuffle-sources-preview')
DOCKER = '/usr/local/bin/docker'
BASE = 'http://192.168.68.81:8094'
IMAGE = 'shuffle-player:sources-20261117'
EXPECTED_OLD_IMAGE = 'sha256:22216de8c1fa92ba98e13a454b16ca474ddd8757660b0e7b028dd79e81acb202'
BACKUP_HASH = '4de36d001b655efe282136ab9c7491ab7920d9034a4807b1afcde9769a152c3b'


def run(*args, **options):
    return subprocess.run(list(args), check=True, **options)


def inspect(name):
    return json.loads(subprocess.check_output([DOCKER, 'inspect', name], text=True))[0]


def main(stage):
    stage = stage.resolve()
    assert stage.parent == ROOT and stage.name.startswith('incoming-sources-'), 'Unexpected staging path'
    git_backup = (stage / 'git-backup-commit.txt').read_text().strip()
    assert len(git_backup) == 40 and all(c in '0123456789abcdef' for c in git_backup)
    spec = importlib.util.spec_from_file_location('recovery', stage / 'synology/deploy-music-feed.py')
    recovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recovery)
    old, domain = inspect('shuffle-player-player-1'), inspect('darkride-synology')
    assert old['Image'] == EXPECTED_OLD_IMAGE, 'Live image changed since its audited Git backup'
    assert hashlib.sha256((ROOT / 'data/jukebox.db').read_bytes()).hexdigest() == BACKUP_HASH
    key = (ROOT / 'secrets/owner-key').read_text().strip()

    def signed(route, payload=None, base=BASE):
        epoch = json.load(urlopen(base + '/api/owner-challenge', timeout=10))['epoch']
        body = json.dumps(payload).encode() if payload is not None else b''
        method, stamp, nonce = 'POST' if payload is not None else 'GET', str(int(time.time())), secrets.token_hex(16)
        canonical = '\n'.join((method, route, epoch, stamp, nonce, hashlib.sha256(body).hexdigest())).encode()
        headers = {'Content-Type':'application/json', 'X-Shuffle-Epoch':epoch, 'X-Shuffle-Time':stamp,
                   'X-Shuffle-Nonce':nonce, 'X-Shuffle-Signature':hmac.new(key.encode(), canonical, hashlib.sha256).hexdigest()}
        return json.load(urlopen(Request(base + route, data=body if payload is not None else None, headers=headers), timeout=30))

    def wait():
        for _ in range(90):
            try: return signed('/api/station')
            except Exception: time.sleep(1)
        raise RuntimeError('Live player did not become ready')

    saved = signed('/api/station')
    assert not saved['playing'], 'Live playback changed; this migration must preserve the deliberate pause'
    assert saved.get('source', 'library') == 'library'
    run(DOCKER, 'build', '-t', IMAGE, '-f', 'synology/Dockerfile', '.', cwd=stage)

    backup = ROOT / ('before-sources-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    backup.mkdir()
    (backup / 'station.json').write_text(json.dumps(saved))
    (backup / 'container.json').write_text(json.dumps(old))
    (backup / 'git-backup-commit.txt').write_text(git_backup + '\n')
    run(DOCKER, 'tag', old['Image'], 'shuffle-player:before-sources-20261117')
    files = json.loads((stage / 'deployment-files.json').read_text())
    for name in files:
        (stage / name).resolve().relative_to(stage)
        source = ROOT / name
        if source.is_file():
            target = backup / 'files' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    working, settings = ROOT / 'working', ROOT / 'settings'
    working.mkdir(exist_ok=True)
    settings.mkdir(exist_ok=True)
    # Promote the already-tested index into an independent live directory.
    # SQLite backup and the scanner's persistent lock keep this a consistent copy.
    with (PREVIEW / 'working/scan.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not (working / 'jukebox.db').exists():
            with closing(sqlite3.connect((PREVIEW / 'working/jukebox.db').as_uri() + '?mode=ro', uri=True)) as source, closing(sqlite3.connect(working / 'seed.tmp')) as target:
                source.backup(target)
                assert target.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            (working / 'seed.tmp').replace(working / 'jukebox.db')
            if (PREVIEW / 'working/scan.json').exists():
                shutil.copy2(PREVIEW / 'working/scan.json', working / 'scan.json')
            (working / 'backups').mkdir(exist_ok=True)
            for source in (PREVIEW / 'working/backups').glob('*.db'):
                shutil.copy2(source, working / 'backups' / source.name)
    if not (settings / 'sources.json').exists():
        sources = json.loads((PREVIEW / 'settings/sources.json').read_text()) if (PREVIEW / 'settings/sources.json').exists() else {'stations':[]}
        sources['active'] = 'library'  # Keep the live programme, not preview transport.
        (settings / 'sources.json').write_text(json.dumps(sources))
    if not (settings / 'connection.json').exists():
        env = dict(value.split('=', 1) for value in old['Config']['Env'] if '=' in value)
        public = env.get('PUBLIC_LISTENING_BASE', '').rstrip('/')
        connection = {'public_base':public, 'stream_url':public + '/stream.mp3' if public else '',
                      'screen_url':public + '/dr-screen' if public else '', 'internet_confirmed_at':0}
        (settings / 'connection.json').write_text(json.dumps(connection))
    with closing(sqlite3.connect(working / 'jukebox.db')) as db:
        total = db.execute('SELECT COUNT(*) FROM tracks').fetchone()[0]
        assert total >= 17623

    # Check the exact new image and paused recovery before publishing any ports.
    check_name = 'shuffle-sources-release-check-' + secrets.token_hex(4)
    command = [DOCKER, 'run', '-d', '--name', check_name, '--read-only', '--user', '1026:100',
               '--cap-drop=ALL', '--security-opt=no-new-privileges',
               '--tmpfs', '/cache:rw,noexec,nosuid,size=512m,uid=1026,gid=100,mode=0700']
    for source, dest, readonly in [(ROOT/'data','/data',True), (Path('/volume1/Media/Media/LOSSLESS'),'/mnt/lossless',True),
                                    (ROOT/'secrets','/run/shuffle-owner',True), (working,'/working',False), (settings,'/settings',False)]:
        command += ['--mount', 'type=bind,source=' + str(source) + ',target=' + dest + (',readonly' if readonly else '')]
    for value in ['SHUFFLE_WORKING_DIRECTORY=/working','SHUFFLE_SOURCE_DIRECTORY=/settings',
                  'SHUFFLE_OWNER_KEY_FILE=/run/shuffle-owner/owner-key','SHUFFLE_START_PAUSED=1','SHUFFLE_VISUALIZER_BANK=VLM']:
        command += ['-e', value]
    check_id = subprocess.check_output(command + [IMAGE], text=True).strip()
    try:
        # The preflight container has no published ports. Check paused startup
        # and search through its HTTP API using the existing in-container key.
        verify_code = (stage / 'synology/verify_sources_preview.py').read_text()
        script = "ns={'__name__':'preflight'}\nexec(" + repr(verify_code) + ",ns)\n"
        script += 'saved=' + repr(saved) + '\n'
        script += '''
import time
call=ns['call']
for _ in range(90):
    try:
        current=call('/api/station')
        break
    except Exception: time.sleep(1)
else: raise RuntimeError('Preflight startup failed')
assert not current['playing']
assert len(call('/api/search?q=Shuffle%20Preview%20Sample')['tracks'])==2
assert call('/api/sources')['can_control']
print('PREFLIGHT PASS: paused startup; working index/search; owner access',flush=True)
'''
        run(DOCKER, 'exec', '-i', check_id, 'python', '-B', '-', input=script, text=True)
    finally:
        run(DOCKER, 'rm', '-f', check_id, stdout=subprocess.DEVNULL)
    latest = signed('/api/station')
    assert not latest['playing'] and latest['current']['id'] == saved['current']['id'] and latest['version'] == saved['version'], 'Live station changed during preparation'
    assert inspect('shuffle-player-player-1')['Id'] == old['Id']
    print('BACKUP', str(backup), 'tracks', total, 'paused', True, flush=True)

    try:
        for name in files:
            target = ROOT / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stage / name, target)
        run(DOCKER, 'compose', 'config', '--quiet', cwd=ROOT)
        run(DOCKER, 'compose', 'up', '-d', '--no-deps', '--no-build', 'player', cwd=ROOT)
        assert not wait()['playing'], 'New station must start paused'
        final = signed('/api/station')
        assert not final['playing']
        new = inspect('shuffle-player-player-1')
        assert new['HostConfig']['ReadonlyRootfs'] and new['HostConfig']['PortBindings'] == old['HostConfig']['PortBindings']
        mounts = {item['Destination']:item for item in new['Mounts']}
        for destination in ('/data','/mnt/lossless','/run/shuffle-owner'):
            assert not mounts[destination]['RW']
        assert mounts['/working']['RW'] and mounts['/settings']['RW']
        assert mounts['/working']['Source'] == str(working) and mounts['/settings']['Source'] == str(settings)
        assert len(signed('/api/search?q=Shuffle%20Preview%20Sample')['tracks']) == 2
        with urlopen(Request('http://192.168.68.81:8001/stream.mp3', method='HEAD'), timeout=15) as response:
            assert response.status == 200 and response.headers['Content-Type'] == 'audio/mpeg'
        assert hashlib.sha256((ROOT / 'data/jukebox.db').read_bytes()).hexdigest() == BACKUP_HASH
        assert (ROOT / 'secrets/owner-key').read_text().strip() == key
        report = {'result':'DEPLOYED', 'image':new['Image'], 'backup':str(backup), 'git_backup':git_backup,
                  'playing':False, 'current':final['current']['title'], 'position':round(final['position'],2),
                  'queue_count':final['queue_count'], 'working_tracks':total, 'queue_disposable':True}
        (backup / 'deployment-result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)
    except Exception:
        for name in files:
            previous = backup / 'files' / name
            target = ROOT / name
            if previous.exists(): shutil.copy2(previous, target)
            elif target.exists():
                aside = backup / 'failed-new' / name
                aside.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(aside))
        compose = ROOT / 'compose.yaml'
        text = recovery.compose_with_image(compose.read_text(), 'shuffle-player:before-sources-20261117')
        text = text.replace('SHUFFLE_START_PAUSED: "0"', 'SHUFFLE_START_PAUSED: "1"')
        compose.write_text(text)
        run(DOCKER, 'compose', 'up', '-d', '--no-deps', '--no-build', 'player', cwd=ROOT)
        assert not wait()['playing']
        print('ROLLED BACK, kept paused. Previous station snapshot is in private backup: ' + str(backup), flush=True)
        raise
    finally:
        after = inspect('darkride-synology')
        assert (after['Id'], after['State']['StartedAt']) == (domain['Id'], domain['State']['StartedAt']) and after['State']['Running'], 'DarkRide uptime changed'


if __name__ == '__main__':
    main(Path(sys.argv[1]))
