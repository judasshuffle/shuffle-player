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

function hsl(h, s, l) {
  h = ((h % 360) + 360) % 360;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs((h / 60) % 2 - 1));
  const m = l - c / 2;
  let r = 0, g = 0, b = 0;
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return {r: Math.round((r + m) * 255), g: Math.round((g + m) * 255), b: Math.round((b + m) * 255)};
}

function mix(a, b, amount) {
  return {r: Math.round(a.r + (b.r - a.r) * amount), g: Math.round(a.g + (b.g - a.g) * amount), b: Math.round(a.b + (b.b - a.b) * amount)};
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

  render({ctx, w, h, t, dt, audio, params, globals, state}) {
    const feedback = ensureFeedback(state, ctx, w, h);
    const feedbackCtx = feedback.getContext("2d");
    const cx = w / 2;
    const cy = h / 2;
    const elapsed = clamp(Number(dt) || 0, 0, 0.12);
    const energy = clamp(audio.energy || 0, 0, 1);
    const activity = clamp((energy - 0.018) / 0.16, 0, 1);
    const bass = averageBand(audio.freq, 0, 14);
    const treble = averageBand(audio.freq, Math.floor(audio.freq.length * 0.42), audio.freq.length);
    // Keep feedback short enough that old bright seams cannot accumulate into
    // a white wash, especially while the canvas is in additive mode elsewhere.
    const decaySeconds = Math.max(0.35, Number(params.echoDecay) || 1.2);
    const trailAlpha = Math.exp(-elapsed / decaySeconds);
    const rotation = (Number(params.echoRotation) || 0.08) * elapsed;
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

    // Keep a quiet motion floor so the visualizer never looks frozen when the
    // stream is between beats or the analyser reports near-silence.
    const motionActivity = Math.max(activity, 0.22);
    if (motionActivity > 0.01 || audio.beat) {
      const primary = paletteColor(false);
      const accent = paletteColor(true);
      const stretch = 0.78 + bass * (Number(params.echoBassStretch) || 1.7);
      const seamGain = Number(params.echoSeamGain) || 1.0;
      const seamCount = 36;
      // Use the portrait screen as a stage, rather than keeping the loom in
      // a small central patch.  The quiet-state floor still leaves room for
      // the title, while the active strands can reach the full width/height.
      const span = h * (1.08 + bass * 0.28) * stretch;
      const halfHeight = Math.min(h * 0.62, h * (0.42 + bass * 0.22));

      ctx.save();
      // Coloured seams must replace/fade naturally; additive compositing makes
      // repeated feedback converge to white.
      ctx.globalCompositeOperation = "source-over";
      ctx.lineCap = "round";
      for (let i = 0; i < seamCount; i++) {
        const ratio = i / (seamCount - 1);
        const bin = Math.min(audio.freq.length - 1, 2 + Math.floor(ratio * audio.freq.length * 0.48));
        // A time-based floor keeps the loom visible when the radio stream is
        // quiet; audio still lifts the same strands and drives the shape.
        const audioLevel = audio.freq[bin] / 255;
        const motionLevel = 0.28 + 0.22 * (0.5 + 0.5 * Math.sin(Number(t) * 0.002 + i * 0.7));
        const level = Math.max(audioLevel, motionLevel);
        const seam = motionActivity * (0.28 + level * 0.72);
        if (seam < 0.018) continue;

        const row = (ratio - 0.5) * span;
        const bend = (level - 0.35) * 55 + Math.sin(i * 1.7 + bass * 8) * 10;
        const bright = clamp(0.18 + seam * 0.75 + (audio.beat ? treble * 0.35 : 0), 0, 0.82);
        const width = 1.0 + seam * 3.0 + (audio.beat && i % 3 === 0 ? 1.8 : 0);
        const spectrum = hsl((Number(t) * 0.035 + i * (360 / seamCount)) % 360, 0.92, 0.58);
        const color = audio.beat && i % 3 === 0 ? accent : mix(primary, spectrum, 0.60);

        const drawSeam = (mirror) => {
          const my = mirror ? -row : row;
          const wave = mirror ? -bend : bend;
          ctx.beginPath();
          ctx.moveTo(0, cy + my);
          ctx.bezierCurveTo(
            w * 0.28, cy + my + wave * 1.8 + Math.sin(i + Number(t) * 0.001) * halfHeight * 0.08,
            w * 0.72, cy + my - wave * 1.8 - Math.sin(i + Number(t) * 0.001) * halfHeight * 0.08,
            w, cy + my,
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
