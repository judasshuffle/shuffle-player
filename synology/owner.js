// Sign requests locally. Session unlock survives navigation; remembering is opt-in.
(() => {
  const originalFetch = window.fetch.bind(window), storageKey = 'shuffle.owner.key';
  let key = '', epoch = '';
  const input = document.getElementById('ownerKey');
  const status = document.getElementById('ownerStatus');
  const remember = document.getElementById('rememberOwner');
  function stored(storage) { try { return storage.getItem(storageKey) || ''; } catch { return ''; } }
  function forget() {
    key = ''; epoch = '';
    for (const storage of [sessionStorage, localStorage]) { try { storage.removeItem(storageKey); } catch {} }
  }
  function persist() {
    try {
      sessionStorage.setItem(storageKey, key);
      if (remember?.checked) localStorage.setItem(storageKey, key);
      else localStorage.removeItem(storageKey);
    } catch { status.textContent = 'Unlocked. Browser storage is unavailable; refresh will lock controls.'; }
  }
  async function challenge() {
    epoch = (await (await originalFetch('/api/owner-challenge')).json()).epoch;
  }
  async function signedFetch(url, options = {}, retry = true) {
    if (!key) return originalFetch(url, options);
    if (!epoch) await challenge();
    const method = options.method || 'GET', body = options.body || '';
    const stamp = String(Math.floor(Date.now() / 1000));
    const nonce = Array.from(crypto.getRandomValues(new Uint8Array(16)), n => n.toString(16).padStart(2, '0')).join('');
    const message = [method, url, epoch, stamp, nonce, sha256(body)].join('\n');
    const signedEpoch = epoch;
    const response = await originalFetch(url, {...options, headers: {...options.headers,
      'X-Shuffle-Epoch': epoch, 'X-Shuffle-Time': stamp, 'X-Shuffle-Nonce': nonce,
      'X-Shuffle-Signature': sha256.hmac(key, message)}});
    let rejected = response.status === 403;
    if (retry && response.ok && method === 'GET' && (url.startsWith('/api/station') || url === '/api/sources')) {
      rejected = (await response.clone().json()).can_control === false;
    }
    if (retry && rejected) {
      await challenge();
      if (epoch !== signedEpoch) return signedFetch(url, options, false);
    }
    return response;
  }
  async function unlock(value) {
    key = value;
    if (!/^[0-9a-f]{64}$/.test(key)) { forget(); status.textContent = 'Enter your private owner key.'; return; }
    try {
      await challenge();
      const response = await signedFetch('/api/dj', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{"action":"state"}'});
      if (!response.ok) { forget(); throw Error('Owner key rejected.'); }
      status.textContent = remember?.checked ? 'Owner controls unlocked. Remembered on this browser.' : 'Owner controls unlocked for this tab, including page changes and refreshes.';
      persist();
    } catch (error) { key = ''; status.textContent = error.message; }
  }
  const saved = stored(localStorage) || stored(sessionStorage);
  if (remember) remember.checked = !!stored(localStorage);
  let ready = saved ? unlock(saved) : Promise.resolve();
  window.fetch = async (url, options) => {
    if (typeof url !== 'string' || !(url.startsWith('/api/station') || url === '/api/dj' || url.startsWith('/api/sources') || url === '/api/scan' || url === '/api/listening')) return originalFetch(url, options);
    await ready;
    return signedFetch(url, options);
  };
  document.getElementById('ownerLogin').onsubmit = async event => {
    event.preventDefault();
    const value = input.value.trim(); input.value = '';
    ready = unlock(value);
    await ready;
  };
  if (remember) remember.onchange = () => {
    if (key) {
      persist();
      status.textContent = remember.checked ? 'Owner access remembered on this browser.' : 'Owner access kept for this tab only.';
    }
  };
  document.getElementById('ownerLock').onclick = () => { forget(); status.textContent = 'Controls locked. Saved owner access cleared.'; };
  window.addEventListener('storage', event => {
    if (event.key === storageKey && !event.newValue) { forget(); status.textContent = 'Owner access locked in another tab.'; }
  });
})();
