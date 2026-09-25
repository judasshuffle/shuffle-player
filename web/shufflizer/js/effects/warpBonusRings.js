// A forward flight through luminous gates, inspired by Tempest 2000's warp bonus rounds.
// This effect is separate so the existing Tempest and pyramid presets stay as they are.
const TAU = Math.PI * 2;

export const effect = {
  id: "warpBonusRings",
  name: "Warp Bonus Rings",
  defaults: {},
  init() {},
  update() {},
  render({ ctx, w, h, dt, audio, params, globals, state }) {
    const energy = Math.min(1, (audio.energy || 0) * 6);
    const bassBins = Math.min(24, audio.freq?.length || 0);
    let bassSum = 0;
    for (let i = 0; i < bassBins; i++) bassSum += audio.freq[i];
    const bass = bassBins ? bassSum / (bassBins * 255) : 0;
    state.travel = (state.travel || 0) + Math.min(dt || 0.016, 0.05) * (0.26 + energy * 0.18);
    state.flash = audio.beat ? 1 : (state.flash || 0) * 0.91;

    ctx.fillStyle = `rgba(2,3,13,${globals.phosphor ? Math.max(0.10, params.trail) : 1})`;
    ctx.fillRect(0, 0, w, h);

    const cx = w * 0.5 + Math.sin(state.travel * 0.8) * w * 0.035;
    const cy = h * 0.49 + Math.cos(state.travel * 0.6) * h * 0.035;
    const size = Math.min(w, h);

    // Sweeping bands evoke the horizon beneath the bonus stage's flying rings.
    for (let i = 0; i < 13; i++) {
      const depth = (i / 13 + state.travel * 0.20) % 1;
      const y = cy + Math.pow(depth, 1.7) * h * 0.56;
      ctx.strokeStyle = `rgba(255,${Math.round(66 + depth * 100)},${Math.round(120 + depth * 80)},${0.08 + depth * 0.26})`;
      ctx.lineWidth = 1 + depth * 3;
      ctx.beginPath();
      ctx.moveTo(0, y + Math.sin(i + state.travel * 2) * depth * 10);
      ctx.quadraticCurveTo(cx, y - 16 * depth, w, y + Math.cos(i + state.travel * 2) * depth * 10);
      ctx.stroke();
    }

    // Draw far gates first. Perspective makes them approach and pass the viewer.
    for (let i = 0; i < 11; i++) {
      const depth = (i / 11 + state.travel) % 1;
      const perspective = Math.pow(depth, 2.2);
      const radius = size * (0.035 + perspective * 0.76) * (1 + bass * 0.15);
      const x = cx + Math.sin(i * 0.61 + state.travel * 1.3) * w * 0.065 * depth;
      const y = cy + Math.cos(i * 0.47 + state.travel) * h * 0.042 * depth;
      const hue = (192 + i * 32 + Math.floor(state.travel * 60)) % 360;
      const alpha = 0.22 + depth * 0.66;

      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(Math.sin(state.travel * 0.75 + i * 0.3) * 0.12);
      ctx.strokeStyle = `hsla(${hue},100%,${62 + energy * 18}%,${alpha})`;
      ctx.lineWidth = 1.5 + depth * 5 + state.flash * depth * 2;
      if (globals.glow) {
        ctx.shadowColor = ctx.strokeStyle;
        ctx.shadowBlur = 8 + depth * 16;
      }
      ctx.beginPath();
      ctx.ellipse(0, 0, radius, radius * 0.76, 0, 0, TAU);
      ctx.stroke();

      // Short tick marks give each gate a legible arcade wireframe silhouette.
      for (let tick = 0; tick < 12; tick++) {
        const a = tick / 12 * TAU;
        ctx.beginPath();
        ctx.moveTo(Math.cos(a) * radius, Math.sin(a) * radius * 0.76);
        ctx.lineTo(Math.cos(a) * radius * 1.08, Math.sin(a) * radius * 0.82);
        ctx.stroke();
      }
      ctx.restore();
    }
  },
};
