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
    ctx.strokeStyle = "rgba(0,255,102,0.95)";

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
    ctx.strokeStyle = "rgba(0,255,102,0.80)";

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
    ctx.strokeStyle = "rgba(0,255,102,0.95)";

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
    ctx.shadowColor = "#ffffff";
  }

  ctx.font = "14px system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
  ctx.textBaseline = "bottom";

  const pad = 12;
  const x = pad;
  const y = h - pad;

  // Outline + fill effect using current strokeStyle-ish
  ctx.strokeStyle = "rgba(0,255,102,0.9)";
  ctx.fillStyle = "rgba(0,255,102,0.25)";
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

    // Overlay: now playing
    drawNowPlaying(ctx, w, h, globals.trackTitle, globals.glow);

    // Global overlays
    drawOverlays(ctx, w, h, t, audio, uiState);
  }

  requestAnimationFrame((t) => {
    lastT = t;
    requestAnimationFrame(frame);
  });
}
