import { getEffectById } from "./effects/index.js";

function rmsTimeDomain(byteArr) {
  let sum = 0;
  for (let i = 0; i < byteArr.length; i++) {
    const v = (byteArr[i] - 128) / 128;
    sum += v * v;
  }
  return Math.sqrt(sum / byteArr.length);
}


// --- Global overlays (hub ring / outer ring / spoke), concentric + independent rotation ---
let __ovHubAng = 0;
let __ovBigAng = 0;
let __ovSpokeAng = 0;

function __clamp(x, a, b){ return Math.max(a, Math.min(b, x)); }

function __smoothSample(wave, i, win=4){
  // simple moving average (smooth hub)
  let sum = 0, n = 0;
  for (let k = -win; k <= win; k++){
    const j = (i + k + wave.length) % wave.length;
    sum += wave[j];
    n++;
  }
  return sum / n;
}

function drawOverlays(ctx, w, h, t, audio, ui){
  if (!audio || !audio.wave || !ui) return;

  const cx = w / 2, cy = h / 2;
  const wave = audio.wave;

  const energy = audio.energy ?? 0;
  // Throb based on energy (kept stable)
  const throb = __clamp(energy * (ui.ovThrob ?? 0), 0, 1.25);

  // independent angles
  __ovHubAng   += (ui.ovHubRot   ?? 0) * 0.0025;
  __ovBigAng   += (ui.ovBigRot   ?? 0) * 0.0025;
  __ovSpokeAng += (ui.ovSpokeRot ?? 0) * 0.0025;

  // HUB WAVE RING (smooth)
  if (ui.ovHub){
    const baseR = (ui.ovHubR ?? 90) + throb * 18;
    const ampR  = (ui.ovHubAmp ?? 20) * (0.35 + 0.65 * throb);
    const step  = 6;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(__ovHubAng);

    ctx.globalAlpha = 0.85;
    ctx.lineWidth = 2.6;
    ctx.strokeStyle = ((window.SHUF && window.SHUF.primary) ? window.SHUF.primary : window.SHUF_PRIMARY || ((window.SHUF && window.SHUF.primary) ? window.SHUF.primary : window.SHUF_PRIMARY || "rgba(0,255,102,0.95)"));

    ctx.beginPath();
    for (let i = 0; i < wave.length; i += step){
      const a = (i / wave.length) * Math.PI * 2;
      const v = (__smoothSample(wave, i, 5) - 128) / 128;
      const r = baseR + v * ampR;
      const x = Math.cos(a) * r;
      const y = Math.sin(a) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
  }

  // OUTER WAVE RING (thicker / more aggressive)
  if (ui.ovBig){
    const baseR = (ui.ovBigR ?? 320) + throb * 34;
    const ampR  = (ui.ovBigAmp ?? 80) * (0.55 + 0.75 * throb);
    const step  = 3;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(__ovBigAng);

    ctx.globalAlpha = 0.75;
    ctx.lineWidth = 3.8;
    ctx.strokeStyle = ((window.SHUF && window.SHUF.primary) ? window.SHUF.primary : window.SHUF_PRIMARY || "rgba(0,255,102,0.80)");

    ctx.beginPath();
    for (let i = 0; i < wave.length; i += step){
      const a = (i / wave.length) * Math.PI * 2;
      const v = (wave[i] - 128) / 128;
      const r = baseR + v * ampR;
      const x = Math.cos(a) * r;
      const y = Math.sin(a) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    // IMPORTANT: do NOT closePath (prevents “wedge/chomp” chord)
    ctx.stroke();
    ctx.restore();
  }

  // SPOKE WAVE (diameter waveform)
  if (ui.ovSpoke){
    const spokeLen = (ui.ovSpokeLen ?? 900);
    const amp = (ui.ovSpokeAmp ?? 35) * (0.35 + 0.8 * throb);
    const step = 2;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(__ovSpokeAng);

    ctx.globalAlpha = 0.85;
    ctx.lineWidth = 2.0;
    ctx.strokeStyle = ((window.SHUF && window.SHUF.primary) ? window.SHUF.primary : window.SHUF_PRIMARY || "rgba(0,255,102,0.95)");

    ctx.beginPath();
    for (let i = 0; i < wave.length; i += step){
      const x = (i / (wave.length - 1)) * (spokeLen * 2) - spokeLen;
      const y = ((wave[i] - 128) / 128) * amp;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
  }
}


function drawNowPlaying(ctx, w, h, title, glowOn) {
  if (!title) return;

  ctx.save();
  ctx.globalAlpha = 0.75;
  ctx.lineWidth = 2;

  // Subtle phosphor-ish look
  if (glowOn) {
    ctx.globalCompositeOperation = "lighter";
    ctx.shadowBlur = 10;
    ctx.shadowColor = ((window.SHUF && window.SHUF.accent) ? window.SHUF.accent : window.SHUF_ACCENT || "#ffffff");
  }

  ctx.font = "14px system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
  ctx.textBaseline = "bottom";

  const pad = 12;
  const x = pad;
  const y = h - pad;

  // Outline + fill effect using current strokeStyle-ish
  ctx.strokeStyle = ((window.SHUF && window.SHUF.primary) ? window.SHUF.primary : window.SHUF_PRIMARY || "rgba(0,255,102,0.9)");
  ctx.fillStyle = ((window.SHUF && window.SHUF.glowFill) ? window.SHUF.glowFill : window.SHUF_GLOW_FILL || "rgba(0,255,102,0.25)");
  ctx.strokeText(title, x, y);
  ctx.fillText(title, x, y);

  ctx.restore();
}

export function startEngine(canvas, analyser, uiState) {
  const ctx = canvas.getContext("2d", { alpha: false });

  let w = window.innerWidth;
  let h = window.innerHeight;

  function resize() {
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    w = window.innerWidth;
    h = window.innerHeight;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener("resize", resize);

  const freq = new Uint8Array(analyser.frequencyBinCount);
  const wave = new Uint8Array(analyser.fftSize);


  // TITLE_PARTICLES_ENGINE
  const titleParticles = [];
  let _lastTitle = "";
  let _nextTitlePing = 0;
  let _titleDebugUntil = 0;

  function spawnTitleParticle(text) {
    const t = (text || "").toString().trim();
    if (!t) return;

    titleParticles.push({
      text: t.length > 44 ? t.slice(0, 41) + "…" : t,
      angle: Math.random() * Math.PI * 2,
      radius: 40 + Math.random() * 80,
      spin: 0.02 + Math.random() * 0.03,
      life: 1.0,
      drift: 0.8 + Math.random() * 1.4,
      vr: (Math.random() - 0.5) * 1.8,
      va: 0.010 + Math.random() * 0.018,
      size: 32 + Math.random() * 20,
    });

    if (titleParticles.length > 10) titleParticles.splice(0, titleParticles.length - 10);
  }

  function drawTitleParticles(ctx, w, h, energy, glowOn) {
    if (!titleParticles.length) return;
    const cx = w / 2, cy = h / 2;

    ctx.save();
    for (let i = titleParticles.length - 1; i >= 0; i--) {
      const p = titleParticles[i];
      p.angle += (p.va ?? 0.02) + energy * 0.010;
      p.vr = (p.vr ?? 0) + (energy * 0.10 - 0.02);   // audio pushes out a bit
      p.vr += (Math.random() - 0.5) * 0.12;           // gentle wander
      p.radius += p.vr;

      // soft spring toward a target orbit (keeps it floaty, not pinned)
      const target = 420;
      p.vr += (target - p.radius) * 0.00035;

      // damping
      p.vr *= 0.99;
      
      p.life -= 0.0008;

      const x = cx + Math.cos(p.angle) * p.radius;
      const y = cy + Math.sin(p.angle) * p.radius;

      ctx.save();
      ctx.globalAlpha = Math.max(0, p.life);

      if (glowOn) {
        ctx.globalCompositeOperation = "lighter";
        ctx.shadowBlur = 10;
        ctx.shadowColor = ((window.SHUF && window.SHUF.primary) ? window.SHUF.primary : window.SHUF_PRIMARY || "rgba(0,255,102,0.95)");
      }

      ctx.font = `${Math.floor(p.size)}px system-ui, -apple-system, Segoe UI, Roboto, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      // neon-ish
      ctx.strokeStyle = ((window.SHUF && window.SHUF.primary) ? window.SHUF.primary : window.SHUF_PRIMARY || "rgba(0,255,102,0.95)");
      ctx.fillStyle = ctx.strokeStyle;
      ctx.lineWidth = 5;

      ctx.translate(x, y);
      ctx.rotate(p.angle); // rotate like the pentagon vibe
      ctx.strokeText(p.text, 0, 0);
      ctx.fillText(p.text, 0, 0);

      ctx.restore();

      if (p.life <= 0) titleParticles.splice(i, 1);
    }
    ctx.restore();
  }

  let energyAvg = 0;
  let beatCooldown = 0;

  let currentEffectId = null;
  let effectState = {};

  let lastT = 0;
  const maxFps = 60;            // set 45 if you want smoother under VNC
  const minDt = 1000 / maxFps;

  function frame(t) {
    requestAnimationFrame(frame);
    if (t - lastT < minDt) return;
    const dt = (t - lastT) / 1000;
    lastT = t;

    analyser.getByteFrequencyData(freq);
    analyser.getByteTimeDomainData(wave);

    const energy = rmsTimeDomain(wave);
    energyAvg = energyAvg * 0.96 + energy * 0.04;

    const beatThresh = uiState.beatThresh;
    const beat = (energy > energyAvg * beatThresh) && beatCooldown <= 0;
    if (beat) beatCooldown = 14;
    beatCooldown--;

    if (uiState.effectId && uiState.effectId !== currentEffectId) {
      currentEffectId = uiState.effectId;
      effectState = {};
      const fx = getEffectById(currentEffectId);
      try { fx.init?.({ ctx, w, h }); } catch {}
    }

    const fx = getEffectById(uiState.effectId || "tempestTunnel");

    const audio = { energy, energyAvg, beat, freq, wave };

    const globals = {
      glow: !!uiState.glow,
      phosphor: !!uiState.phosphor,
      trackTitle: uiState.trackTitle || "",
    };

    const params = uiState;

    fx.render({ ctx, w, h, t, dt, audio, globals, params, state: effectState });


    // TITLE_PARTICLES_ENGINE: spawn on title change
    if (params.titleParticles !== false && globals.trackTitle && globals.trackTitle !== _lastTitle) {
      _lastTitle = globals.trackTitle;
      _nextTitlePing = t + 60000; // 60s
      spawnTitleParticle(globals.trackTitle);
      _titleDebugUntil = t + 2000;
    }

    // TITLE_PARTICLES_ENGINE: draw on top
    if (params.titleParticles !== false) drawTitleParticles(ctx, w, h, energy, globals.glow);

    // TITLE_PARTICLES_ENGINE: periodic ping
    if (params.titleParticles !== false && globals.trackTitle && t >= _nextTitlePing) {
      _nextTitlePing = t + 60000; // 60s
      for (let i = 0; i < 3; i++) {
        spawnTitleParticle(globals.trackTitle);
      }
    }

    // TITLE_PARTICLES_DEBUG_FLASH
    if (t < _titleDebugUntil) {
      ctx.save();
      ctx.globalAlpha = 0.9;
      ctx.font = "22px system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.strokeStyle = ((window.SHUF && window.SHUF.primary) ? window.SHUF.primary : window.SHUF_PRIMARY || "rgba(0,255,102,0.95)");
      ctx.fillStyle = ctx.strokeStyle;
      ctx.lineWidth = 3;
      ctx.strokeText("TRACKTITLE CHANGED", w/2, h/2);
      ctx.fillText("TRACKTITLE CHANGED", w/2, h/2);
      ctx.restore();
    }

    // Overlay: now playing (disabled; title uses particles)

    // Global overlays
    drawOverlays(ctx, w, h, t, audio, uiState);
  }

  requestAnimationFrame((t) => {
    lastT = t;
    requestAnimationFrame(frame);
  });
}
