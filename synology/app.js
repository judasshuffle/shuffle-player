const el = id => document.getElementById(id);
const player = el('player');
const context = new (window.AudioContext || window.webkitAudioContext)();
const source = context.createMediaElementSource(player);
const analyser = context.createAnalyser();
analyser.fftSize = 1024;
source.connect(analyser);
analyser.connect(context.destination);
window.playerAudio = {audioCtx: context, analyser, setMuted: value => { player.muted = value; }};
window.currentTrackTitle = '';
const frame = document.createElement('iframe');
frame.src = '/visualizer/index.html?embed=1';
frame.title = 'Shufflizer — reacts to browser playback';
frame.allow = 'autoplay';
el('visualizer').append(frame);
let queue = [], position = -1, offset = 0, query = '', generation = 0;
let stationController = null;
let actionVersion = 0;
let playbackVersion = 0, pendingPlayback = null, cancelPendingPlayback = null, failedPlayback = null;
let quality = 'original';
try { if (localStorage.getItem('shuffle.playback.quality') === 'mp3') quality = 'mp3'; } catch {}
el('quality').value = quality;
function qualityInfo(track) {
  if (quality === 'mp3') {
    el('qualityInfo').textContent = 'MP3 256 kbps · converted for playback only. First play may take a moment.';
  } else if (track && !player.canPlayType(track.mime_type || 'audio/flac')) {
    el('qualityInfo').textContent = 'This browser does not report support for the original format. Choose MP3 if it will not play.';
  } else {
    el('qualityInfo').textContent = 'Original audio, with no conversion. Lossless sources stay lossless.';
  }
}
qualityInfo();
async function loadTrack(track, resumeAt = 0, autoplay = true) {
  const mine = ++playbackVersion;
  if (cancelPendingPlayback) cancelPendingPlayback();
  const pending = pendingPlayback = {trackId:track.id, resumeAt, autoplay, positionRestored:true};
  failedPlayback = null;
  player.pause();
  qualityInfo(track);
  el('status').textContent = quality === 'mp3' ? 'Preparing MP3 playback…' : 'Loading original audio…';
  // Resume WebAudio during the click, before waiting for conversion or metadata.
  const resumed = autoplay ? context.resume().catch(() => {}) : Promise.resolve();
  const metadata = new Promise(resolve => {
    let timer;
    const finish = ok => {
      clearTimeout(timer);
      player.removeEventListener('loadedmetadata', ready);
      player.removeEventListener('error', failed);
      if (mine === playbackVersion) cancelPendingPlayback = null;
      resolve(ok);
    };
    const ready = () => {
      if (mine !== playbackVersion) return finish(false);
      try {
        if (resumeAt > 0) player.currentTime = Number.isFinite(player.duration)
          ? Math.min(resumeAt, Math.max(0, player.duration - 0.05)) : resumeAt;
      } catch { pending.positionRestored = false; }
      finish(true);
    };
    const failed = () => finish(false);
    cancelPendingPlayback = () => finish(false);
    player.addEventListener('loadedmetadata', ready);
    player.addEventListener('error', failed);
    timer = setTimeout(failed, 210000);
  });
  player.src = '/media/' + track.id + (quality === 'mp3' ? '?quality=mp3' : '');
  player.load();
  const loaded = await metadata;
  if (mine !== playbackVersion) return;
  pendingPlayback = null;
  if (!loaded) {
    failedPlayback = pending;
    el('status').textContent = quality === 'mp3'
      ? 'MP3 playback unavailable. Try Lossless / original; your queue is preserved.'
      : 'Original playback unavailable. Try MP3 compatibility; your queue is preserved.';
    return;
  }
  try {
    await resumed;
    if (mine !== playbackVersion) return;
    if (pending.autoplay) await player.play();
    if (mine === playbackVersion) {
      el('status').textContent = pending.autoplay
        ? 'Playing in this browser. The visualizer uses the same audio.' : 'Paused. Playback quality updated.';
      if (!pending.positionRestored) el('status').textContent += ' Position could not be restored; playback restarts at the beginning.';
    }
  } catch {
    if (mine === playbackVersion) el('status').textContent = 'Press Play to resume. If the original format struggles, choose MP3 compatibility.';
  }
}
el('quality').onchange = () => {
  quality = el('quality').value === 'mp3' ? 'mp3' : 'original';
  try { localStorage.setItem('shuffle.playback.quality', quality); } catch {}
  if (stationController) return stationController.monitor(true);
  qualityInfo(position >= 0 ? queue[position] : null);
  if (position < 0 || !queue[position]) return;
  const restore = pendingPlayback || (failedPlayback?.trackId === queue[position].id ? failedPlayback : null);
  const resumeAt = restore ? restore.resumeAt : (Number.isFinite(player.currentTime) ? player.currentTime : 0);
  const autoplay = restore ? restore.autoplay : !player.paused;
  return loadTrack(queue[position], resumeAt, autoplay);
};
function button(label, action) { const b = document.createElement('button'); b.textContent = label; b.onclick = action; return b; }
function renderQueue() {
  el('queue').replaceChildren();
  queue.forEach((track, index) => {
    const li = document.createElement('li');
    li.textContent = `${index === position ? '▶ ' : ''}${track.artist || 'Unknown artist'} — ${track.title || 'Untitled'}`;
    li.append(button('Play', () => play(index)), button('Remove', () => {
      if (index === position) {
        ++playbackVersion; if (cancelPendingPlayback) cancelPendingPlayback(); pendingPlayback = null;
        player.pause(); player.removeAttribute('src'); player.load(); position = -1;
      }
      else if (index < position) position--;
      queue.splice(index, 1); renderQueue();
    }));
    el('queue').append(li);
  });
}
async function play(index) {
  if (stationController) return stationController.command('select', {index});
  if (index < 0 || index >= queue.length) return;
  position = index;
  const track = queue[index];
  el('artwork').src = '/artwork/' + track.id;
  el('artwork').alt = `Album artwork for ${track.album || track.title || 'current track'}`;
  window.currentTrackTitle = `${track.artist || 'Unknown artist'} — ${track.title || 'Untitled'}`;
  el('title').textContent = window.currentTrackTitle;
  el('album').textContent = track.album || '';
  el('originalLink').href = '/media/' + track.id + '?quality=original';
  el('mp3Link').href = '/media/' + track.id + '?quality=mp3';
  el('originalLink').hidden = el('mp3Link').hidden = false;
  renderQueue();
  player.muted = false;
  await loadTrack(track);
}
player.addEventListener('play', () => context.resume());
player.addEventListener('ended', () => { if (stationController || pendingPlayback) return; if (position + 1 < queue.length) play(position + 1); else el('status').textContent = 'Queue finished.'; });
player.addEventListener('error', () => { el('status').textContent = 'Playback unavailable. Try the other playback quality; your queue is preserved.'; });
el('prev').onclick = () => play(position - 1);
el('next').onclick = () => play(position + 1);
el('toggle').onclick = async () => {
  if (pendingPlayback) {
    pendingPlayback.autoplay = !pendingPlayback.autoplay;
    el('status').textContent = pendingPlayback.autoplay ? 'Playback will start when ready.' : 'Playback will stay paused when ready.';
    return;
  }
  if (!player.getAttribute('src')) return play(position < 0 ? 0 : position);
  if (!player.paused) return player.pause();
  try { await context.resume(); await player.play(); } catch { el('status').textContent = 'Unable to play this track.'; }
};
async function search(append = false) {
  const mine = ++generation;
  try {
    const response = await fetch('/api/search?q=' + encodeURIComponent(query) + '&offset=' + offset);
    if (!response.ok) throw Error();
    const result = await response.json();
    if (mine !== generation) return;
    el('interpretation').textContent = result.error || result.message || 'Review matches before playback.';
    el('playMatches').disabled = el('queueMatches').disabled = !!result.error || !result.tracks.some(track => track.available);
    if (!append) el('results').replaceChildren();
    for (const track of result.tracks) {
      const row = document.createElement('div'); row.className = 'track';
      const meta = document.createElement('div'); meta.className = 'meta';
      const title = document.createElement('strong'); title.textContent = track.title || 'Untitled';
      const detail = document.createElement('div'); detail.className = 'small';
      detail.textContent = `${track.artist || 'Unknown artist'} · ${track.album || ''}${track.available ? '' : ' · File unavailable (index retained)'}`;
      meta.append(title, detail); row.append(meta);
      const start = button('Play', () => { actionVersion++; if (stationController) return stationController.command('replace', {ids:[track.id]}); queue = [track]; play(0); });
      const add = button('Add to queue', () => { if (stationController) return stationController.command('append', {ids:[track.id]}); queue.push(track); renderQueue(); });
      start.disabled = add.disabled = !track.available; row.append(start, add); el('results').append(row);
    }
    if (!append && !result.tracks.length) el('results').textContent = 'No matching tracks.';
    el('more').hidden = !result.has_more;
  } catch { if (mine === generation) el('results').textContent = 'Library unavailable. No scan or rebuild was started.'; }
}
async function collectMatches(shuffle = false) {
  const mine = ++actionVersion, selectedQuery = query;
  let collected = [], cursor = 0;
  el('status').textContent = shuffle ? 'Reading tracks from the existing index; no music scan.' : 'Collecting the reviewed matches from the index.';
  while (true) {
    const url = shuffle ? '/api/shuffle?after=' + cursor : '/api/search?q=' + encodeURIComponent(selectedQuery) + '&offset=' + cursor;
    const response = await fetch(url);
    if (!response.ok) throw Error('Unable to read indexed tracks.');
    const result = await response.json();
    if (mine !== actionVersion) return null;
    if (result.error) throw Error(result.error);
    collected.push(...result.tracks.filter(track => track.available));
    if (!result.has_more) break;
    cursor = shuffle ? result.after : cursor + 50;
  }
  if (shuffle) {
    for (let i = collected.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [collected[i], collected[j]] = [collected[j], collected[i]];
    }
  }
  return collected;
}
async function useMatches(start, shuffle = false) {
  if (stationController && (shuffle || start)) {
    return stationController.command(shuffle ? 'shuffle' : 'program', shuffle ? {} : {query});
  }
  try {
    const matches = await collectMatches(shuffle);
    if (!matches) return;
    if (!matches.length) { el('status').textContent = 'No available indexed tracks match. Queue unchanged.'; return; }
    if (stationController) return await stationController.command(start ? 'replace' : 'append', {ids:matches.map(track => track.id), repeat:shuffle});
    if (start) {
      queue = matches; position = -1; renderQueue(); await play(0);
    } else {
      queue.push(...matches); renderQueue();
      el('status').textContent = `${matches.length} matching tracks added to the queue; playback unchanged.`;
    }
  } catch (error) { el('status').textContent = error.message + ' Queue unchanged.'; }
}
el('playMatches').onclick = () => useMatches(true);
el('queueMatches').onclick = () => useMatches(false);
el('shuffleAll').onclick = () => useMatches(true, true);
el('search').onsubmit = event => { event.preventDefault(); actionVersion++; query = el('q').value.trim(); offset = 0; el('playMatches').disabled = el('queueMatches').disabled = true; search(); };
el('more').onclick = () => { offset += 50; search(true); };
el('styleSelect').onchange = () => {
  if (!el('styleSelect').value) return;
  el('q').value = 'play genre ' + el('styleSelect').value;
  actionVersion++; query = el('q').value; offset = 0;
  el('playMatches').disabled = el('queueMatches').disabled = true;
  return search();
};
async function loadStyles() {
  try {
    const response = await fetch('/api/styles');
    if (!response.ok) throw Error();
    const result = await response.json();
    if (result.error) throw Error(result.error);
    const families = document.createElement('optgroup'); families.label = 'Musical styles';
    const subgenres = document.createElement('optgroup'); subgenres.label = 'More styles from your library';
    for (const style of result.styles) {
      const option = document.createElement('option');
      option.value = style.name; option.textContent = `${style.name} (${style.count.toLocaleString()})`;
      option.disabled = !style.count;
      (style.family ? families : subgenres).append(option);
    }
    el('styleSelect').append(families, subgenres);
    el('styleInfo').textContent = `${result.tagged.toLocaleString()} tracks have genre tags; ${result.untagged.toLocaleString()} are untagged. Counts use existing tags and can overlap; styles without matches are disabled.`;
  } catch (error) {
    el('styleInfo').textContent = error.message || 'Styles unavailable.';
  }
}
loadStyles();
search();
