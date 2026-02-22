// --- SHUFFLIZER_TINT_HELPERS ---
function _shuf_parseRGB(s){
  // expects "rgb(r,g,b)" or "rgba(r,g,b,a)"
  const m = /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i.exec(String(s||""));
  if (!m) return {r:255,g:255,b:255};
  return {r:+m[1], g:+m[2], b:+m[3]};
}
function _shuf_hslToRgb(h,s,l){
  // h:0-360, s/l:0-1
  h = ((h % 360) + 360) % 360;
  const c = (1 - Math.abs(2*l - 1)) * s;
  const x = c * (1 - Math.abs(((h/60) % 2) - 1));
  const m = l - c/2;
  let r=0,g=0,b=0;
  if (h < 60)      { r=c; g=x; b=0; }
  else if (h <120) { r=x; g=c; b=0; }
  else if (h <180) { r=0; g=c; b=x; }
  else if (h <240) { r=0; g=x; b=c; }
  else if (h <300) { r=x; g=0; b=c; }
  else             { r=c; g=0; b=x; }
  return { r: Math.round((r+m)*255), g: Math.round((g+m)*255), b: Math.round((b+m)*255) };
}
function _shuf_mixRGB(a,b,t){
  t = Math.max(0, Math.min(1, t));
  return {
    r: Math.round(a.r + (b.r - a.r)*t),
    g: Math.round(a.g + (b.g - a.g)*t),
    b: Math.round(a.b + (b.b - a.b)*t),
  };
}
function _shuf_rgba(c,a){ return `rgba(${c.r},${c.g},${c.b},${a})`; }
// --- /SHUFFLIZER_TINT_HELPERS ---

let __scopeAng = 0;
let __scopeDrift = 0;

export const effect = {
  id: "tempestTunnel",
  name: "Tempest Tunnel",
  defaults: {
    segments: 16,
  },
  init() {},
  update() {},
  render({ ctx, w, h, t, audio, params, globals, state }) {
    const { energy, wave } = audio;
    const cx = w / 2, cy = h / 2;

    // Trail / phosphor
    const trailAmt = globals.phosphor ? params.trail : 1.0;
    ctx.fillStyle = `rgba(0,0,0,${trailAmt})`;
    ctx.fillRect(0, 0, w, h);

    // Stroke vibe
    // rainbow energy, tinted toward palette
    const _tint = (typeof window !== "undefined" && typeof (window.SHUF && typeof window.SHUF.tint==='number') ? window.SHUF.tint : window.SHUF_TINT === "number") ? (window.SHUF && typeof window.SHUF.tint==='number') ? window.SHUF.tint : window.SHUF_TINT : 0.65;
    const _h = (energy * 800) % 360;
    const _rain = _shuf_hslToRgb(_h, 1.0, 50);
    const _pal = _shuf_parseRGB((energy > 0.55 ? ((window.SHUF && window.SHUF.accent) ? window.SHUF.accent : window.SHUF_ACCENT || (window.SHUF && window.SHUF.primary) ? window.SHUF.primary : window.SHUF_PRIMARY) : ((window.SHUF && window.SHUF.primary) ? window.SHUF.primary : window.SHUF_PRIMARY || "rgba(0,255,102,1)")));
    const _mix = _shuf_mixRGB(_rain, _pal, _tint);
    ctx.strokeStyle = _shuf_rgba(_mix, 1.0);ctx.lineWidth = 2 + energy * 5;

    const glowOn = globals.glow;
    if (glowOn) {
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.shadowBlur = 10;
      ctx.shadowColor = ctx.strokeStyle;
    }

    // Spin
    state.angle = (state.angle ?? 0) + params.spin * 0.01 + energy * 0.1;

    // Rim ring
    const segments = state.segments ?? 16;
    const baseRadius = 200 + energy * 100 * params.zap;
    ctx.beginPath();
    for (let i = 0; i <= segments; i++) {
      const a = state.angle + (i / segments) * Math.PI * 2;
      const x = cx + Math.cos(a) * baseRadius;
      const y = cy + Math.sin(a) * baseRadius;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    if (glowOn) ctx.restore();

    // Spawn burst shapes on beat
    if (!state.shapes) state.shapes = [];
    if (audio.beat) {
      const n = params.spawn | 0;
      for (let i = 0; i < n; i++) {
        state.shapes.push({
          angle: Math.random() * Math.PI * 2,
          radius: 100 + Math.random() * 200,
          spin: (Math.random() - 0.5) * 0.1,
          life: 1,
        });
      }
    }

    // Draw shapes
    for (let i = state.shapes.length - 1; i >= 0; i--) {
      const s = state.shapes[i];
      s.angle += s.spin + energy * 0.1;
      s.radius += energy * 10;
      s.life -= 0.01;

      const x = cx + Math.cos(s.angle) * s.radius;
      const y = cy + Math.sin(s.angle) * s.radius;

      ctx.save();
      ctx.globalAlpha = Math.max(0, s.life);

      if (glowOn) {
        ctx.globalCompositeOperation = "lighter";
        ctx.shadowBlur = 10;
        ctx.shadowColor = ctx.strokeStyle;
      }

      ctx.beginPath();
      const size = 10 + energy * 50;
      for (let j = 0; j < 5; j++) {
        const a = s.angle + (j * Math.PI * 2) / 5;
        ctx.lineTo(x + Math.cos(a) * size, y + Math.sin(a) * size);
      }
      ctx.closePath();
      ctx.stroke();
      ctx.restore();

      if (s.life <= 0) state.shapes.splice(i, 1);
    }

    // Optional shockwave rings (shared style)
    if (!state.rings) state.rings = [];
    if (audio.beat && params.shockwave > 0.01) {
      state.rings.push({
        r: 60,
        speed: 6 + energy * params.shockwave * 18,
        a: 0.9,
        w: 2 + energy * params.shockwave * 6,
      });
    }

    for (let i = state.rings.length - 1; i >= 0; i--) {
      const r = state.rings[i];
      r.r += r.speed;
      r.a -= 0.02;
      r.w *= 0.995;

      ctx.save();
      ctx.globalAlpha = r.a;
      ctx.lineWidth = r.w;

      if (glowOn) {
        ctx.globalCompositeOperation = "lighter";
        ctx.shadowBlur = 12;
        ctx.shadowColor = ctx.strokeStyle;
      }

      ctx.beginPath();
      ctx.arc(cx, cy, r.r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      if (r.a <= 0.02) state.rings.splice(i, 1);
    }
    // OLED-friendly scope: rotating clock-hand (avoids persistent horizontal line)
    __scopeAng += 0.016;
    __scopeDrift += 0.005;

    const baseLen = Math.min(w, h) * 0.14;
    const len = Math.min(Math.min(w, h) * 0.46, baseLen + energy * Math.min(w, h) * 0.35);

    const dcx = cx + Math.cos(__scopeDrift) * 10;
    const dcy = cy + Math.sin(__scopeDrift) * 10;

    ctx.save();
    if (glowOn) {
      ctx.globalCompositeOperation = "lighter";
      ctx.shadowBlur = 6;
      ctx.shadowColor = ctx.strokeStyle;
    }
    ctx.globalAlpha = 0.75;
    ctx.lineWidth = 1.2;

    ctx.translate(dcx, dcy);
    ctx.rotate(__scopeAng);

    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(len, 0);
    ctx.stroke();
    ctx.restore();
  },
};
