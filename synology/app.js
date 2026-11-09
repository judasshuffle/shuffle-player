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
function button(label, action) { const b = document.createElement('button'); b.textContent = label; b.onclick = action; return b; }
function renderQueue() {
  el('queue').replaceChildren();
  queue.forEach((track, index) => {
    const li = document.createElement('li');
    li.textContent = `${index === position ? '▶ ' : ''}${track.artist || 'Unknown artist'} — ${track.title || 'Untitled'}`;
    li.append(button('Play', () => play(index)), button('Remove', () => {
      if (index === position) { player.pause(); player.removeAttribute('src'); player.load(); position = -1; }
      else if (index < position) position--;
      queue.splice(index, 1); renderQueue();
    }));
    el('queue').append(li);
  });
}
async function play(index) {
  if (index < 0 || index >= queue.length) return;
  position = index;
  const track = queue[index];
  player.src = '/media/' + track.id;
  window.currentTrackTitle = `${track.artist || 'Unknown artist'} — ${track.title || 'Untitled'}`;
  el('title').textContent = window.currentTrackTitle;
  el('album').textContent = track.album || '';
  renderQueue();
  try { await context.resume(); player.muted = false; await player.play(); el('status').textContent = 'Playing in this browser. The visualizer uses the same audio.'; }
  catch (error) { el('status').textContent = 'Playback unavailable. The file may be missing or its format unsupported by this browser. No index entries were changed.'; }
}
player.addEventListener('play', () => context.resume());
player.addEventListener('ended', () => { if (position + 1 < queue.length) play(position + 1); else el('status').textContent = 'Queue finished.'; });
player.addEventListener('error', () => { el('status').textContent = 'Track unavailable or unsupported by this browser. Choose another track; the index is unchanged.'; });
el('prev').onclick = () => play(position - 1);
el('next').onclick = () => play(position + 1);
el('toggle').onclick = async () => {
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
    if (!append) el('results').replaceChildren();
    for (const track of result.tracks) {
      const row = document.createElement('div'); row.className = 'track';
      const meta = document.createElement('div'); meta.className = 'meta';
      const title = document.createElement('strong'); title.textContent = track.title || 'Untitled';
      const detail = document.createElement('div'); detail.className = 'small';
      detail.textContent = `${track.artist || 'Unknown artist'} · ${track.album || ''}${track.available ? '' : ' · File unavailable (index retained)'}`;
      meta.append(title, detail); row.append(meta);
      const start = button('Play', () => { queue.push(track); play(queue.length - 1); });
      const add = button('Add to queue', () => { queue.push(track); renderQueue(); });
      start.disabled = add.disabled = !track.available; row.append(start, add); el('results').append(row);
    }
    if (!append && !result.tracks.length) el('results').textContent = 'No matching tracks.';
    el('more').hidden = !result.has_more;
  } catch { if (mine === generation) el('results').textContent = 'Library unavailable. No scan or rebuild was started.'; }
}
el('search').onsubmit = event => { event.preventDefault(); query = el('q').value.trim(); offset = 0; search(); };
el('more').onclick = () => { offset += 50; search(true); };
search();
