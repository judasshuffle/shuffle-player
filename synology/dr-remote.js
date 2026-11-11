(() => {
  const el = id => document.getElementById(id);
  let bridge, owner = false, busy = false, request = 0, pending = null;
  let reviewed = '', offset = 0, hasMore = false;
  function enabled() {
    for (const id of ['shuffle','next']) el(id).disabled = busy || !owner;
    for (const id of ['play','append']) el(id).disabled = busy || !owner || !reviewed || el('query').value.trim() !== reviewed;
    el('more').disabled = busy;
  }
  function send(message) { if (bridge) bridge.emitWebEvent(JSON.stringify({app:'shufflizer-remote',...message})); }
  function command(action, extra = {}) {
    if (!owner || busy) return;
    busy = true; enabled();
    pending = {id: ++request, action};
    el('status').textContent = action === 'search' ? 'Searching…' : 'Sending DJ command…';
    send({command: action, request, ...extra});
  }
  el('volume').oninput = () => {
    el('volumeValue').textContent = el('volume').value;
    send({sound:Number(el('volume').value)});
  };
  el('query').oninput = enabled;
  el('search').onsubmit = event => { event.preventDefault(); if (busy) return; reviewed=''; offset=0; command('search',{query:el('query').value.trim(),offset}); };
  el('more').onclick = () => { offset += 50; command('search',{query:reviewed,offset}); };
  for (const action of ['play','append']) el(action).onclick = () => command(action,{query:reviewed});
  el('shuffle').onclick = () => command('shuffle');
  el('next').onclick = () => command('next');
  function receive(raw) {
    let message; try { message = JSON.parse(raw); } catch (_) { return; }
    if (!message || message.app !== 'shufflizer-remote') return;
    if (message.init) {
      owner = message.owner === true;
      el('dj').hidden = !owner;
      el('volume').value = message.volume; el('volumeValue').textContent = message.volume;
      el('status').textContent = owner ? 'Owner DJ remote ready.' : 'Visitor remote · personal volume only.';
      enabled(); if (owner && !pending) command('state');
      return;
    }
    if (!pending || pending.id !== message.request) return;
    const action = pending.action; pending = null; busy = false;
    if (message.error) { el('status').textContent = message.error; enabled(); return; }
    const result = message.result;
    if (action === 'search') {
      if (!offset) el('results').replaceChildren();
      reviewed = message.query;
      for (const track of result.tracks) { const row = document.createElement('li'); row.textContent = `${track.artist} — ${track.title}${track.available ? '' : ' (unavailable)'}`; el('results').append(row); }
      hasMore = result.has_more; el('more').hidden = !hasMore;
      el('interpretation').textContent = result.error || result.message || 'Review matches before choosing Play now or Add to queue.';
      if (result.error || (!offset && !result.tracks.some(track => track.available))) reviewed = '';
      el('status').textContent = 'Search complete. Playback unchanged.';
    } else {
      const track = result.current;
      el('nowPlaying').textContent = `${track ? track.artist + ' — ' + track.title : 'No track'} · ${result.queue_count} queued`;
      el('status').textContent = action === 'append' ? 'Matches added to the queue.' : action === 'state' ? 'Owner DJ remote ready.' : 'Shared station updated. The screen may buffer for a few seconds.';
    }
    enabled();
  }
  const timer = setInterval(() => {
    if (!window.EventBridge) return;
    clearInterval(timer); bridge=window.EventBridge;
    bridge.scriptEventReceived.connect(receive); send({hello:true}); send({ready:true});
  },100);
})();
