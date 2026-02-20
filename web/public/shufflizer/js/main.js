import { initUI } from "./ui.js";
import { initAudio } from "./audio.js";
import { startEngine } from "./engine.js";
import { startNowPlaying } from "./nowPlaying.js";

const canvas = document.getElementById("c");
const audioEl = document.getElementById("audio");

// Use the page host (Pi IP) so remote clients hit the Pi's Icecast.
audioEl.src = "http://" + window.location.hostname + ":8001/stream.mp3";
audioEl.load();

const ui = initUI();
const audio = initAudio(audioEl, { startMuted: ui.state.muted });

// Now playing (Icecast status JSON)
ui.state.trackTitle = "";
startNowPlaying({
  host: window.location.hostname,
  intervalMs: 2000,
  onUpdate: (title) => { ui.state.trackTitle = title; },
});

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
