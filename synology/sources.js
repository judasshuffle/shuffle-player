(() => {
  const el = id => document.getElementById(id);
  let busy = false, allowed = false, connectionError = false;
  async function request(route, payload) {
    const response = await fetch(route, payload ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)} : {});
    if (!response.ok) {
      const text = await response.text();
      const doc = new DOMParser().parseFromString(text, 'text/html');
      throw Error(response.status === 403 ? 'Unlock with your owner key first.' : (Array.from(doc.querySelectorAll('p')).map(p => p.textContent).join(' ') || 'Request failed.'));
    }
    return response.json();
  }
  async function refresh() {
    try {
      const data = await request('/api/sources');
      if (connectionError) { el('sourceStatus').textContent = 'Connection restored.'; connectionError = false; }
      allowed = data.can_control;
      if (window.ConnectionSetup) await window.ConnectionSetup.updateOwner(allowed);
      if (!busy) {
        const select = el('sourceSelect');
        select.replaceChildren();
        for (const source of [{id:'library', name:'My music library'}, ...data.stations]) {
          const option = document.createElement('option'); option.value = source.id; option.textContent = source.name; select.append(option);
        }
        select.value = data.active; select.disabled = !allowed;
      }
      if (el('savedStations')) {
        el('savedStations').replaceChildren();
        for (const source of data.stations) { const li = document.createElement('li'); li.textContent = source.url ? `${source.name} · ${source.url}` : source.name; el('savedStations').append(li); }
        el('testStation').disabled = el('saveStation').disabled = busy || !allowed;
        const scan = await request('/api/scan');
        el('scanLibrary').disabled = !allowed || scan.running;
        el('scanStatus').textContent = scan.running ? 'Scanning for changes. You can keep listening…' :
          (scan.error || (scan.finished_at ? `Last scan: ${new Date(scan.finished_at * 1000).toLocaleString()} · ${scan.added} added · ${scan.updated} updated · ${scan.unchanged} unchanged · ${scan.total} tracks.` : 'No scans yet. Your existing backup has seeded the working library.'));
      }
    } catch (error) { connectionError = true; el('sourceStatus').textContent = 'Player connection interrupted. Reconnecting…'; }
    setTimeout(refresh, 1500);
  }
  el('sourceSelect').onchange = async event => {
    busy = true; event.target.disabled = true;
    el('sourceStatus').textContent = 'Testing and switching source…';
    try { await request('/api/sources', {action:'select', id:event.target.value}); el('sourceStatus').textContent = 'Shared source changed.'; }
    catch (error) { el('sourceStatus').textContent = error.message; }
    finally { busy = false; }
  };
  if (el('stationForm')) {
    async function station(action) {
      if (busy) return;
      busy = true;
      el('testStatus').textContent = 'Checking for decodable audio (up to 15 seconds)…';
      try {
        const result = await request('/api/sources', {action, name:el('stationName').value, url:el('stationUrl').value});
        el('testStatus').textContent = result.message || 'Station saved. Choose it above when ready.';
      } catch (error) { el('testStatus').textContent = error.message; }
      finally { busy = false; }
    }
    el('stationForm').onsubmit = event => { event.preventDefault(); station('save'); };
    el('testStation').onclick = () => station('test');
    el('scanLibrary').onclick = async () => {
      el('scanLibrary').disabled = true;
      try { await request('/api/scan', {}); el('scanStatus').textContent = 'Scan started…'; }
      catch (error) { el('scanStatus').textContent = error.message; }
    };
  }
  refresh();
})();
