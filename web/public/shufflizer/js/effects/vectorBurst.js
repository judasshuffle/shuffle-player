function rand(min, max) { return min + Math.random() * (max - min); }

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

    ctx.strokeStyle = `hsl(${energy * 1000},100%,55%)`;
    ctx.lineWidth = 1.2 + energy * 4;

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
