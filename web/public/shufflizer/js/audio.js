export function initAudio(audioEl, { startMuted = true } = {}) {
  audioEl.crossOrigin = "anonymous";

  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const src = audioCtx.createMediaElementSource(audioEl);

  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 1024;

  const gain = audioCtx.createGain();
  gain.gain.value = startMuted ? 0.0 : 1.0;

  src.connect(analyser);
  analyser.connect(gain);
  gain.connect(audioCtx.destination);

  function setMuted(muted) {
    gain.gain.value = muted ? 0.0 : 1.0;
  }

  audioEl.addEventListener("play", async () => {
    try { await audioCtx.resume(); } catch {}
  });

  return { audioCtx, analyser, setMuted };
}
