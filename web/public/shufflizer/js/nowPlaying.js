function pickSource(src) {
  if (!src) return null;
  if (Array.isArray(src)) return src[0] ?? null;
  return src;
}

function extractTitle(source) {
  if (!source) return "";
  // common Icecast fields
  return (
    source.title ||
    source.yp_currently_playing ||
    source.server_name ||
    source.description ||
    ""
  );
}

export function startNowPlaying({ host, intervalMs = 2000, onUpdate } = {}) {
  let stopped = false;
  let last = "";

  async function tick() {
    if (stopped) return;

    try {
      const url = `http://${host}:8001/status-json.xsl?_=${Date.now()}`;
      const r = await fetch(url, { cache: "no-store" });
      const j = await r.json();

      const src = pickSource(j?.icestats?.source);
      const title = extractTitle(src).trim();

      if (title && title !== last) {
        last = title;
        onUpdate?.(title);
      }
    } catch {
      // ignore; we'll try again next tick
    } finally {
      if (!stopped) setTimeout(tick, intervalMs);
    }
  }

  tick();

  return () => { stopped = true; };
}
