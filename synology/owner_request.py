"""Owner diagnostic client. Reads a private local key, never sends it to HTTP."""
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import time
from urllib.request import Request, urlopen


def signed_request(base, route, payload=None, key_file=None):
    key = Path(key_file or Path(__file__).parent / 'secrets/owner-key').read_text().strip()
    with urlopen(base + '/api/owner-challenge', timeout=15) as response:
        epoch = json.load(response)['epoch']
    body = json.dumps(payload).encode() if payload is not None else b''
    method = 'POST' if payload is not None else 'GET'
    stamp, nonce = str(int(time.time())), secrets.token_hex(16)
    canonical = '\n'.join((method, route, epoch, stamp, nonce, hashlib.sha256(body).hexdigest())).encode()
    headers = {'X-Shuffle-Epoch': epoch, 'X-Shuffle-Time': stamp, 'X-Shuffle-Nonce': nonce,
               'X-Shuffle-Signature': hmac.new(key.encode(), canonical, hashlib.sha256).hexdigest()}
    if payload is not None: headers['Content-Type'] = 'application/json'
    return Request(base + route, data=body if payload is not None else None, headers=headers, method=method)
