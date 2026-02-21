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

    ctx.strokeStyle = `hsl(${energy * 900},100%,55%)`;
    ctx.lineWidth = 1.5 + energy * 4;

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
