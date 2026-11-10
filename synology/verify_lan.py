"""Read-only LAN delivery checks; never scans folders or modifies the index."""
import hashlib
import json
from urllib.request import Request, urlopen
from urllib.parse import quote

BASE = 'http://192.168.68.81:8094'

def get(path, headers=None, method='GET'):
    return urlopen(Request(BASE + path, headers=headers or {}, method=method), timeout=60)

for path in ('/', '/app.js', '/palette.js', '/visualizer/js/ui.js', '/visualizer/index.html?embed=1',
             '/visualizer/js/main.js', '/visualizer/js/engine.js', '/visualizer/css/style.css'):
    with get(path) as response:
        assert response.status == 200 and response.read(), path
print('Player and embedded Shufflizer assets: OK')
with get('/visualizer/js/main.js') as response:
    script = response.read().decode()
    assert script.startswith('import "/palette.js";') and 'Ember test' not in script
print('Palette initialisation precedes visualizer UI: OK')
with get('/api/styles') as response:
    catalog = json.load(response)
assert len(catalog['styles']) >= 130
assert catalog['tagged'] == 15846 and catalog['untagged'] == 1777
counts = {style['name']: style['count'] for style in catalog['styles']}
for name in ('Blues', 'Jazz', 'Disco'):
    ids, offset = [], 0
    while True:
        with get('/api/search?q=' + quote('play genre ' + name) + '&offset=' + str(offset)) as response:
            page = json.load(response)
        assert page['style'] == name and not page.get('error')
        ids.extend(track['id'] for track in page['tracks'])
        if not page['has_more']:
            break
        offset += 50
    assert len(ids) == len(set(ids)) == counts[name] > 0
    print('Genre pagination:', name, len(ids), 'matches')
with get('/api/search?q=' + quote("play 70's genre disco")) as response:
    decade_style = json.load(response)
assert decade_style['decade'] == 1970 and decade_style['style'] == 'Disco'
print('Style catalogue and style + decade commands: OK')
with get('/api/search?q=play%2070s%20Bob%20Dylan') as response:
    result = json.load(response)
assert result['decade'] == 1970 and result['tracks'] and not result.get('error')
assert all(t['available'] for t in result['tracks'])
print('1970s Bob Dylan search:', len(result['tracks']), 'available matches')
decade_ids = None
for phrase in ("play 80's Dylan", 'play 80s Dylan', 'play 1980s Dylan'):
    ids, offset = [], 0
    while True:
        with get('/api/search?q=' + quote(phrase) + '&offset=' + str(offset)) as response:
            page = json.load(response)
        assert page['decade'] == 1980 and not page.get('error')
        ids.extend(t['id'] for t in page['tracks'])
        if not page['has_more']:
            break
        offset += 50
    assert ids and (decade_ids is None or ids == decade_ids)
    decade_ids = ids
print('All three 1980s command spellings:', len(decade_ids), 'identical matches')
with get('/artwork/' + str(decade_ids[0])) as response:
    assert response.status == 200 and response.headers['Content-Type'].startswith('image/')
    assert response.read()
with get('/artwork/999999999999999999999') as response:
    assert response.headers['Content-Type'] == 'image/svg+xml'
print('Real-library artwork and missing-artwork fallback: OK')
track = next(t for t in result['tracks'] if t['title'] == 'Hurricane')
route = '/media/' + str(track['id'])
with get(route, method='HEAD') as response:
    size = int(response.headers['Content-Length'])
    assert response.headers['Accept-Ranges'] == 'bytes'
    print('Audio HEAD:', response.status, response.headers['Content-Type'], size, 'bytes')
with get(route, {'Range': 'bytes=0-4095'}) as response:
    prefix = response.read()
    assert response.status == 206 and len(prefix) == 4096
    assert prefix[:4] == b'fLaC'
with get(route, {'Range': 'bytes=-4096'}) as response:
    suffix = response.read()
    assert response.status == 206 and len(suffix) == 4096
digest = hashlib.sha256()
length = 0
with get(route) as response:
    while chunk := response.read(1024 * 1024):
        digest.update(chunk)
        length += len(chunk)
assert length == size
print('Complete FLAC delivery:', track['title'], 'id', track['id'], 'SHA256', digest.hexdigest())
cursor = total = available = 0
while True:
    with get('/api/shuffle?after=' + str(cursor)) as response:
        batch = json.load(response)
    total += len(batch['tracks'])
    available += sum(t['available'] for t in batch['tracks'])
    if not batch['has_more']:
        break
    assert batch['after'] > cursor
    cursor = batch['after']
assert total == 17623
print('Shuffle All indexed pagination:', total, 'tracks;', available, 'available')
