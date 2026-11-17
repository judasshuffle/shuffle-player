// Guided connection setup. A home-network test never proves internet access.
(() => {
  const el = id => document.getElementById(id);
  if (!el('connectionForm')) return;
  let allowed = false, loaded = false, loading = false, saving = false, saved = null;
  let localBase = location.origin, ownerVersion = 0;
  const ownerFields = ['publicPlayerBase', 'saveConnection', 'useLocalConnection'];
  async function request(payload) {
    const response = await fetch('/api/listening', payload ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)} : {});
    if (!response.ok) {
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      throw Error(response.status === 403 ? 'Unlock owner access first.' : (Array.from(doc.querySelectorAll('p')).map(p => p.textContent).join(' ') || 'Unable to save your connection.'));
    }
    return response.json();
  }
  function status() {
    const publicSaved = !!saved?.public_base;
    el('connectionStream').value = allowed ? saved?.stream_url || '' : '';
    el('connectionScreen').value = allowed ? saved?.screen_url || '' : '';
    for (const [field, button] of [['connectionStream','copyStream'], ['connectionScreen','copyScreen']]) {
      el(field).disabled = el(button).disabled = !allowed || !el(field).value;
    }
    el('outsideHeard').disabled = !allowed || !publicSaved || saving;
    el('confirmInternet').disabled = !allowed || !publicSaved || !el('outsideHeard').checked || saving;
    el('internetTestStatus').textContent = allowed && publicSaved && saved.internet_confirmed_at ?
      'Outside-home test recorded by you: ' + new Date(saved.internet_confirmed_at * 1000).toLocaleString() + '. This was not an automatic external check.' :
      'Internet listening has not been confirmed. A saved address or successful home test is not proof.';
    el('linkScope').textContent = !allowed ? 'Unlock owner access to view your saved links.' : publicSaved ?
      'These are your saved public links. Complete the outside-home test before using them for remote listeners.' :
      saved?.stream_url || saved?.screen_url ? 'Existing links are saved, but no public setup has been confirmed. Home-network links work only at home.' :
      'Save a public address above, or choose home-network links below.';
  }
  function routerDetails(base) {
    try {
      const url = new URL(base);
      el('routerDevice').textContent = url.hostname;
      el('routerPort').textContent = url.port || (url.protocol === 'https:' ? '443' : '80');
    } catch {
      el('routerDevice').textContent = 'Check the home IP of the device running your player.';
      el('routerPort').textContent = 'Check the listening-only host port in your installation; do not forward the owner-control port.';
    }
  }
  window.ConnectionSetup = {async updateOwner(next) {
    if (allowed !== next) ownerVersion++;
    allowed = next;
    for (const id of ownerFields) el(id).disabled = !allowed || saving;
    if (!allowed) {
      loaded = false; saved = null;
      el('publicPlayerBase').value = '';
      el('outsideHeard').checked = false;
      el('connectionStatus').textContent = 'Unlock owner access to view or save your connection.';
      el('routerDevice').textContent = 'Unlock owner access to view this installation’s details.';
      el('routerPort').textContent = 'Use the listening-only host port from your installation.';
      status(); return;
    }
    if (loaded || loading) return;
    loading = true;
    const version = ownerVersion;
    try {
      const data = await request();
      if (!allowed || version !== ownerVersion) return;
      saved = data;
      localBase = data.local_listening_base || location.origin;
      el('publicPlayerBase').value = data.public_base || '';
      // Only show a concrete router port when the installation explicitly supplies it.
      routerDetails(data.local_listening_base || '');
      el('connectionStatus').textContent = data.public_base ? 'Public address saved. Check the outside-home test below.' : 'Enter your own public address for internet listening, or keep using home-network links.';
      loaded = true; status();
    } catch (error) { el('connectionStatus').textContent = error.message; }
    finally { loading = false; }
  }};
  function publicAddress() {
    const text = el('publicPlayerBase').value.trim();
    if (!text) throw Error('Enter your public address, or choose “Save home-network links only” below.');
    const url = new URL(text);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw Error('Use an http:// or https:// player address without a password.');
    // Accept a pasted existing screen/stream link, including a cache-busting query.
    if (/\/(dr-screen|stream\.mp3)\/?$/.test(url.pathname)) {
      url.pathname = url.pathname.replace(/\/(dr-screen|stream\.mp3)\/?$/, '');
      url.search = ''; url.hash = '';
    }
    if (url.search || url.hash) throw Error('Use the player address without a query or # suffix.');
    return url.href.replace(/\/+$/, '');
  }
  async function save(payload, message) {
    if (!allowed || saving) return;
    saving = true;
    const version = ownerVersion;
    for (const id of ownerFields) el(id).disabled = true;
    status();
    try {
      const result = await request(payload);
      if (!allowed || version !== ownerVersion) return;
      saved = result;
      el('publicPlayerBase').value = result.public_base || '';
      el('outsideHeard').checked = false;
      el('connectionStatus').textContent = message;
    } catch (error) { el('connectionStatus').textContent = error.message; }
    finally {
      saving = false;
      for (const id of ownerFields) el(id).disabled = !allowed;
      status();
    }
  }
  el('connectionForm').onsubmit = event => {
    event.preventDefault();
    try { save({public_base: publicAddress()}, 'Public address saved privately. Your DarkRide links are generated below. Internet listening still needs the outside-home test.'); }
    catch (error) { el('connectionStatus').textContent = error.message; }
  };
  el('useLocalConnection').onclick = () => save({public_base:'', stream_url:new URL('stream.mp3', localBase.replace(/\/?$/, '/')).href,
    screen_url:new URL('dr-screen', localBase.replace(/\/?$/, '/')).href}, 'Home-network links saved privately. No internet access has been confirmed.');
  el('outsideHeard').onchange = status;
  el('confirmInternet').onclick = () => {
    try {
      if (publicAddress() !== saved?.public_base) throw Error('Save the changed address first, then test the new link with Wi-Fi off.');
      if (!el('outsideHeard').checked) return;
      save({public_base:saved.public_base, confirm_internet:true}, 'Your outside-home listening test has been recorded.');
    } catch (error) { el('connectionStatus').textContent = error.message; }
  };
  el('publicPlayerBase').oninput = () => {
    el('outsideHeard').checked = false;
    status();
    if (el('publicPlayerBase').value.trim() !== (saved?.public_base || '')) {
      el('outsideHeard').disabled = el('confirmInternet').disabled = true;
      el('connectionStatus').textContent = 'Address changed. Save it to generate matching links; any previous test applies only to the saved address.';
    }
  };
  async function copy(field) {
    const input = el(field);
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(input.value);
      else { input.focus(); input.select(); if (!document.execCommand('copy')) throw Error(); }
      el('copyStatus').textContent = 'Link copied. Paste it into the matching DarkRide radio or screen field.';
    } catch { input.focus(); input.select(); el('copyStatus').textContent = 'Link selected. Press Ctrl+C (or copy on your device).'; }
  }
  el('copyStream').onclick = () => copy('connectionStream');
  el('copyScreen').onclick = () => copy('connectionScreen');
  const audio = el('localTestAudio');
  el('testLocalAudio').onclick = async () => {
    audio.src = '/stream.mp3';
    el('localTestStatus').textContent = 'Connecting to this player…';
    el('stopLocalAudio').hidden = false;
    try { await audio.play(); }
    catch { el('localTestStatus').textContent = 'Could not play here. Check the player is reachable, then try again. Internet access remains untested.'; }
  };
  audio.onplaying = () => { el('localTestStatus').textContent = 'Audio received in this browser. If you hear silence, check station playback and volume. This does not test internet access.'; };
  audio.onerror = () => { el('localTestStatus').textContent = 'Local audio connection failed. Check the player is running and reachable on this network.'; };
  el('stopLocalAudio').onclick = () => {
    audio.pause(); audio.removeAttribute('src'); audio.load(); el('stopLocalAudio').hidden = true;
    el('localTestStatus').textContent = 'Local audio test stopped. Internet access remains untested.';
  };
})();
