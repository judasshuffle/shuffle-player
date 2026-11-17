const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const source = fs.readFileSync('synology/owner.js', 'utf8');
const ownerKey = 'a'.repeat(64), storageKey = 'shuffle.owner.key';
const storage = () => {
  const values = new Map();
  return {getItem: key => values.get(key), setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key)};
};
let epoch = 'first-epoch';
let requests = [];
function page(sessionStorage, localStorage) {
  const elements = Object.fromEntries(['ownerKey','ownerStatus','rememberOwner','ownerLogin','ownerLock'].map(id => [id, {}]));
  const window = {addEventListener() {}, fetch: async (url, options = {}) => {
    requests.push({url, options});
    if (url === '/api/owner-challenge') return {json: async () => ({epoch})};
    const headers = options.headers || {}, body = options.body || '';
    const message = [options.method || 'GET', url, epoch, headers['X-Shuffle-Time'], headers['X-Shuffle-Nonce'], crypto.createHash('sha256').update(body).digest('hex')].join('\n');
    const valid = headers['X-Shuffle-Epoch'] === epoch && headers['X-Shuffle-Signature'] === crypto.createHmac('sha256', ownerKey).update(message).digest('hex');
    const data = {can_control: valid};
    const ok = options.method !== 'POST' || valid;
    return {ok, status: ok ? 200 : 403, json: async () => data, clone: () => ({json:async () => data})};
  }};
  const context = vm.createContext({window, document:{getElementById:id=>elements[id]}, sessionStorage, localStorage,
                                   crypto:crypto.webcrypto, console});
  vm.runInContext(fs.readFileSync('synology/sha256.js', 'utf8'), context);
  context.sha256 = window.sha256;
  vm.runInContext(source, context);
  return {window, elements};
}
(async () => {
  const session = storage(), local = storage();
  let tab = page(session, local);
  tab.elements.ownerKey.value = ownerKey;
  await tab.elements.ownerLogin.onsubmit({preventDefault(){}});
  assert.equal(session.getItem(storageKey), ownerKey);
  assert.equal(local.getItem(storageKey), undefined, 'Remembering across visits requires opt-in');
  tab = page(session, local);
  assert.equal((await (await tab.window.fetch('/api/sources')).json()).can_control, true, 'Navigation restores owner signatures');
  epoch = 'restarted-epoch';
  assert.equal((await (await tab.window.fetch('/api/station?since=1')).json()).can_control, true, 'Server restart renews challenge without key entry');
  tab.elements.rememberOwner.checked = true;
  tab.elements.rememberOwner.onchange();
  assert.equal(local.getItem(storageKey), ownerKey);
  tab = page(storage(), local);
  assert.equal((await (await tab.window.fetch('/api/sources')).json()).can_control, true, 'Remembered unlock works in a new tab/session');
  assert.equal(tab.elements.rememberOwner.checked, true);
  assert.ok(requests.every(({options}) => !JSON.stringify(options).includes(ownerKey)), 'Private key is never sent in requests');
  tab.elements.ownerLock.onclick();
  assert.equal(local.getItem(storageKey), undefined);
  assert.equal((await (await tab.window.fetch('/api/sources')).json()).can_control, false);
  console.log('Owner unlock tests passed: navigation, refresh, opt-in persistence, restart renewal, signing and Lock.');
})().catch(error => {console.error(error); process.exitCode = 1;});
