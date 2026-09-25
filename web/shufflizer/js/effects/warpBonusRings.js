// Bonus-stage flight: a dark perspective grid, molten sky and flying violet shards.
// Kept separate from the original tunnel and pyramid effects.
const TAU = Math.PI * 2;

function makeLavaTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 256;
  const g = canvas.getContext("2d");
  const base = g.createLinearGradient(0, 0, 0, canvas.height);
  base.addColorStop(0, "#43151d");
  base.addColorStop(0.45, "#a33826");
  base.addColorStop(0.78, "#d67731");
  base.addColorStop(1, "#54212a");
  g.fillStyle = base;
  g.fillRect(0, 0, canvas.width, canvas.height);

  // Deterministic streaks give the reusable texture a mottled, flowing surface.
  let seed = 1729;
  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  const colors = ["rgba(255,216,129,.55)", "rgba(255,155,58,.42)",
    "rgba(68,16,28,.46)", "rgba(120,26,35,.52)"];
  for (let i = 0; i < 180; i++) {
    const x = random() * canvas.width;
    const y = random() * canvas.height;
    const length = 35 + random() * 240;
    g.strokeStyle = colors[i % colors.length];
    g.lineWidth = 0.7 + random() * 3.5;
    g.beginPath();
    g.moveTo(x, y);
    g.bezierCurveTo(x + length * 0.28, y - 15 + random() * 30,
      x + length * 0.75, y + 14 - random() * 28, x + length, y);
    g.stroke();
  }
  return canvas;
}

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

    // Move one small texture over a narrowing, bending ceiling in perspective.
    // The texture is generated once, then reused; no per-frame pixel processing.
    if (!state.lavaTexture) state.lavaTexture = makeLavaTexture();
    const texture = state.lavaTexture;
    const bands = 40;
    for (let i = 0; i < bands; i++) {
      const z = i / bands;
      const next = (i + 1) / bands;
      const y = h * (0.34 * Math.pow(z, 1.15));
      const yNext = h * (0.34 * Math.pow(next, 1.15));
      const ripple = 1 + Math.sin(time * 3.2 + z * 12) * 0.09 * (0.25 + z);
      const width = w * (1 - 0.91 * Math.pow(z, 1.4)) * ripple;
      const bend = Math.sin(time * 1.1 + z * 3.1) * w * 0.08 * z;
      const x = cx + bend - width / 2;
      const sourceY = Math.floor((time * 58 + z * 205) % (texture.height - 5));
      ctx.drawImage(texture, 0, sourceY, texture.width, 5,
        x, y, width, yNext - y + 1.2);
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
