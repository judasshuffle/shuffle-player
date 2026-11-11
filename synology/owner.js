// Dashboard owner key stays in this tab's memory; only request signatures travel.
(() => {
  const originalFetch = window.fetch.bind(window);
  let key = '', epoch = '';
  const input = document.getElementById('ownerKey');
  const status = document.getElementById('ownerStatus');
  async function signedFetch(url, options = {}) {
    if (!key) return originalFetch(url, options);
    const method = options.method || 'GET', body = options.body || '';
    const stamp = String(Math.floor(Date.now() / 1000));
    const nonce = Array.from(crypto.getRandomValues(new Uint8Array(16)), n => n.toString(16).padStart(2, '0')).join('');
    const message = [method, url, epoch, stamp, nonce, sha256(body)].join('\n');
    return originalFetch(url, {...options, headers: {...options.headers,
      'X-Shuffle-Epoch': epoch, 'X-Shuffle-Time': stamp, 'X-Shuffle-Nonce': nonce,
      'X-Shuffle-Signature': sha256.hmac(key, message)}});
  }
  window.fetch = (url, options) => typeof url === 'string' &&
    (url.startsWith('/api/station') || url === '/api/dj') ? signedFetch(url, options) : originalFetch(url, options);
  document.getElementById('ownerLogin').onsubmit = async event => {
    event.preventDefault();
    key = input.value.trim(); input.value = '';
    if (!/^[0-9a-f]{64}$/.test(key)) { key = ''; status.textContent = 'Enter your private owner key.'; return; }
    try {
      epoch = (await (await originalFetch('/api/owner-challenge')).json()).epoch;
      const response = await signedFetch('/api/dj', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{"action":"state"}'});
      if (!response.ok) throw Error('Owner key rejected.');
      status.textContent = 'Owner controls unlocked in this tab.';
    } catch (error) { key = ''; status.textContent = error.message; }
  };
  document.getElementById('ownerLock').onclick = () => { key = ''; status.textContent = 'Controls locked.'; };
})();
