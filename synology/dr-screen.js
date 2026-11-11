/* Listener only: never calls station controls or loads a second audio stream. */
const player = document.getElementById('player');
const status = document.getElementById('status');
const button = document.getElementById('start');
const volumeSlider = document.getElementById('volume');
const context = new (window.AudioContext || window.webkitAudioContext)();
const source = context.createMediaElementSource(player);
const analyser = context.createAnalyser();
analyser.fftSize = 1024;
const gain = context.createGain();
let volume = 100;
source.connect(analyser);
analyser.connect(gain);
gain.connect(context.destination);
// Shufflizer's existing embedded runtime consumes this exact analyser.
window.playerAudio = {audioCtx: context, analyser, setMuted() {}};
window.currentTrackTitle = '';
const frame = document.createElement('iframe');
frame.src = '/visualizer/index.html?embed=1';
frame.title = 'Shufflizer live MP3';
frame.allow = 'autoplay';
document.getElementById('visualizer').append(frame);
function showState() {
  const playing = !player.paused && context.state === 'running';
  status.textContent = playing ? `Live screen audio · volume ${volume}%` :
    'Autoplay blocked or audio suspended. Click Enable screen audio in DarkRide.';
  button.hidden = playing;
}
function start() {
  if (context.state !== 'running') status.textContent = 'Audio suspended. Click Enable screen audio if it does not start.';
  // Both calls happen during the gesture; neither waits for the other.
  const resume = context.resume();
  const play = player.play();
  Promise.all([resume, play]).then(showState).catch(error => {
    status.textContent = error.name === 'NotAllowedError' ?
      'DarkRide blocked autoplay. Click Enable screen audio.' :
      `Screen audio could not start (${error.name}). Click to retry.`;
    button.hidden = false;
  });
}
button.addEventListener('click', start);
function applyVolume(value) {
  volume = Math.max(0, Math.min(100, value));
  gain.gain.setValueAtTime(volume / 100, context.currentTime);
  volumeSlider.value = volume;
  showState();
}
volumeSlider.addEventListener('input', () => {
  applyVolume(Number(volumeSlider.value));
  if (bridgeConnected) window.EventBridge.emitWebEvent(JSON.stringify({sound: volume}));
});
context.addEventListener('statechange', showState);
player.addEventListener('playing', showState);
player.addEventListener('waiting', () => { status.textContent = 'Buffering live MP3…'; });
player.addEventListener('error', () => {
  status.textContent = 'Live MP3 unavailable. Check the station on the LAN dashboard, then retry.';
  button.hidden = false;
});
let bridgeTimer;
let bridgeConnected = false;
let visualizerReady = false;
frame.addEventListener('load', () => {
  visualizerReady = true;
  if (bridgeConnected) window.EventBridge.emitWebEvent(JSON.stringify({ready: true}));
});
function connectBridge() {
  const bridge = window.EventBridge;
  if (!bridge || !bridge.scriptEventReceived || !bridge.emitWebEvent) return;
  clearInterval(bridgeTimer);
  bridgeConnected = true;
  bridge.scriptEventReceived.connect(raw => {
    let message;
    try { message = typeof raw === 'string' ? JSON.parse(raw) : raw; } catch (_) { return; }
    if (!message || typeof message.volume !== 'number' || !Number.isFinite(message.volume)) return;
    applyVolume(message.volume);
  });
  bridge.emitWebEvent(JSON.stringify({hello: true}));
  if (visualizerReady) bridge.emitWebEvent(JSON.stringify({ready: true}));
}
bridgeTimer = setInterval(connectBridge, 100);
connectBridge();
start();
window.addEventListener('pagehide', () => { clearInterval(bridgeTimer); player.pause(); context.close(); });
