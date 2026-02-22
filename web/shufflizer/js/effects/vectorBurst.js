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

﻿function rand(min, max) { return min + Math.random() * (max - min); }

export const effect = {
  id: "vectorBurst",
  name: "Vector Burst",
  defaults: {},
  init() {},
  update() {},
  render({ ctx, w, h, dt, audio, params, globals, state }) {
    const { energy } = audio;
    const cx = w / 2, cy = h / 2;

    const trailAmt = globals.phosphor ? params.trail : 1.0;
    ctx.fillStyle = `rgba(0,0,0,${trailAmt})`;
    ctx.fillRect(0, 0, w, h);

    // rainbow energy, tinted toward palette
    const _tint = (typeof window !== "undefined" && typeof (window.SHUF && typeof window.SHUF.tint==='number') ? window.SHUF.tint : window.SHUF_TINT === "number") ? (window.SHUF && typeof window.SHUF.tint==='number') ? window.SHUF.tint : window.SHUF_TINT : 0.65;
    const _h = (energy * 1000) % 360;
    const _rain = _shuf_hslToRgb(_h, 1.0, 55);
    const _pal = _shuf_parseRGB((energy > 0.55 ? ((window.SHUF && window.SHUF.accent) ? window.SHUF.accent : window.SHUF_ACCENT || (window.SHUF && window.SHUF.primary) ? window.SHUF.primary : window.SHUF_PRIMARY) : ((window.SHUF && window.SHUF.primary) ? window.SHUF.primary : window.SHUF_PRIMARY || "rgba(0,255,102,1)")));
    const _mix = _shuf_mixRGB(_rain, _pal, _tint);
    ctx.strokeStyle = _shuf_rgba(_mix, 1.0);ctx.lineWidth = 1.2 + energy * 4;

    const glowOn = globals.glow;
    if (glowOn) {
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.shadowBlur = 10;
      ctx.shadowColor = ctx.strokeStyle;
    }

    if (!state.particles) state.particles = [];

    // --- ORBITING EMITTER (slow revolve + beat kick) ---
    state.theta ??= 0;
    state.orbit ??= 120;

    const baseSpeed = 0.35;                 // radians/sec feel
    const beatKick = audio.beat ? 1.2 : 0;  // extra spin on beats
    const dtheta = (baseSpeed + beatKick) * (dt || 0.016);
    state.theta += dtheta;

    // orbit radius breathes with energy (smoothed)
    const targetOrbit = 80 + energy * 260;
    state.orbit = state.orbit * 0.92 + targetOrbit * 0.08;

    const ex = cx + Math.cos(state.theta) * state.orbit;
    const ey = cy + Math.sin(state.theta) * state.orbit;
    // ---------------------------------------------------

    // Emit on beat + small continuous emit
    const emit = audio.beat ? (params.spawn | 0) + 6 : 1;
    for (let i = 0; i < emit; i++) {
      const a = rand(0, Math.PI * 2);
      const sp = rand(2, 8) + energy * 20 * params.zap;
      state.particles.push({
        x: ex,
        y: ey,
        vx: Math.cos(a) * sp,
        vy: Math.sin(a) * sp,
        life: rand(0.6, 1.2),
        rot: rand(0, Math.PI * 2),
        spin: rand(-0.12, 0.12),
        len: rand(10, 40) + energy * 120,
      });
    }

    // Integrate + draw
    for (let i = state.particles.length - 1; i >= 0; i--) {
      const p = state.particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.rot += p.spin;
      p.vx *= 0.985;
      p.vy *= 0.985;
      p.life -= 0.02;

      ctx.save();
      ctx.globalAlpha = Math.max(0, p.life);
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.beginPath();
      ctx.moveTo(-p.len, 0);
      ctx.lineTo(p.len, 0);
      ctx.moveTo(0, -p.len * 0.35);
      ctx.lineTo(0, p.len * 0.35);
      ctx.stroke();
      ctx.restore();

      if (p.life <= 0 || p.x < -200 || p.x > w + 200 || p.y < -200 || p.y > h + 200) {
        state.particles.splice(i, 1);
      }
    }

    if (glowOn) ctx.restore();
  },
};
