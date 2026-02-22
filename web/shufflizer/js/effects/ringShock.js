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
  id: "ringShock",
  name: "Ring Shock",
  defaults: {},
  init() {},
  update() {},
  render({ ctx, w, h, audio, params, globals, state }) {
    const { energy, wave } = audio;
    const cx = w / 2, cy = h / 2;

    const trailAmt = globals.phosphor ? params.trail : 1.0;
    ctx.fillStyle = `rgba(0,0,0,${trailAmt})`;
    ctx.fillRect(0, 0, w, h);

    // rainbow energy, tinted toward palette
    const _tint = (typeof window !== "undefined" && typeof window.SHUF_TINT === "number") ? window.SHUF_TINT : 0.65;
    const _h = (energy * 900) % 360;
    const _rain = _shuf_hslToRgb(_h, 1.0, 55);
    const _pal = _shuf_parseRGB((energy > 0.55 ? (window.SHUF_ACCENT || window.SHUF_PRIMARY) : (window.SHUF_PRIMARY || "rgba(0,255,102,1)")));
    const _mix = _shuf_mixRGB(_rain, _pal, _tint);
    ctx.strokeStyle = _shuf_rgba(_mix, 1.0);ctx.lineWidth = 1.5 + energy * 4;

    const glowOn = globals.glow;
    if (glowOn) {
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.shadowBlur = 14;
      ctx.shadowColor = ctx.strokeStyle;
    }

    if (!state.rings) state.rings = [];

    if (audio.beat) {
      const strength = Math.min(2.0, energy * (params.shockwave + 0.25));
      const count = Math.max(1, (params.spawn | 0) || 2);
      for (let i = 0; i < count; i++) {
        state.rings.push({
          r: 40 + i * 18,
          speed: 8 + strength * 20,
          a: 0.95,
          w: 1.5 + strength * 4,
        });
      }
    }

    for (let i = state.rings.length - 1; i >= 0; i--) {
      const r = state.rings[i];
      r.r += r.speed;
      r.a -= 0.02;
      r.w *= 0.997;

      ctx.save();
      ctx.globalAlpha = r.a;
      ctx.lineWidth = r.w;

      ctx.beginPath();
      ctx.arc(cx, cy, r.r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      if (r.a <= 0.02) state.rings.splice(i, 1);
    }

    if (glowOn) ctx.restore();
    // OLED-friendly scope: rotating clock-hand (avoids persistent horizontal line)
    __scopeAng += 0.018;      // rotation speed
    __scopeDrift += 0.006;    // slow drift

    // energy-driven length (but capped)
    const baseLen = Math.min(w, h) * 0.14;
    const len = Math.min(Math.min(w, h) * 0.42, baseLen + energy * Math.min(w, h) * 0.35);

    // drift the center a bit so no pixel is always hit
    const dcx = cx + Math.cos(__scopeDrift) * 10;
    const dcy = cy + Math.sin(__scopeDrift) * 10;

    ctx.save();
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
