function rmsTimeDomain(byteArr) {
  let sum = 0;
  for (let i = 0; i < byteArr.length; i++) {
    const v = (byteArr[i] - 128) / 128;
    sum += v * v;
  }
  return Math.sqrt(sum / byteArr.length);
}

// TITLE_PARTICLE_PLUMBING
let _spawnTitleParticleImpl = null;

export function setTitleParticleSpawner(fn) {
  _spawnTitleParticleImpl = fn;
}

export function spawnTitleParticle(text) {
  if (typeof _spawnTitleParticleImpl === "function") {
    _spawnTitleParticleImpl(text);
    return true;
  }
  console.warn("spawnTitleParticle: spawner not armed yet (initVisuals has not registered it)");
  return false;
}


export function initVisuals(canvas, analyser, uiState) {
  const ctx = canvas.getContext("2d", { alpha: false });

  function resize() {
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = Math.floor(window.innerWidth * dpr);
    canvas.height = Math.floor(window.innerHeight * dpr);
    canvas.style.width = window.innerWidth + "px";
    canvas.style.height = window.innerHeight + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener("resize", resize);

  const freq = new Uint8Array(analyser.frequencyBinCount);
  const wave = new Uint8Array(analyser.fftSize);

  let angle = 0;
  let shapes = [];
  let texts = [];


// TITLE_PARTICLE_IMPL
  setTitleParticleSpawner((text) => {
    if (!text) return;
    const t = String(text).trim();
    if (!t) return;

    texts.push({
      text: t.length > 44 ? t.slice(0, 41) + "…" : t,
      angle: Math.random() * Math.PI * 2,
      radius: 30 + Math.random() * 40,
      spin: (Math.random() - 0.5) * 0.08,
      life: 1.0,
      drift: 0.6 + Math.random() * 1.2,
      size: 18 + Math.random() * 10,
    });

    if (texts.length > 12) texts.splice(0, texts.length - 12);
  });

  let rings = [];

  let energyAvg = 0;
  let beatCooldown = 0;

  function spawnShape(energy) {
    shapes.push({
      angle: Math.random() * Math.PI * 2,
      radius: 100 + Math.random() * 200,
      spin: (Math.random() - 0.5) * 0.1,
      life: 1,
      bornEnergy: energy,
    });
  }

  function spawnRing(strength) {
    rings.push({
      r: 60,
      speed: 6 + strength * 18,
      a: 0.9,
      w: 2 + strength * 6,
    });
  }

  function drawRing(cx, cy, ring, glowOn) {
    ctx.save();
    ctx.globalAlpha = ring.a;
    ctx.lineWidth = ring.w;

    if (glowOn) {
      ctx.globalCompositeOperation = "lighter";
      ctx.shadowBlur = 12;
      ctx.shadowColor = ctx.strokeStyle;
    }

    ctx.beginPath();
    ctx.arc(cx, cy, ring.r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  function frame() {
    requestAnimationFrame(frame);

    analyser.getByteFrequencyData(freq);
    analyser.getByteTimeDomainData(wave);

    const energy = rmsTimeDomain(wave);

    const spinAmt = uiState.spin;
    const trailAmt = uiState.phosphor ? uiState.trail : 1.0;
    const zapAmt = uiState.zap;
    const spawnRate = uiState.spawn;
    const shockwaveAmt = uiState.shockwave;
    const glowOn = uiState.glow;
    const beatThresh = uiState.beatThresh;

    ctx.fillStyle = `rgba(0,0,0,${trailAmt})`;
    ctx.fillRect(0, 0, window.innerWidth, window.innerHeight);

    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;

    energyAvg = energyAvg * 0.96 + energy * 0.04;

    const isBeat = (energy > energyAvg * beatThresh) && beatCooldown <= 0;

    if (isBeat) {
      for (let i = 0; i < spawnRate; i++) spawnShape(energy);
      if (shockwaveAmt > 0.01) spawnRing(energy * shockwaveAmt);
      beatCooldown = 14;
    }
    beatCooldown--;

    angle += spinAmt * 0.01 + energy * 0.1;

    ctx.strokeStyle = `hsl(${energy * 800},100%,50%)`;
    ctx.lineWidth = 2 + energy * 5;

    if (glowOn) {
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.shadowBlur = 10;
      ctx.shadowColor = ctx.strokeStyle;
    }

    const segments = 16;
    const baseRadius = 200 + energy * 100 * zapAmt;
    ctx.beginPath();
    for (let i = 0; i <= segments; i++) {
      const a = angle + (i / segments) * Math.PI * 2;
      const x = cx + Math.cos(a) * baseRadius;
      const y = cy + Math.sin(a) * baseRadius;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    if (glowOn) ctx.restore();

    for (let i = shapes.length - 1; i >= 0; i--) {
      const s = shapes[i];
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

      if (s.life <= 0) shapes.splice(i, 1);
    }


    // TEXT_PARTICLES_LOOP
    for (let i = texts.length - 1; i >= 0; i--) {
      const t = texts[i];
      t.angle += t.spin + energy * 0.06;
      t.radius += (energy * 8 + 1.2) * t.drift;
      t.life -= 0.008;

      const x = cx + Math.cos(t.angle) * t.radius;
      const y = cy + Math.sin(t.angle) * t.radius;

      ctx.save();
      ctx.globalAlpha = Math.max(0, t.life);

      if (glowOn) {
        ctx.globalCompositeOperation = "lighter";
        ctx.shadowBlur = 10;
        ctx.shadowColor = ctx.strokeStyle;
      }

      ctx.font = `${Math.floor(t.size)}px system-ui, -apple-system, Segoe UI, Roboto, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      ctx.lineWidth = 3;
      ctx.strokeText(t.text, x, y);
      ctx.fillStyle = ctx.strokeStyle;
      ctx.fillText(t.text, x, y);

      ctx.restore();

      if (t.life <= 0) texts.splice(i, 1);
    }

    for (let i = rings.length - 1; i >= 0; i--) {
      const r = rings[i];
      r.r += r.speed;
      r.a -= 0.02;
      r.w *= 0.995;

      drawRing(cx, cy, r, glowOn);

      if (r.a <= 0.02) rings.splice(i, 1);
    }

    ctx.save();
    if (glowOn) {
      ctx.globalCompositeOperation = "lighter";
      ctx.shadowBlur = 6;
      ctx.shadowColor = ctx.strokeStyle;
    }
    ctx.beginPath();
    for (let i = 0; i < wave.length; i++) {
      const x = (i / wave.length) * window.innerWidth;
      const y = cy + (wave[i] - 128);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
  }

  requestAnimationFrame(frame);
}
