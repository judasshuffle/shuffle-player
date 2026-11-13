function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

function parseRGB(value) {
  const match = /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i.exec(String(value || ""));
  return match ? {r: +match[1], g: +match[2], b: +match[3]} : {r: 0, g: 255, b: 170};
}

function rgba(color, alpha) {
  return `rgba(${color.r},${color.g},${color.b},${alpha})`;
}

function paletteColor(accent = false) {
  if (typeof window === "undefined") return {r: 0, g: 255, b: 170};
  const palette = window.SHUF || {};
  return parseRGB(accent ? (palette.accent || window.SHUF_ACCENT) :
    (palette.primary || window.SHUF_PRIMARY));
}

function averageBand(freq, start, end) {
  let total = 0;
  let count = 0;
  for (let i = start; i < Math.min(end, freq.length); i++) {
    total += freq[i];
    count++;
  }
  return count ? total / count / 255 : 0;
}

function ensureFeedback(state, ctx, w, h) {
  if (!state.feedback) state.feedback = document.createElement("canvas");
  if (state.feedback.width !== w || state.feedback.height !== h) {
    state.feedback.width = w;
    state.feedback.height = h;
    state.feedback.getContext("2d").clearRect(0, 0, w, h);
  }
  return state.feedback;
}

export const effect = {
  id: "echoLoom",
  name: "Echo Loom",
  defaults: {},
  init() {},
  update() {},

  render({ctx, w, h, dt, audio, params, globals, state}) {
    const feedback = ensureFeedback(state, ctx, w, h);
    const feedbackCtx = feedback.getContext("2d");
    const cx = w / 2;
    const cy = h / 2;
    const elapsed = clamp(Number(dt) || 0, 0, 0.12);
    const energy = clamp(audio.energy || 0, 0, 1);
    const activity = clamp((energy - 0.018) / 0.16, 0, 1);
    const bass = averageBand(audio.freq, 0, 14);
    const treble = averageBand(audio.freq, Math.floor(audio.freq.length * 0.42), audio.freq.length);
    const decaySeconds = Math.max(0.45, Number(params.echoDecay) || 2.4);
    const trailAlpha = Math.exp(-elapsed / decaySeconds);
    const rotation = (Number(params.echoRotation) || 0.018) * elapsed;
    const offset = (Number(params.echoOffset) || 14) * elapsed * (0.35 + bass);

    // Time-based feedback keeps the look consistent at 30 FPS and 60 FPS.
    ctx.save();
    ctx.fillStyle = `rgba(0,0,0,${1 - trailAlpha})`;
    ctx.fillRect(0, 0, w, h);
    ctx.globalAlpha = trailAlpha;
    ctx.translate(cx + offset, cy + offset * 0.42);
    ctx.rotate(rotation);
    ctx.drawImage(feedback, -cx, -cy, w, h);
    ctx.restore();

    if (activity > 0.01 || audio.beat) {
      const primary = paletteColor(false);
      const accent = paletteColor(true);
      const stretch = 0.78 + bass * (Number(params.echoBassStretch) || 1.7);
      const seamGain = Number(params.echoSeamGain) || 1.0;
      const seamCount = 36;
      const span = Math.min(w, h) * (0.34 + bass * 0.52) * stretch;
      const halfHeight = Math.min(h * 0.38, 100 + bass * h * 0.28);

      ctx.save();
      ctx.globalCompositeOperation = globals.glow ? "lighter" : "source-over";
      ctx.lineCap = "round";
      for (let i = 0; i < seamCount; i++) {
        const ratio = i / (seamCount - 1);
        const bin = Math.min(audio.freq.length - 1, 2 + Math.floor(ratio * audio.freq.length * 0.48));
        const level = audio.freq[bin] / 255;
        const seam = activity * level;
        if (seam < 0.035) continue;

        const x = (ratio - 0.5) * span;
        const bend = (level - 0.35) * 55 + Math.sin(i * 1.7 + bass * 8) * 10;
        const bright = clamp(0.22 + seam * 0.75 + (audio.beat ? treble * 0.65 : 0), 0, 1);
        const width = 0.7 + seam * 2.2 + (audio.beat && i % 3 === 0 ? 1.8 : 0);
        const color = audio.beat && i % 3 === 0 ? accent : primary;

        const drawSeam = (mirror) => {
          const mx = mirror ? -x : x;
          const my = mirror ? -bend : bend;
          ctx.beginPath();
          ctx.moveTo(cx + mx * 0.12, cy - halfHeight * (0.2 + level * 0.35));
          ctx.bezierCurveTo(
            cx + mx * 0.68 + my * 0.22, cy - halfHeight * 0.12,
            cx + mx * 0.88 - my * 0.18, cy + halfHeight * 0.24,
            cx + mx, cy + halfHeight * (0.58 + level * 0.34),
          );
          ctx.stroke();
        };

        ctx.globalAlpha = bright * seamGain;
        ctx.lineWidth = width;
        ctx.strokeStyle = rgba(color, 1);
        drawSeam(false);
        drawSeam(true);
      }
      ctx.restore();
    }

    // Capture the complete current frame for the next time-based echo.
    feedbackCtx.clearRect(0, 0, w, h);
    feedbackCtx.drawImage(ctx.canvas, 0, 0, w, h);
  },
};
