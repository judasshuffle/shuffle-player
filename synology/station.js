// The NAS owns playback. Browser audio is an optional monitor of that station.
(() => {
  let state = null, preview = [], previewStart = 0, received = 0, loadedId = null;
  let monitoring = false, busy = false;
  const listen = el('listenHere'), seek = el('stationSeek');
  player.controls = false;
  player.hidden = true;
  const clock = () => state ? state.position + (state.playing ? (performance.now() - received) / 1000 : 0) : 0;
  const time = seconds => Math.floor(seconds / 60) + ':' + String(Math.floor(seconds % 60)).padStart(2, '0');
  async function monitor(force = false) {
    const track = state?.current;
    qualityInfo(track);
    if (!monitoring || !track || !state.playing) {
      if (pendingPlayback) {
        ++playbackVersion;
        if (cancelPendingPlayback) cancelPendingPlayback();
        pendingPlayback = null; loadedId = null;
      }
      player.pause(); return;
    }
    if (force || loadedId !== track.id) {
      loadedId = track.id;
      await loadTrack(track, clock(), true);
      // Conversion/loading time does not stop the station clock.
      if (state?.current?.id === track.id && Number.isFinite(player.duration)) player.currentTime = Math.min(clock(), Math.max(0, player.duration - .1));
    } else if (!pendingPlayback) {
      if (Math.abs(player.currentTime - clock()) > 3) player.currentTime = clock();
      if (player.paused) player.play().catch(() => {});
    }
  }
  function show(next) {
    state = next; received = performance.now();
    if (next.queue) { preview = next.queue; previewStart = next.queue_start; }
    const track = state.current;
    if (track) {
      window.currentTrackTitle = `${track.artist || 'Unknown artist'} — ${track.title || 'Untitled'}`;
      el('title').textContent = window.currentTrackTitle;
      el('album').textContent = track.album || '';
      el('artwork').src = '/artwork/' + track.id;
      el('artwork').alt = 'Album artwork for ' + (track.album || track.title || 'current track');
      el('originalLink').href = '/media/' + track.id + '?quality=original';
      el('mp3Link').href = '/media/' + track.id + '?quality=mp3';
      el('originalLink').hidden = el('mp3Link').hidden = false;
    }
    el('toggle').textContent = state.playing ? 'Pause station' : 'Play station';
    ['toggle','prev','next','shuffleAll','playMatches','queueMatches'].forEach(id => { el(id).disabled = !state.can_control; });
    seek.disabled = !state.can_control || !track?.duration;
    seek.max = track?.duration || 1;
    seek.value = Math.min(clock(), Number(seek.max));
    el('stationTime').textContent = `${time(clock())} / ${time(track?.duration || 0)}`;
    el('stationStatus').textContent = `${state.playing ? 'Playing' : 'Paused'} on the shared DarkRide station · ${state.queue_count} queued tracks. ${state.can_control ? 'These controls change what everyone hears.' : 'Open the LAN player to control the station.'} DarkRide may lag by a few seconds.`;
    el('queue').replaceChildren();
    el('queue').start = previewStart + 1;
    preview.forEach((item, local) => {
      const index = previewStart + local, row = document.createElement('li');
      row.textContent = `${index === state.index ? '▶ ' : ''}${item.artist || 'Unknown artist'} — ${item.title || 'Untitled'}`;
      const select = button('Play', () => command('select', {index}));
      const remove = button('Remove', () => command('remove', {index}));
      select.disabled = remove.disabled = !state.can_control;
      row.append(select, remove); el('queue').append(row);
    });
    el('queueInfo').textContent = `${state.queue_count} tracks in the NAS station queue; showing ${preview.length} around the current track. Queue stays in memory until the player container restarts.`;
    monitor().catch(() => {});
  }
  async function command(action, extra = {}) {
    if (!state?.can_control || busy) return;
    context.resume().catch(() => {});
    busy = true;
    try {
      const response = await fetch('/api/station/control', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action,...extra})});
      if (!response.ok) throw Error('Station command failed (' + response.status + '). Refresh and try again.');
      show(await response.json());
    } catch (error) { el('stationStatus').textContent = error.message; }
    finally { busy = false; }
  }
  stationController = {command, monitor};
  el('prev').onclick = () => command('previous');
  el('next').onclick = () => command('next');
  el('toggle').onclick = () => command('toggle');
  seek.onchange = () => command('seek', {position:Number(seek.value)});
  listen.onchange = () => {
    monitoring = listen.checked;
    context.resume().catch(() => {});
    monitor(true).catch(() => {});
    el('status').textContent = monitoring ? 'Browser monitor enabled. Quality applies only to this browser.' : 'Listening through DarkRide. Browser audio is off; station controls remain active.';
  };
  async function poll() {
    try {
      const response = await fetch('/api/station?since=' + (state?.version || 0));
      if (!response.ok) throw Error('Station unavailable');
      if (!busy) show(await response.json());
    } catch { el('stationStatus').textContent = 'Station connection lost. Reconnecting…'; }
    setTimeout(poll, 1000);
  }
  el('status').textContent = 'Listening through DarkRide. Enable “Listen in this browser” for a local lossless or MP3 monitor and reactive visualizer.';
  poll();
})();
