/*
  Shufflizer Settings Store (v1)
  - Loads defaults from /config/settings.json (served from Pi)
  - Overlays user overrides from localStorage
  - Exposes: window.ShufflizerSettings
  - Emits: window event "shufflizer:settings-ready"
*/

(function () {
  const LS_KEY = "shufflizer.settings.v1";

  const deepMerge = (base, over) => {
    if (!over || typeof over !== "object") return base;
    const out = Array.isArray(base) ? [...base] : { ...base };
    for (const [k, v] of Object.entries(over)) {
      if (v && typeof v === "object" && !Array.isArray(v) && base && typeof base[k] === "object") {
        out[k] = deepMerge(base[k], v);
      } else {
        out[k] = v;
      }
    }
    return out;
  };

  const safeParse = (s) => {
    try { return JSON.parse(s); } catch { return null; }
  };

  const state = {
    loaded: false,
    data: null,
  };

  async function load() {
    // 1) Load defaults from file
    let defaults = null;
    try {
      const res = await fetch("/config/settings.json", { cache: "no-store" });
      if (res.ok) defaults = await res.json();
    } catch (e) {
      // ignore, we'll fallback
    }

    // 2) Fallback defaults if file missing
    if (!defaults) {
      defaults = {
        audio: { mode: "stream", streamUrl: "/stream.mp3", customUrl: "" },
        visual: { oledSafe: true, hideTrackText: false, hideOverlayLabels: false }
      };
    }

    // 3) Overlay local overrides
    const overrides = safeParse(localStorage.getItem(LS_KEY)) || {};
    const merged = deepMerge(defaults, overrides);

    state.loaded = true;
    state.data = merged;

    // Announce readiness
    window.dispatchEvent(new CustomEvent("shufflizer:settings-ready", { detail: merged }));
    return merged;
  }

  function get() {
    return state.data;
  }

  function set(patch) {
    const cur = state.data || {};
    const next = deepMerge(cur, patch || {});
    state.data = next;

    // Persist only the overrides (patch merged into LS, not the whole defaults file)
    const prevOverrides = safeParse(localStorage.getItem(LS_KEY)) || {};
    const nextOverrides = deepMerge(prevOverrides, patch || {});
    localStorage.setItem(LS_KEY, JSON.stringify(nextOverrides));

    window.dispatchEvent(new CustomEvent("shufflizer:settings-changed", { detail: next }));
    return next;
  }

  // Expose a small API
  window.ShufflizerSettings = { load, get, set, _lsKey: LS_KEY };

  // Auto-load immediately
  load();
})();
