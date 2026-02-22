export function startNowPlaying({ intervalMs = 1000, onUpdate } = {}) {
  let stopped = false;
  let lastTs = null;

  async function tick() {
    if (stopped) return;

    try {
      // Same-origin (served by :8090), avoids CORS
      const r = await fetch(`/nowplaying.json?_=${Date.now()}`, { cache: "no-store" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();

      const ts = j?.ts ?? null;
      const artist = (j?.artist ?? "").toString().trim();
      const title  = (j?.title  ?? "").toString().trim();

      const text = (artist && title) ? `${artist} — ${title}` : (title || artist || "");

      // Fire when ts changes (track change), or first time we get data
      if (ts !== null && ts !== lastTs) {
        lastTs = ts;
        if (text) onUpdate?.(text);
      } else if (lastTs === null && text) {
        // Initial fill
        lastTs = ts;
        onUpdate?.(text);
      }
    } catch (e) {
      console.log('[nowplaying] fetch failed', e);
    } finally {
      if (!stopped) setTimeout(tick, intervalMs);
    }
  }

  tick();
  return () => { stopped = true; };
}
