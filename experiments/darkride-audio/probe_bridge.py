"""Read-only 30-second bridge probe; validates real live chunks, not fixture music."""
import array
import hashlib
import io
import json
import math
import time
import urllib.request
import wave

BASE = 'http://127.0.0.1:18791'


def main():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    seen, samples, start = set(), [], time.monotonic()
    first = None
    for _ in range(30):
        t = time.monotonic()
        with opener.open(BASE + '/manifest.json', timeout=3) as r:
            m = json.load(r)
        assert len(m['ids']) <= 12, 'Retention exceeded'
        if m['ids']:
            key = (m['session'], m['ids'][-1])
            if key not in seen:
                with opener.open(BASE + '/chunk/%s/%s.wav' % key, timeout=3) as r:
                    payload = r.read()
                with wave.open(io.BytesIO(payload)) as w:
                    assert (w.getframerate(), w.getsampwidth(), w.getnchannels(), w.getnframes()) == (24000, 2, 1, 48000)
                    pcm = w.readframes(w.getnframes())
                values = array.array('h', pcm)
                rms = math.sqrt(sum(x*x for x in values) / len(values))
                samples.append({'id': key[1], 'elapsed': round(t-start, 3),
                    'age': round(m['age'], 3), 'rms': round(rms, 2),
                    'sha256': hashlib.sha256(pcm).hexdigest(),
                    'fetch_ms': round((time.monotonic()-t)*1000, 2)})
                seen.add(key)
                if first is None:
                    first = m['restarts']
        time.sleep(max(0, 1-(time.monotonic()-t)))
    assert len(samples) >= 10, 'Too few fresh chunks'
    assert any(s['rms'] > 0 for s in samples), 'All captured audio is silence'
    assert len({s['sha256'] for s in samples}) > 1, 'No changing audio observed'
    print(json.dumps({'source': 'existing live Icecast', 'duration_s': round(time.monotonic()-start, 2),
        'restarts_during_probe': m['restarts']-first, 'samples': samples}, indent=2))


if __name__ == '__main__':
    main()
