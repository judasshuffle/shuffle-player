import { initUI } from "./ui.js";
import { initAudio } from "./audio.js";
import { startEngine } from "./engine.js";
import { startNowPlaying } from "./nowPlaying.js";
import { spawnTitleParticle } from "./visuals.js";

const canvas = document.getElementById("c");
const audioEl = document.getElementById("audio");

// Use the page host (Pi IP) so remote clients hit the Pi's Icecast.
// Stream URL:
// - Normal LAN use: http://<this-host>:8001/stream.mp3
// - Cloudflare quick tunnel: same-origin /stream.mp3 (proxied by 8091 server)
// Stream URL logic with optional override
(function(){
  const override = localStorage.getItem("shufflizer.stream.override");
  if (override && override.trim()) {
    audioEl.src = override.trim();
    return;
  }

  audioEl.src = /trycloudflare\.com$/i.test(location.hostname)
    ? new URL("/stream.mp3", location.href).toString()
    : `http://${location.hostname}:8001/stream.mp3`;
})();
audioEl.load();

const ui = initUI();
// --- SHUFFLIZER_PALETTE_CORE ---
window.SHUF_PRESETS = window.SHUF_PRESETS || {"Phosphor Prime":{"primary":"rgba(0,255,102,0.95)","accent":"rgba(102,255,208,0.90)","glow":"rgba(0,170,68,0.90)","glowFill":"rgba(0,170,68,0.25)","tint":0.65},"Ember Grid":{"primary":"rgba(255,146,0,0.95)","accent":"rgba(255,205,115,0.90)","glow":"rgba(215,123,95,0.90)","glowFill":"rgba(215,123,95,0.25)","tint":0.65},"Copper Pulse":{"primary":"rgba(241,142,63,0.95)","accent":"rgba(229,149,121,0.90)","glow":"rgba(193,76,50,0.90)","glowFill":"rgba(193,76,50,0.25)","tint":0.65},"Overdrive":{"primary":"rgba(255,197,0,0.95)","accent":"rgba(236,65,11,0.90)","glow":"rgba(179,0,25,0.90)","glowFill":"rgba(179,0,25,0.25)","tint":0.7},"Midnight Alloy":{"primary":"rgba(255,164,0,0.95)","accent":"rgba(108,52,0,0.90)","glow":"rgba(65,34,42,0.90)","glowFill":"rgba(65,34,42,0.25)","tint":0.7},"Analog Drift":{"primary":"rgba(255,205,135,0.95)","accent":"rgba(188,117,118,0.90)","glow":"rgba(105,107,126,0.90)","glowFill":"rgba(105,107,126,0.25)","tint":0.6}};

// --- Custom palette support (Step2) ---
(function(){
  const KEY_NAME   = "shufflizer.palette.name";
  const KEY_CUSTOM = "shufflizer.palette.custom";

  function clamp01(x){
    x = Number(x);
    if (!isFinite(x)) return 0;
    return Math.max(0, Math.min(1, x));
  }

  function normHex(s){
    if (!s) return null;
    s = String(s).trim();
    if (!s) return null;
    if (s[0] !== "#") s = "#" + s;
    const m3 = /^#([0-9a-fA-F]{3})$/.exec(s);
    if (m3){
      const a = m3[1];
      return "#" + a[0]*2 + a[1]*2 + a[2]*2;
    }
    const m6 = /^#([0-9a-fA-F]{6})$/.exec(s);
    if (m6) return "#" + m6[1].toUpperCase();
    return null;
  }

  function getActivePresetOrFallback(){
    // Best effort: use current SHUF if present, else Phosphor Prime, else first preset
    const presets = window.SHUF_PRESETS || {};
    if (window.SHUF && window.SHUF.primary) {
      return {
        primary: window.SHUF.primary,
        accent: window.SHUF.accent || window.SHUF.primary,
        glow: window.SHUF.glow || window.SHUF.primary,
        glowFill: window.SHUF.glowFill || window.SHUF.glow || window.SHUF.primary,
        tint: (typeof window.SHUF.tint === "number") ? window.SHUF.tint : 0.25
      };
    }
    if (presets["Phosphor Prime"]) return presets["Phosphor Prime"];
    const first = Object.keys(presets)[0];
    return first ? presets[first] : { primary:"#39FF14", accent:"#7CFF5B", glow:"#39FF14", glowFill:"#39FF1440", tint:0.25 };
  }

  function getCustomDefault(){
    const base = getActivePresetOrFallback();
    return {
      primary: base.primary,
      accent: base.accent,
      glow: base.glow,
      glowFill: base.glowFill,
      tint: (typeof base.tint === "number") ? base.tint : 0.25
    };
  }

  function loadCustom(){
    try{
      const raw = localStorage.getItem(KEY_CUSTOM);
      if (!raw) return getCustomDefault();
      const obj = JSON.parse(raw) || {};
      const d = getCustomDefault();
      return {
        primary:  normHex(obj.primary)  || d.primary,
        accent:   normHex(obj.accent)   || d.accent,
        glow:     normHex(obj.glow)     || d.glow,
        glowFill: normHex(obj.glowFill) || d.glowFill,
        tint: clamp01(obj.tint ?? d.tint)
      };
    }catch(e){
      return getCustomDefault();
    }
  }

  function saveCustom(obj){
    try{
      localStorage.setItem(KEY_CUSTOM, JSON.stringify(obj));
    }catch(e){}
  }

  function applyPalette(name, pal){
    // Unified state (Step1)
    window.SHUF = window.SHUF || {};
    window.SHUF.name = name;
    window.SHUF.primary  = pal.primary;
    window.SHUF.accent   = pal.accent;
    window.SHUF.glow     = pal.glow;
    window.SHUF.glowFill = pal.glowFill;
    window.SHUF.tint     = (typeof pal.tint === "number") ? pal.tint : (window.SHUF.tint ?? 0.25);

    // Back-compat globals (Step1)
    window.SHUF_PRIMARY   = window.SHUF.primary;
    window.SHUF_ACCENT    = window.SHUF.accent;
    window.SHUF_GLOW_FILL = window.SHUF.glowFill;
    window.SHUF_TINT      = window.SHUF.tint;
  }

  // Public API for UI
  window.SHUF_getCustomPalette = function(){
    return loadCustom();
  };

  window.SHUF_setCustomPalette = function(partial){
    const cur = loadCustom();
    const next = {
      primary:  normHex(partial.primary)  || cur.primary,
      accent:   normHex(partial.accent)   || cur.accent,
      glow:     normHex(partial.glow)     || cur.glow,
      glowFill: normHex(partial.glowFill) || cur.glowFill,
      tint: clamp01(partial.tint ?? cur.tint)
    };
    saveCustom(next);
    // Keep currently selected name unchanged; UI will set name to Custom when needed
    return next;
  };

  window.SHUF_applyPaletteByName = function(name){
    const presets = window.SHUF_PRESETS || {};
    if (name === "Custom"){
      const pal = loadCustom();
      applyPalette("Custom", pal);
      try{ localStorage.setItem(KEY_NAME, "Custom"); }catch(e){}
      return;
    }
    if (presets[name]){
      applyPalette(name, presets[name]);
      try{ localStorage.setItem(KEY_NAME, name); }catch(e){}
      return;
    }
    // Unknown: fall back to stored name or Phosphor Prime or first
    const fallback = presets["Phosphor Prime"] ? "Phosphor Prime" : (Object.keys(presets)[0] || "Custom");
    window.SHUF_applyPaletteByName(fallback);
  };
})();


(function(){
  const KEY = 'shufflizer.palette.name';
  const DEFAULT = 'Ember Grid';
  let name = DEFAULT;
  try { name = localStorage.getItem(KEY) || DEFAULT; } catch {}
  const p = (window.SHUF_PRESETS && window.SHUF_PRESETS[name]) ? window.SHUF_PRESETS[name] : window.SHUF_PRESETS[DEFAULT];
  window.SHUF = Object.assign({ name }, p);
  // Back-compat globals (still used in some places)
  window.SHUF_PRIMARY = window.SHUF.primary;
  window.SHUF_ACCENT  = window.SHUF.accent;
  window.SHUF_GLOW    = window.SHUF.glow;
  window.SHUF_GLOW_FILL = window.SHUF.glowFill;
  window.SHUF_TINT = window.SHUF.tint;
})();
// --- /SHUFFLIZER_PALETTE_CORE ---

// Palette step1: override primary stroke (RGBA)
window.SHUF_PRIMARY = "rgba(255,146,0,0.95)"; // Ember test
window.SHUF_TINT = 0.65; // 0=no tint (full rainbow), 1=full palette
window.SHUF_ACCENT = "rgba(255,205,115,0.90)"; // Ember highlight
window.SHUF_GLOW   = "rgba(215,123,95,0.90)";  // Ember glow/shadow
window.SHUF_GLOW_FILL = "rgba(215,123,95,0.25)"; // Ember soft fill


const audio = initAudio(audioEl, { startMuted: ui.state.muted });

// Now playing (Icecast status JSON)
ui.state.trackTitle = "";


ui.els.muted.addEventListener("change", () => {
  audio.setMuted(ui.els.muted.checked);
});

audioEl.addEventListener("play", () => {
  audio.setMuted(ui.els.muted.checked);
});

// Keyboard controls
window.addEventListener("keydown", (e) => {
  const tag = (document.activeElement && document.activeElement.tagName || "").toLowerCase();
  if (tag === "input" || tag === "select" || tag === "textarea") return;

  if (e.code === "BracketLeft") {
    e.preventDefault();
    ui.api.prev();
  } else if (e.code === "BracketRight") {
    e.preventDefault();
    ui.api.next();
  } else if (e.code === "Backslash") {
    e.preventDefault();
    ui.api.random();
  } else if (e.code === "KeyM") {
    e.preventDefault();
    ui.api.mutate(e.shiftKey ? 0.85 : 0.35);
  }
});

startEngine(canvas, audio.analyser, ui.state);

startNowPlaying({
  host: window.location.hostname,
  intervalMs: 2000,
  onUpdate: (title) => { ui.state.trackTitle = title; const el = document.getElementById("npTextUi"); if (el) el.textContent = title; spawnTitleParticle(title); },
});

// SHUFFLIZER_AUTOHIDE_UI
(function setupAutoHideUI() {
  const ui = document.getElementById("ui");
  if (!ui) return;

  const HIDE_AFTER_MS = 4000;
  let t = null;

  function showUI() {
    document.body.classList.remove("ui-hidden");
  }

  function hideUI() {
    document.body.classList.add("ui-hidden");
  }

  function arm() {
    clearTimeout(t);
    t = setTimeout(hideUI, HIDE_AFTER_MS);
  }

  // Wake on any user interaction (listeners survive even when UI is hidden)
  function wake() {
    showUI();
    arm();
  }

  const events = ["pointerdown", "pointermove", "mousemove", "touchstart", "keydown", "wheel"];
  for (const ev of events) {
    window.addEventListener(ev, wake, { passive: true, capture: true });
  }

  arm();
})();
// SHUFFLIZER_NP_TO_UI
