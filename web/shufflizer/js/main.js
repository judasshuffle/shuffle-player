import { initUI } from "./ui.js";
import { initAudio } from "./audio.js";
import { startEngine } from "./engine.js";
import { startNowPlaying } from "./nowPlaying.js";
import { spawnTitleParticle } from "./visuals.js";

const canvas = document.getElementById("c");
const audioEl = document.getElementById("audio");

// Use the page host (Pi IP) so remote clients hit the Pi's Icecast.
audioEl.src = `http://${location.hostname}:8001/stream.mp3`;
audioEl.load();

const ui = initUI();
// --- SHUFFLIZER_PALETTE_CORE ---
window.SHUF_PRESETS = window.SHUF_PRESETS || {"Phosphor Prime":{"primary":"rgba(0,255,102,0.95)","accent":"rgba(102,255,208,0.90)","glow":"rgba(0,170,68,0.90)","glowFill":"rgba(0,170,68,0.25)","tint":0.65},"Ember Grid":{"primary":"rgba(255,146,0,0.95)","accent":"rgba(255,205,115,0.90)","glow":"rgba(215,123,95,0.90)","glowFill":"rgba(215,123,95,0.25)","tint":0.65},"Copper Pulse":{"primary":"rgba(241,142,63,0.95)","accent":"rgba(229,149,121,0.90)","glow":"rgba(193,76,50,0.90)","glowFill":"rgba(193,76,50,0.25)","tint":0.65},"Overdrive":{"primary":"rgba(255,197,0,0.95)","accent":"rgba(236,65,11,0.90)","glow":"rgba(179,0,25,0.90)","glowFill":"rgba(179,0,25,0.25)","tint":0.7},"Midnight Alloy":{"primary":"rgba(255,164,0,0.95)","accent":"rgba(108,52,0,0.90)","glow":"rgba(65,34,42,0.90)","glowFill":"rgba(65,34,42,0.25)","tint":0.7},"Analog Drift":{"primary":"rgba(255,205,135,0.95)","accent":"rgba(188,117,118,0.90)","glow":"rgba(105,107,126,0.90)","glowFill":"rgba(105,107,126,0.25)","tint":0.6}};
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
