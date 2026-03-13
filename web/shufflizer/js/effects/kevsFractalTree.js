function parseRGB(s) {
  const m = /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i.exec(String(s || ""));
  if (!m) return { r: 255, g: 255, b: 255 };
  return { r: +m[1], g: +m[2], b: +m[3] };
}

function hslToRgb(h, s, l) {
  h = ((h % 360) + 360) % 360;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let r = 0, g = 0, b = 0;

  if (h < 60)      { r = c; g = x; b = 0; }
  else if (h < 120){ r = x; g = c; b = 0; }
  else if (h < 180){ r = 0; g = c; b = x; }
  else if (h < 240){ r = 0; g = x; b = c; }
  else if (h < 300){ r = x; g = 0; b = c; }
  else             { r = c; g = 0; b = x; }

  return {
    r: Math.round((r + m) * 255),
    g: Math.round((g + m) * 255),
    b: Math.round((b + m) * 255),
  };
}

function mixRGB(a, b, t) {
  t = Math.max(0, Math.min(1, t));
  return {
    r: Math.round(a.r + (b.r - a.r) * t),
    g: Math.round(a.g + (b.g - a.g) * t),
    b: Math.round(a.b + (b.b - a.b) * t),
  };
}

function rgba(c, a) {
  return `rgba(${c.r},${c.g},${c.b},${a})`;
}

function drawLeaf(ctx, x, y, size, color, glow) {
  ctx.save();
  ctx.fillStyle = color;
  if (glow) {
    ctx.shadowBlur = size * 2.2;
    ctx.shadowColor = color;
  }
  ctx.beginPath();
  ctx.arc(x, y, size, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawBranch(ctx, x, y, len, angle, depth, width, spread, wiggle, state, leafiness, glow) {
  if (depth <= 0 || len < 2) return;

  const bend = wiggle * 0.12 * Math.sin(state.time * 3.2 + depth * 0.7 + x * 0.002);
  const a = angle + bend;

  const x2 = x + Math.cos(a) * len;
  const y2 = y + Math.sin(a) * len;

  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x2, y2);
  ctx.stroke();

  // Leaf clusters near the tips
  if (depth <= 2) {
    const leafCount = 2 + Math.floor(leafiness * 4);
    for (let i = 0; i < leafCount; i++) {
      const jitterA = a + (Math.random() - 0.5) * 1.2;
      const jitterR = (Math.random() * 8) + 2;
      const lx = x2 + Math.cos(jitterA) * jitterR;
      const ly = y2 + Math.sin(jitterA) * jitterR;

      const leafHue = (state.leafHueBase + depth * 18 + i * 22 + state.time * 40) % 360;
      const leafRgb = hslToRgb(leafHue, 0.95, 0.60 + Math.random() * 0.1);
      const leafSize = Math.max(1.5, width * (0.9 + Math.random() * 0.8));

      drawLeaf(ctx, lx, ly, leafSize, rgba(leafRgb, 0.90), glow);
    }
  }

  const childLen = len * Math.min(0.82, 0.68 + wiggle * 0.06);
  const childWidth = Math.max(0.5, width * 0.72);

  drawBranch(ctx, x2, y2, childLen, a - spread, depth - 1, childWidth, spread, wiggle, state, leafiness, glow);
  drawBranch(ctx, x2, y2, childLen, a + spread, depth - 1, childWidth, spread, wiggle, state, leafiness, glow);
}

export const effect = {
  id: "kevsFractalTree",
  name: "Kevs Fractal Tree",
  defaults: {},
  init() {},
  update() {},

  render({ ctx, w, h, audio, params, globals, state }) {
    const energy = audio?.energy || 0;
    const beat = !!audio?.beat;
    const wave = audio?.wave || [];
    params = params || {};
    globals = globals || {};
    state = state || {};

    if (state.time == null) state.time = 0;
    if (state.beatPulse == null) state.beatPulse = 0;
    if (state.leafHueBase == null) state.leafHueBase = Math.random() * 360;

    state.time += 0.016;
    state.beatPulse *= 0.92;
    if (beat) {
      state.beatPulse = 1.0;
      state.leafHueBase = (state.leafHueBase + 25) % 360;
    }

    const trailAmt = globals.phosphor ? (params.trail ?? 0.10) : 0.18;
    ctx.fillStyle = `rgba(0,0,0,${trailAmt})`;
    ctx.fillRect(0, 0, w, h);

    const cx = w / 2;
    const rootY = h * 0.93;

    const waveSample = wave.length
      ? ((wave[(state.time * 60 | 0) % wave.length] - 128) / 128)
      : 0;

    const wiggle = energy * 0.8 + Math.abs(waveSample) * 0.8;
    const pulse = state.beatPulse;

    const depth = 8 + Math.floor(energy * 3) + (pulse > 0.6 ? 1 : 0);
    const trunkLen = Math.min(w, h) * (0.18 + energy * 0.10 + pulse * 0.05);
    const spread = 0.34 + energy * 0.18 + pulse * 0.12 + Math.sin(state.time * 0.9) * 0.04;
    const trunkWidth = 6 + energy * 5 + pulse * 3;
    const leafiness = 0.4 + energy * 0.8 + pulse * 0.5;

    const hue = (110 + energy * 120 + state.time * 10) % 360;
    const rainbow = hslToRgb(hue, 1.0, 0.58);

    const primary = parseRGB((window.SHUF && window.SHUF.primary) || window.SHUF_PRIMARY || "rgb(0,255,102)");
    const accent = parseRGB((window.SHUF && window.SHUF.accent) || window.SHUF_ACCENT || "rgb(0,200,255)");
    const paletteMix = mixRGB(primary, accent, 0.5 + pulse * 0.3);
    const finalColor = mixRGB(rainbow, paletteMix, 0.65);

    ctx.save();
    ctx.lineCap = "round";
    ctx.strokeStyle = rgba(finalColor, 0.95);

    if (globals.glow) {
      ctx.globalCompositeOperation = "lighter";
      ctx.shadowBlur = 10 + energy * 18 + pulse * 18;
      ctx.shadowColor = ctx.strokeStyle;
    }

    drawBranch(
      ctx,
      cx,
      rootY,
      trunkLen,
      -Math.PI / 2,
      depth,
      trunkWidth,
      spread,
      wiggle,
      state,
      leafiness,
      !!globals.glow
    );

    ctx.restore();
  },
};