function clamp(x, a, b) {
  return Math.max(a, Math.min(b, x));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function rgba(c, a) {
  return `rgba(${c.r},${c.g},${c.b},${a})`;
}

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
  t = clamp(t, 0, 1);
  return {
    r: Math.round(a.r + (b.r - a.r) * t),
    g: Math.round(a.g + (b.g - a.g) * t),
    b: Math.round(a.b + (b.b - a.b) * t),
  };
}

function polygonPoints(radius, sides, rotation = 0) {
  const pts = [];
  for (let i = 0; i < sides; i++) {
    const a = rotation - Math.PI / 2 + (i / sides) * Math.PI * 2;
    pts.push({
      x: Math.cos(a) * radius,
      y: Math.sin(a) * radius,
      a
    });
  }
  return pts;
}

function sampleWaveNorm(wave, idx01) {
  if (!wave || !wave.length) return 0;
  const i = Math.floor(clamp(idx01, 0, 0.9999) * wave.length);
  return (wave[i] - 128) / 128;
}

function getSpectralInfo(freq) {
  if (!freq || !freq.length) {
    return { bass: 0, mid: 0, treble: 0, centroid: 0, pitchNorm: 0 };
  }

  let sum = 0;
  let weighted = 0;
  let bass = 0, mid = 0, treble = 0;

  for (let i = 0; i < freq.length; i++) {
    const v = freq[i] / 255;
    sum += v;
    weighted += v * i;

    const p = i / freq.length;
    if (p < 0.18) bass += v;
    else if (p < 0.55) mid += v;
    else treble += v;
  }

  const centroid = sum > 0 ? weighted / sum / Math.max(1, freq.length - 1) : 0;
  return {
    bass: bass / Math.max(1, freq.length * 0.18),
    mid: mid / Math.max(1, freq.length * 0.37),
    treble: treble / Math.max(1, freq.length * 0.45),
    centroid,
    pitchNorm: centroid
  };
}

function drawPyramidModel(ctx, x, y, angle, spin, size, hue, glowOn, alpha) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle + spin);
  ctx.lineJoin = "round";

  const tip = { x: 0, y: -size * 1.15 };
  const bl  = { x: -size * 0.95, y: size * 0.58 };
  const br  = { x:  size * 0.95, y: size * 0.58 };
  const mid = { x: 0, y: size * 0.15 };

  const cFront = hslToRgb(hue, 0.98, 0.60);
  const cLeft  = hslToRgb(hue - 16, 0.95, 0.48);
  const cRight = hslToRgb(hue + 10, 0.98, 0.36);
  const cHi    = hslToRgb(hue + 6, 1.00, 0.82);

  if (glowOn) {
    ctx.shadowBlur = size * 1.4;
    ctx.shadowColor = rgba(cFront, alpha * 0.6);
  }

  // left face
  ctx.beginPath();
  ctx.moveTo(tip.x, tip.y);
  ctx.lineTo(bl.x, bl.y);
  ctx.lineTo(mid.x, mid.y);
  ctx.closePath();
  ctx.fillStyle = rgba(cLeft, alpha);
  ctx.fill();

  // right/front face
  ctx.beginPath();
  ctx.moveTo(tip.x, tip.y);
  ctx.lineTo(mid.x, mid.y);
  ctx.lineTo(br.x, br.y);
  ctx.closePath();
  ctx.fillStyle = rgba(cFront, alpha);
  ctx.fill();

  // bottom face
  ctx.beginPath();
  ctx.moveTo(mid.x, mid.y);
  ctx.lineTo(bl.x, bl.y);
  ctx.lineTo(br.x, br.y);
  ctx.closePath();
  ctx.fillStyle = rgba(cRight, alpha);
  ctx.fill();

  // highlight edges
  ctx.shadowBlur = 0;
  ctx.strokeStyle = rgba(cHi, alpha * 0.65);
  ctx.lineWidth = Math.max(1, size * 0.08);

  ctx.beginPath();
  ctx.moveTo(tip.x, tip.y);
  ctx.lineTo(mid.x, mid.y);
  ctx.lineTo(br.x, br.y);
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(tip.x, tip.y);
  ctx.lineTo(bl.x, bl.y);
  ctx.stroke();

  ctx.restore();
}

function drawWaveRibbon(ctx, cx, cy, w, h, t, wave, bandIndex, amp, hueBase, alphaBase) {
  const y = lerp(h * 0.16, h * 0.42, bandIndex / 7);
  const spread = lerp(w * 0.56, w * 0.12, bandIndex / 7);
  const thickness = lerp(10, 3, bandIndex / 7) * (0.8 + amp * 1.2);
  const sway = Math.sin(t * (1.2 + bandIndex * 0.08) + bandIndex * 0.7) * (18 + amp * 24);

  const p1 = 0.08 + bandIndex * 0.07;
  const p2 = 0.34 + bandIndex * 0.05;
  const p3 = 0.61 + bandIndex * 0.03;

  const v1 = sampleWaveNorm(wave, (p1 + t * 0.05) % 1);
  const v2 = sampleWaveNorm(wave, (p2 + t * 0.04) % 1);
  const v3 = sampleWaveNorm(wave, (p3 + t * 0.03) % 1);

  const c1 = hslToRgb(hueBase + bandIndex * 4, 0.95, 0.42);
  const c2 = hslToRgb(hueBase + 10 + bandIndex * 3, 0.98, 0.56);
  const c3 = hslToRgb(hueBase - 8, 0.90, 0.30);

  const grad = ctx.createLinearGradient(cx - spread, y, cx + spread, y);
  grad.addColorStop(0.00, rgba(c3, 0));
  grad.addColorStop(0.15, rgba(c1, alphaBase * 0.40));
  grad.addColorStop(0.50, rgba(c2, alphaBase));
  grad.addColorStop(0.85, rgba(c1, alphaBase * 0.40));
  grad.addColorStop(1.00, rgba(c3, 0));

  ctx.strokeStyle = grad;
  ctx.lineWidth = thickness;
  ctx.lineCap = "round";

  // left ribbon
  ctx.beginPath();
  ctx.moveTo(-40, y + sway + v1 * 40 * amp);
  ctx.bezierCurveTo(
    w * 0.18,
    y + v2 * 70 * amp,
    cx - spread * 0.34,
    lerp(y, cy, 0.78) + v3 * 28 * amp,
    cx,
    cy
  );
  ctx.stroke();

  // right ribbon
  ctx.beginPath();
  ctx.moveTo(w + 40, y - sway - v1 * 40 * amp);
  ctx.bezierCurveTo(
    w * 0.82,
    y - v2 * 70 * amp,
    cx + spread * 0.34,
    lerp(y, cy, 0.78) - v3 * 28 * amp,
    cx,
    cy
  );
  ctx.stroke();
}

function drawStars(ctx, cx, cy, w, h, t) {
  const count = 160;
  for (let i = 0; i < count; i++) {
    let z = (i * 0.041 + t * 0.18) % 1;
    z = z * z;
    const a = (i % 28) / 28 * Math.PI * 2;
    const r = lerp(20, Math.max(w, h) * 0.60, z);
    const x = cx + Math.cos(a) * r;
    const y = cy + Math.sin(a) * r * 0.72 + h * 0.10;
    const s = lerp(0.4, 1.8, z);
    const alpha = lerp(0.06, 0.55, z);

    ctx.fillStyle = `rgba(255,255,255,${alpha})`;
    ctx.fillRect(x, y, s, s);
  }
}

export const effect = {
  id: "tempestBonusPyramids",
  name: "Tempest Bonus Pyramids",
  defaults: {},
  init() {},
  update() {},

  render({ ctx, w, h, t, dt, audio, params, globals, state }) {
    const energy = audio?.energy || 0;
    const beat = !!audio?.beat;
    const wave = audio?.wave || [];
    const freq = audio?.freq || [];

    params = params || {};
    globals = globals || {};
    state = state || {};

    if (state.time == null) state.time = 0;
    if (state.beatPulse == null) state.beatPulse = 0;
    if (state.breathe == null) state.breathe = 0;
    if (state.lastBeatTime == null) state.lastBeatTime = null;
    if (state.tempoSec == null) state.tempoSec = 0.48; // sane default
    if (state.phase == null) state.phase = 0;

    state.time += dt || 0.016;
    state.beatPulse *= 0.90;
    if (beat) {
      state.beatPulse = 1.0;
      if (state.lastBeatTime != null) {
        const gap = Math.max(0.18, Math.min(1.20, state.time - state.lastBeatTime));
        state.tempoSec = lerp(state.tempoSec, gap, 0.30);
      }
      state.lastBeatTime = state.time;
    }

    const spec = getSpectralInfo(freq);
    const amp = clamp(energy * 6.0, 0, 1.4);
    const tempoHz = 1 / Math.max(0.24, state.tempoSec);
    state.phase += dt * tempoHz * Math.PI * 2;
    state.breathe = lerp(
      state.breathe,
      0.5 + 0.5 * Math.sin(state.phase * 0.5),
      0.08
    );

    const bass = clamp(spec.bass * 1.6, 0, 1.2);
    const mid = clamp(spec.mid * 1.4, 0, 1.2);
    const treble = clamp(spec.treble * 1.8, 0, 1.2);
    const pitchNorm = clamp(spec.pitchNorm, 0, 1);
    const pulse = state.beatPulse;

    const cx = w / 2;
    const cy = h * 0.57;

    const trailAmt = globals.phosphor ? (params.trail ?? 0.09) : 0.16;
    ctx.fillStyle = `rgba(0,0,0,${trailAmt})`;
    ctx.fillRect(0, 0, w, h);

    // Background starfield
    drawStars(ctx, cx, cy, w, h, state.time);

    // Orange waveform ribbons
    ctx.save();
    if (globals.glow) {
      ctx.globalCompositeOperation = "screen";
      ctx.shadowBlur = 12 + amp * 18;
      ctx.shadowColor = "rgba(255,140,40,0.35)";
    }

    const ribbonHue = lerp(18, 42, 0.35 + pitchNorm * 0.4);
    for (let i = 0; i < 8; i++) {
      drawWaveRibbon(
        ctx,
        cx,
        cy,
        w,
        h,
        state.time,
        wave,
        i,
        0.7 + amp * 0.9 + bass * 0.4,
        ribbonHue,
        0.16 + mid * 0.12 + pulse * 0.18
      );
    }
    ctx.restore();

    // Centre portal glow
    const portalBase = parseRGB((window.SHUF && window.SHUF.accent) || window.SHUF_ACCENT || "rgb(120,255,220)");
    const portalGlow = mixRGB(portalBase, { r: 255, g: 255, b: 255 }, 0.45 + treble * 0.25);
    const portalR = 18 + amp * 18 + pulse * 22;

    const portalGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, portalR * 2.6);
    portalGrad.addColorStop(0.00, rgba({ r: 255, g: 255, b: 255 }, 0.95));
    portalGrad.addColorStop(0.10, rgba(portalGlow, 0.75));
    portalGrad.addColorStop(0.24, rgba(portalGlow, 0.28));
    portalGrad.addColorStop(1.00, "rgba(0,0,0,0)");
    ctx.fillStyle = portalGrad;
    ctx.beginPath();
    ctx.arc(cx, cy, portalR * 2.6, 0, Math.PI * 2);
    ctx.fill();

    // Hoops and pyramids
    const hoopCount = 11;
    const sideCount = 3;
    const baseHoopColor = parseRGB((window.SHUF && window.SHUF.primary) || window.SHUF_PRIMARY || "rgb(220,120,255)");

    for (let i = 0; i < hoopCount; i++) {
      let z = (i / hoopCount + state.time * (0.18 + tempoHz * 0.05)) % 1;
      z = 1 - z;
      const near = 1 - z;
      const scale = Math.pow(near, 2.15);

      const radius = lerp(10, Math.min(w, h) * 0.30, scale) * (0.92 + amp * 0.10 + pulse * 0.10);
      const drift = state.time * (0.75 + tempoHz * 0.10) + i * 0.72;
      const px = cx
        + Math.sin(drift) * lerp(0, w * 0.14, scale)
        + Math.sin(state.time * 0.6 + i) * w * 0.015;
      const py = cy
        + Math.cos(drift * 1.15) * lerp(0, h * 0.09, scale)
        + Math.sin(state.phase * 0.5 + i * 0.4) * (6 + state.breathe * 10);

      const rot = state.time * (0.85 + tempoHz * 0.18) + i * 0.55;
      const hoopAlpha = lerp(0.18, 0.88, scale);
      const hoopColor = mixRGB(baseHoopColor, portalBase, 0.22 + pitchNorm * 0.35);

      ctx.save();
      ctx.translate(px, py);
      ctx.rotate(rot);
      ctx.lineJoin = "round";

      const pts = polygonPoints(radius, sideCount, 0);

      ctx.strokeStyle = rgba(hoopColor, hoopAlpha * 0.85);
      ctx.lineWidth = Math.max(1.6, radius * (0.045 + amp * 0.01));
      if (globals.glow) {
        ctx.shadowBlur = 8 + amp * 10 + pulse * 10;
        ctx.shadowColor = rgba(hoopColor, 0.50);
      }

      ctx.beginPath();
      for (let p = 0; p < pts.length; p++) {
        if (p === 0) ctx.moveTo(pts[p].x, pts[p].y);
        else ctx.lineTo(pts[p].x, pts[p].y);
      }
      ctx.closePath();
      ctx.stroke();

      for (let p = 0; p < pts.length; p++) {
        const pt = pts[p];

        const cornerPitch = clamp(
          pitchNorm * 0.55 +
          (p / sideCount) * 0.18 +
          treble * 0.18 +
          Math.abs(sampleWaveNorm(wave, (i * 0.09 + p * 0.17 + state.time * 0.05) % 1)) * 0.12,
          0, 1
        );

        const hue = lerp(320, 188, cornerPitch); // magenta -> cyan
        const pyramidSpin = state.time * (1.5 + p * 0.7 + i * 0.06 + tempoHz * 0.4);
        const pyramidSize =
          Math.max(4, radius * (0.16 + amp * 0.04 + pulse * 0.03)) *
          (0.88 + bass * 0.18 + treble * 0.08);

        drawPyramidModel(
          ctx,
          pt.x,
          pt.y,
          pt.a,
          pyramidSpin,
          pyramidSize,
          hue,
          !!globals.glow,
          hoopAlpha
        );
      }

      ctx.restore();
    }
  },
};