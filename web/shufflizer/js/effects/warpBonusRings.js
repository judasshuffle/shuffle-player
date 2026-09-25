// Bonus-stage flight: a dark perspective grid, molten sky and flying violet shards.
// Kept separate from the original tunnel and pyramid effects.
const TAU = Math.PI * 2;

function shard(ctx, x, y, size, angle, opacity) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.globalAlpha = opacity;
  ctx.shadowBlur = size * 0.65;
  ctx.shadowColor = "#b349ff";
  ctx.fillStyle = "#a836f2";
  ctx.beginPath();
  ctx.moveTo(0, -size);
  ctx.lineTo(-size * 0.8, size * 0.64);
  ctx.lineTo(size * 0.55, size * 0.30);
  ctx.closePath();
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.fillStyle = "#ec91ff";
  ctx.beginPath();
  ctx.moveTo(0, -size);
  ctx.lineTo(-size * 0.8, size * 0.64);
  ctx.lineTo(-size * 0.15, size * 0.1);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = "#5425a5";
  ctx.beginPath();
  ctx.moveTo(0, -size);
  ctx.lineTo(-size * 0.15, size * 0.1);
  ctx.lineTo(size * 0.55, size * 0.30);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

export const effect = {
  id: "warpBonusRings",
  name: "Bonus Flight",
  defaults: {},
  init() {},
  update() {},
  render({ ctx, w, h, dt, audio, state }) {
    const energy = Math.min(1, (audio.energy || 0) * 5);
    state.travel = (state.travel || 0) + Math.min(dt || 0.016, 0.05) * (0.28 + energy * 0.19);
    state.pulse = audio.beat ? 1 : (state.pulse || 0) * 0.90;
    const time = state.travel;
    const cx = w * (0.5 + Math.sin(time * 0.7) * 0.045);
    const cy = h * 0.48;

    // Clear each frame: this flight needs a black void, not phosphor trails.
    ctx.fillStyle = "#020208";
    ctx.fillRect(0, 0, w, h);

    // Molten bands skim the top of the scene like a planetary horizon.
    const sky = ctx.createLinearGradient(0, 0, 0, h * 0.34);
    sky.addColorStop(0, "#4b1617");
    sky.addColorStop(0.18, "#a73720");
    sky.addColorStop(0.48, "#de6324");
    sky.addColorStop(0.72, "#5e231f");
    sky.addColorStop(1, "rgba(2,2,8,0)");
    ctx.fillStyle = sky;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(w, 0);
    ctx.lineTo(w, h * 0.09);
    ctx.bezierCurveTo(w * 0.82, h * 0.42, w * 0.66, h * 0.15, cx, h * 0.20);
    ctx.bezierCurveTo(w * 0.28, h * 0.12, w * 0.18, h * 0.42, 0, h * 0.12);
    ctx.closePath();
    ctx.fill();

    for (let i = 0; i < 22; i++) {
      const band = i / 22;
      const sway = Math.sin(i * 1.7 + time * 3) * h * 0.025;
      const y = h * (0.025 + band * 0.23) + sway;
      ctx.strokeStyle = i % 3 === 0
        ? `rgba(255,215,125,${0.16 + energy * 0.16})`
        : `rgba(103,25,33,${0.30 + band * 0.20})`;
      ctx.lineWidth = 2 + (i % 4) * 2;
      ctx.beginPath();
      ctx.moveTo(-w * 0.05, y + h * 0.06);
      ctx.bezierCurveTo(w * 0.24, y - h * 0.18, w * 0.33, y + h * 0.07, cx, y - h * 0.035);
      ctx.bezierCurveTo(w * 0.7, y + h * 0.04, w * 0.8, y - h * 0.14, w * 1.05, y + h * 0.04);
      ctx.stroke();
    }

    // Thin lava currents bend past the flight corridor without filling the void.
    for (let bank = -1; bank <= 1; bank += 2) {
      for (let current = 0; current < 7; current++) {
        const offset = (current + 1) / 8;
        const bend = Math.sin(time * 1.5 + current * 0.8) * w * 0.055;
        ctx.strokeStyle = current % 3 === 0
          ? `rgba(255,166,78,${0.08 + energy * 0.07})`
          : "rgba(145,42,35,0.09)";
        ctx.lineWidth = 1 + current * 0.4;
        ctx.beginPath();
        ctx.moveTo(cx + bank * w * offset * 0.05, cy - h * 0.14);
        ctx.bezierCurveTo(cx + bank * w * offset * 0.25 + bend, h * 0.44,
          cx + bank * w * offset * 0.8 - bend, h * 0.7,
          cx + bank * w * offset * 1.35, h * 1.08);
        ctx.stroke();
      }
    }

    // Dotted lanes rush toward the camera from a single vanishing point.
    for (let lane = 0; lane < 16; lane++) {
      const angle = lane / 16 * TAU;
      const dx = Math.cos(angle);
      const dy = Math.sin(angle) * 0.70;
      for (let dot = 0; dot < 24; dot++) {
        const depth = (dot / 24 + time * 0.63) % 1;
        const distance = depth * depth * Math.max(w, h) * 0.79;
        const opacity = (0.06 + depth * 0.30) * (dy < 0 ? 0.55 : 1);
        ctx.fillStyle = lane % 3 === 0
          ? `rgba(108,224,255,${opacity})`
          : lane % 3 === 1
            ? `rgba(209,133,255,${opacity})`
            : `rgba(245,224,194,${opacity})`;
        const size = 0.6 + depth * 2.1;
        ctx.fillRect(cx + dx * distance, cy + dy * distance, size, size);
      }
    }

    // Fragmented hoops emerge from the distance, expand and pass the camera.
    for (let gate = 0; gate < 3; gate++) {
      const depth = (gate / 3 + time * 0.36) % 1;
      const radius = Math.min(w, h) * (0.012 + depth * depth * 0.46);
      const gateX = cx + Math.sin(time * 0.75 + depth * 3.7) * w * 0.10 * depth;
      const gateY = cy + Math.cos(time * 0.6 + depth * 2) * h * 0.045 * depth;
      const size = Math.min(w, h) * (0.004 + depth * 0.024) * (1 + state.pulse * 0.14);
      for (let piece = 0; piece < 8; piece++) {
        const angle = piece / 8 * TAU - Math.PI / 2;
        shard(ctx, gateX + Math.cos(angle) * radius, gateY + Math.sin(angle) * radius * 0.77,
          size, angle + Math.PI / 2 + Math.sin(time + gate) * 0.1, 0.20 + depth * 0.75);
      }
    }

    ctx.strokeStyle = `rgba(83,255,118,${0.35 + state.pulse * 0.42})`;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(cx - 10, cy); ctx.lineTo(cx - 3, cy);
    ctx.moveTo(cx + 3, cy); ctx.lineTo(cx + 10, cy);
    ctx.moveTo(cx, cy - 10); ctx.lineTo(cx, cy - 3);
    ctx.moveTo(cx, cy + 3); ctx.lineTo(cx, cy + 10);
    ctx.stroke();
  },
};
