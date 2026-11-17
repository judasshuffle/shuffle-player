"""Create two synthetic tagged tracks, then add that sample album to the NAS.

Run on GreatATuin. No production container changes or writable music mounts.
"""
from pathlib import Path
import shutil
import subprocess

root = Path('/volume1/docker/shuffle-sources-preview')
output = root / 'sample-album'
output.mkdir(exist_ok=True)
docker = '/usr/local/bin/docker'
for number, frequency in ((1, 330), (2, 440)):
    name = f'{number:02}-preview-tone.flac'
    if not (output / name).exists():
        subprocess.run([docker, 'run', '--rm', '--network', 'none', '--read-only',
                        '--cap-drop=ALL', '--security-opt=no-new-privileges',
                        '--mount', f'type=bind,source={output},target=/out',
                        '--entrypoint', 'ffmpeg', 'shuffle-player:sources-preview-20261117',
                        '-v', 'error', '-f', 'lavfi', '-i', f'sine=frequency={frequency}:duration=30',
                        '-metadata', 'artist=Shuffle Preview Sample',
                        '-metadata', 'album=Shuffle Preview Sample',
                        '-metadata', f'title=Preview tone {number}',
                        '-metadata', f'track={number}', '-c:a', 'flac', '/out/' + name], check=True)
album = Path('/volume1/Media/Media/LOSSLESS/Shuffle Preview Sample')
album.mkdir(exist_ok=True)
for source in output.glob('*.flac'):
    target = album / source.name
    if target.exists():
        assert target.read_bytes() == source.read_bytes(), 'Existing sample differs; refusing overwrite'
    else:
        with target.open('xb') as dest, source.open('rb') as src:
            shutil.copyfileobj(src, dest)
print('Added two synthetic sample tracks; player music mount remains read-only.')
