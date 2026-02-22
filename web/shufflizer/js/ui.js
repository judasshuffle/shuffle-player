import { listBanks, listPresets, getPreset } from "./presets.js";

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

function randn() {
  // quick-ish gaussian-ish
  return (Math.random() + Math.random() + Math.random() + Math.random() - 2);
}

function nudgeRange(el, intensity = 0.35) {
  const min = parseFloat(el.min);
  const max = parseFloat(el.max);
  const step = parseFloat(el.step || "1");
  const cur = parseFloat(el.value);

  // how many steps to move (scaled by intensity and range)
  const rangeSteps = Math.max(1, Math.round((max - min) / step));
  const deltaSteps = Math.round(randn() * rangeSteps * 0.08 * intensity);

  const next = clamp(cur + deltaSteps * step, min, max);
  el.value = String(next);
}

export function initUI() {
  const els = {
    bank: document.getElementById("bank"),
    preset: document.getElementById("preset"),

    muted: document.getElementById("muted"),
    glow: document.getElementById("glow"),
    phosphor: document.getElementById("phosphor"),

    titleParticles: document.getElementById("titleParticles"),

    spin: document.getElementById("spin"),
    trail: document.getElementById("trail"),
    zap: document.getElementById("zap"),
    spawn: document.getElementById("spawn"),
    shockwave: document.getElementById("shockwave"),
    beatThresh: document.getElementById("beatThresh"),
  };

  const state = {
  // Overlay defaults
  ovHub: true,
  ovBig: true,
  ovSpoke: true,
  ovThrob: 0.75,
  ovHubR: 90,
  ovHubAmp: 22,
  ovHubRot: 0.35,
  ovBigR: 320,
  ovBigAmp: 85,
  ovBigRot: -0.18,
  ovSpokeLen: 900,
  ovSpokeAmp: 35,
  ovSpokeRot: 0.55,

    // globals
    muted: true,
    glow: false,
    phosphor: true,

    // effect selection (from preset)
    effectId: "tempestTunnel",

    // params
    spin: 1.5,
    trail: 0.08,
    zap: 1.0,
    spawn: 2,
    shockwave: 1.0,
    beatThresh: 1.25,

    // selection
    bank: "Default",
    preset: "Tempest MVP",
  };

  function readFromControls() {
    state.muted = !!els.muted.checked;
    state.glow = !!els.glow.checked;
    state.phosphor = !!els.phosphor.checked;
    if (els.titleParticles) state.titleParticles = !!els.titleParticles.checked;

    state.spin = parseFloat(els.spin.value);
    state.trail = parseFloat(els.trail.value);
    state.zap = parseFloat(els.zap.value);
    state.spawn = parseInt(els.spawn.value, 10);
    state.shockwave = parseFloat(els.shockwave.value);
    state.beatThresh = parseFloat(els.beatThresh.value);

    state.bank = els.bank.value;
    state.preset = els.preset.value;
  }

  function writeToControls(presetObj) {
    if (!presetObj) return;

    state.effectId = presetObj.effectId || "tempestTunnel";

    const params = presetObj.params || {};
    els.spin.value = String(params.spin ?? els.spin.value);
    els.trail.value = String(params.trail ?? els.trail.value);
    els.zap.value = String(params.zap ?? els.zap.value);
    els.spawn.value = String(params.spawn ?? els.spawn.value);
    els.shockwave.value = String(params.shockwave ?? els.shockwave.value);
    els.beatThresh.value = String(params.beatThresh ?? els.beatThresh.value);

    els.glow.checked = !!params.glow;
    els.phosphor.checked = !!params.phosphor;

    readFromControls();
  }

  function repopulateBankSelect() {
    const banks = listBanks();
    els.bank.innerHTML = banks.map(b => `<option value="${b}">${b}</option>`).join("");
    if (!banks.includes(state.bank)) state.bank = banks[0] ?? "Default";
    els.bank.value = state.bank;
  }

  function repopulatePresetSelect(bankName) {
    const presets = listPresets(bankName);
    els.preset.innerHTML = presets.map(p => `<option value="${p}">${p}</option>`).join("");
    if (!presets.includes(state.preset)) state.preset = presets[0] ?? "";
    els.preset.value = state.preset;
  }

  function applySelectedPreset() {
    const p = getPreset(els.bank.value, els.preset.value);
    if (!p) return;
    writeToControls(p);
  }

  function setSelection(bankName, presetName) {
    if (bankName && els.bank.value !== bankName) {
      els.bank.value = bankName;
      state.bank = bankName;
      repopulatePresetSelect(bankName);
    }
    if (presetName) {
      els.preset.value = presetName;
      state.preset = presetName;
    }
    applySelectedPreset();
  }

  function nextPreset(dir = +1) {
    const opts = Array.from(els.preset.options).map(o => o.value);
    if (!opts.length) return;
    const cur = els.preset.value;
    const idx = Math.max(0, opts.indexOf(cur));
    const nextIdx = (idx + dir + opts.length) % opts.length;
    setSelection(els.bank.value, opts[nextIdx]);
  }

  function randomPreset() {
    const banks = Array.from(els.bank.options).map(o => o.value);
    if (!banks.length) return;
    const b = banks[Math.floor(Math.random() * banks.length)];
    const presets = listPresets(b);
    if (!presets.length) return;
    const p = presets[Math.floor(Math.random() * presets.length)];
    setSelection(b, p);
  }

  function mutate(intensity = 0.35) {
    // nudge sliders
    nudgeRange(els.spin, intensity);
    nudgeRange(els.trail, intensity);
    nudgeRange(els.zap, intensity);
    nudgeRange(els.spawn, intensity);
    nudgeRange(els.shockwave, intensity);
    nudgeRange(els.beatThresh, intensity);

    // occasional toggle flips
    if (Math.random() < 0.10 * intensity) els.glow.checked = !els.glow.checked;
    if (Math.random() < 0.06 * intensity) els.phosphor.checked = !els.phosphor.checked;

    readFromControls();
  }

  // init
  repopulateBankSelect();
  repopulatePresetSelect(state.bank);

  els.muted.checked = true;
  applySelectedPreset();

  els.bank.addEventListener("change", () => {
    state.bank = els.bank.value;
    repopulatePresetSelect(state.bank);
    applySelectedPreset();
  });

  els.preset.addEventListener("change", () => {
    state.preset = els.preset.value;
    applySelectedPreset();
  });

  Object.values(els).forEach(el => {
    if (!el) return;
    if (el === els.bank || el === els.preset) return;
    el.addEventListener("input", readFromControls);
    el.addEventListener("change", readFromControls);
  });

  readFromControls();

  
  // --- Overlays wiring (safe inside initUI) ---
  function bindCheck(el, key){
    if (!el) return;
    state[key] = !!el.checked;
    el.addEventListener("change", () => { state[key] = !!el.checked; });
  }
  function bindRange(el, key){
    if (!el) return;
    state[key] = parseFloat(el.value);
    el.addEventListener("input", () => { state[key] = parseFloat(el.value); });
  }

  bindCheck(els.ovHub, "ovHub");
  bindCheck(els.ovBig, "ovBig");
  bindCheck(els.ovSpoke, "ovSpoke");

  bindRange(els.ovThrob, "ovThrob");
  bindRange(els.ovHubR, "ovHubR");
  bindRange(els.ovHubAmp, "ovHubAmp");
  bindRange(els.ovHubRot, "ovHubRot");
  bindRange(els.ovBigR, "ovBigR");
  bindRange(els.ovBigAmp, "ovBigAmp");
  bindRange(els.ovBigRot, "ovBigRot");
  bindRange(els.ovSpokeLen, "ovSpokeLen");
  bindRange(els.ovSpokeAmp, "ovSpokeAmp");
  bindRange(els.ovSpokeRot, "ovSpokeRot");


return {
    els,
    state,
    api: {
      setSelection,
      next: () => nextPreset(+1),
      prev: () => nextPreset(-1),
      random: randomPreset,
      mutate,
    },
  };
}


// --- SHUFFLIZER_PALETTE_UI ---
function _shufPaletteMount(){
  const host = document.getElementById("ui");
  if (!host) return;

  // container
  const row = document.createElement("div");
  row.id = "paletteRow";
  row.style.display = "flex";
  row.style.alignItems = "center";
  row.style.gap = "8px";
  row.style.marginTop = "8px";

  const label = document.createElement("span");
  label.textContent = "Palette";
  label.style.opacity = "0.9";

  const sel = document.createElement("select");
  sel.id = "paletteSelect";
  sel.style.maxWidth = "220px";

  const presets = (window.SHUF_PRESETS || {});
  const names = Object.keys(presets);
  for (const name of names) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  }

  // set current
  const current = (window.SHUF && window.SHUF.name) ? window.SHUF.name : "Ember Grid";
  sel.value = current;

  sel.addEventListener("change", () => {
    const name = sel.value;
    const p = presets[name];
    if (!p) return;

    window.SHUF = Object.assign({ name }, p);
    // back-compat
    window.SHUF_PRIMARY = window.SHUF.primary;
    window.SHUF_ACCENT  = window.SHUF.accent;
    window.SHUF_GLOW    = window.SHUF.glow;
    window.SHUF_GLOW_FILL = window.SHUF.glowFill;
    window.SHUF_TINT = window.SHUF.tint;

    try { localStorage.setItem("shufflizer.palette.name", name); } catch {}

    // notify anyone who cares
    window.dispatchEvent(new CustomEvent("shufflizer:palette", { detail: window.SHUF }));
  });

  row.appendChild(label);
  row.appendChild(sel);

  host.appendChild(row);
}

// Mount after DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", _shufPaletteMount, { once: true });
} else {
  _shufPaletteMount();
}
// --- /SHUFFLIZER_PALETTE_UI ---

// --- Custom palette UI (Step2) ---
(function(){
  const KEY_NAME   = "shufflizer.palette.name";
  const KEY_CUSTOM = "shufflizer.palette.custom";

  function isValidColor(v){
    if (!v) return false;
    v = String(v).trim();
    if (!v) return false;
    if (v.startsWith("#")) return true;
    if (v.startsWith("rgb(")) return true;
    if (v.startsWith("rgba(")) return true;
    return false;
  }

  function clamp01(x){
    x = Number(x);
    if (!isFinite(x)) return 0;
    return Math.max(0, Math.min(1, x));
  }

  function el(tag, attrs){
    const n = document.createElement(tag);
    if (attrs){
      for (const k in attrs){
        if (k === "class") n.className = attrs[k];
        else if (k === "text") n.textContent = attrs[k];
        else n.setAttribute(k, attrs[k]);
      }
    }
    return n;
  }

  function ensureStyles(){
    if (document.getElementById("shuf-pal-styles")) return;
    const css = `
#shufCustomPalettePanel{margin-top:10px;padding:10px;border:1px solid rgba(255,255,255,.12);border-radius:10px;}
#shufCustomPalettePanel .shuf-pal-row{display:flex;align-items:center;gap:10px;margin:6px 0;}
#shufCustomPalettePanel .shuf-pal-label{min-width:88px;opacity:.85;font-size:12px;}
#shufCustomPalettePanel input[type="text"]{flex:1;min-width:0;}
#shufCustomPalettePanel input[type="range"]{flex:1;}
#shufCustomPalettePanel .shuf-pal-help{opacity:.7;font-size:11px;margin-top:6px;line-height:1.2;}
#shufCustomPalettePanel .shuf-pal-error{color:#ff8a8a;font-size:11px;margin-top:6px;display:none;}
`;
    const style = document.createElement("style");
    style.id = "shuf-pal-styles";
    style.textContent = css;
    document.head.appendChild(style);
  }

  function readCustom(){
    try{
      const raw = localStorage.getItem(KEY_CUSTOM);
      if (raw) return JSON.parse(raw);
    }catch(e){}
    // fallback defaults
    return { primary:"#39FF14", accent:"#7CFF5B", glow:"#39FF14", glowFill:"#39FF1440", tint:0.25 };
  }

  function writeCustom(obj){
    try{ localStorage.setItem(KEY_CUSTOM, JSON.stringify(obj)); }catch(e){}
  }

  function getStoredName(){
    try{ return localStorage.getItem(KEY_NAME) || ""; }catch(e){ return ""; }
  }

  function applyName(name){
    if (window.SHUF_applyPaletteByName) window.SHUF_applyPaletteByName(name);
    else try{ localStorage.setItem(KEY_NAME, name); }catch(e){}
  }

  function presetNames(){
    try{
      const p = window.SHUF_PRESETS || {};
      return Object.keys(p);
    }catch(e){
      return [];
    }
  }

  function findPaletteSelectByContext(){
    const selects = Array.from(document.querySelectorAll("select"));
    // Choose a select whose parent container includes the word "Palette"
    const ctx = selects.filter(sel => {
      const p = sel.parentElement;
      if (!p) return false;
      const t = (p.textContent || "");
      return /palette/i.test(t);
    });
    if (ctx.length) return ctx[0];

    // Fallback: look for a label-ish element "Palette" and a select nearby
    const els = Array.from(document.querySelectorAll("*"));
    for (const e of els){
      const txt = (e.textContent || "").trim();
      if (txt === "Palette" || txt === "Palette "){
        const p = e.parentElement;
        if (p){
          const s = p.querySelector("select");
          if (s) return s;
        }
      }
    }
    return null;
  }

  function ensurePaletteOptions(sel){
    if (!sel) return false;
    const names = presetNames();
    if (!names.length) return false;

    // If already populated with presets, do nothing
    const existing = Array.from(sel.options || []).map(o => (o.value || o.textContent || "").trim()).filter(Boolean);
    const hasAnyPreset = existing.some(v => names.includes(v));

    if (!sel.options || sel.options.length === 0 || !hasAnyPreset){
      // rebuild options
      sel.innerHTML = "";
      for (const n of names){
        const opt = document.createElement("option");
        opt.value = n;
        opt.textContent = n;
        sel.appendChild(opt);
      }
      // Add Custom at end
      const optC = document.createElement("option");
      optC.value = "Custom";
      optC.textContent = "Custom";
      sel.appendChild(optC);
    } else {
      // ensure Custom exists
      const hasCustom = existing.includes("Custom");
      if (!hasCustom){
        const optC = document.createElement("option");
        optC.value = "Custom";
        optC.textContent = "Custom";
        sel.appendChild(optC);
      }
    }

    // Select current stored palette name if possible
    const stored = getStoredName();
    if (stored){
      sel.value = stored;
    } else if (window.SHUF && window.SHUF.name){
      sel.value = window.SHUF.name;
    }
    return true;
  }

  function makeRow(label, input){
    const row = el("div", {"class":"shuf-pal-row"});
    row.appendChild(el("label", {"class":"shuf-pal-label", "text":label}));
    row.appendChild(input);
    return row;
  }

  function buildPanel(sel){
    ensureStyles();

    const panel = el("div", { id: "shufCustomPalettePanel" });
    const err = el("div", { id:"shufCustomPaletteError", "class":"shuf-pal-error", "text":"Invalid CSS color string." });

    const inPrimary  = el("input", { type:"text" });
    const inAccent   = el("input", { type:"text" });
    const inGlow     = el("input", { type:"text" });
    const inGlowFill = el("input", { type:"text" });
    const tint       = el("input", { type:"range", min:"0", max:"1", step:"0.01" });

    panel.appendChild(makeRow("Primary", inPrimary));
    panel.appendChild(makeRow("Accent", inAccent));
    panel.appendChild(makeRow("Glow", inGlow));
    panel.appendChild(makeRow("Glow fill", inGlowFill));
    panel.appendChild(makeRow("Tint", tint));
    panel.appendChild(el("div", {"class":"shuf-pal-help", "text":"Custom palette is saved locally in this browser."}));
    panel.appendChild(err);

    const cur = readCustom();
    inPrimary.value  = cur.primary  || "";
    inAccent.value   = cur.accent   || "";
    inGlow.value     = cur.glow     || "";
    inGlowFill.value = cur.glowFill || "";
    tint.value       = String(cur.tint ?? 0.25);

    let tmr = null;
    function schedule(){
      if (tmr) clearTimeout(tmr);
      tmr = setTimeout(applyNow, 60);
    }

    function applyNow(){
      const p  = inPrimary.value.trim();
      const a  = inAccent.value.trim();
      const g  = inGlow.value.trim();
      const gf = inGlowFill.value.trim();
      const tv = clamp01(tint.value);

      const ok = isValidColor(p) && isValidColor(a) && isValidColor(g) && isValidColor(gf);
      err.style.display = ok ? "none" : "block";
      if (!ok) return;

      writeCustom({ primary:p, accent:a, glow:g, glowFill:gf, tint:tv });

      if (sel && sel.value === "Custom"){
        applyName("Custom");
      }
    }

    [inPrimary, inAccent, inGlow, inGlowFill].forEach(inp => {
      inp.addEventListener("input", schedule);
      inp.addEventListener("change", schedule);
    });
    tint.addEventListener("input", schedule);
    tint.addEventListener("change", schedule);

    return panel;
  }

  function wire(sel){
    if (!sel || sel.__shufCustomWired) return;
    sel.__shufCustomWired = true;

    let panel = document.getElementById("shufCustomPalettePanel");
    if (!panel){
      panel = buildPanel(sel);
      sel.insertAdjacentElement("afterend", panel);
    }

    function refresh(){
      panel.style.display = (sel.value === "Custom") ? "" : "none";
    }

    sel.addEventListener("change", () => {
      if (sel.value === "Custom"){
        applyName("Custom");
      } else {
        applyName(sel.value);
      }
      refresh();
    });

    refresh();
  }

  function tryAttach(){
    const sel = findPaletteSelectByContext();
    if (!sel) return false;
    const ok = ensurePaletteOptions(sel);
    if (!ok) return false;
    wire(sel);
    return true;
  }

  // Retry for up to ~3 seconds (UI might build menu after load)
  function retryAttach(){
    const t0 = Date.now();
    const iv = setInterval(() => {
      if (tryAttach()){
        clearInterval(iv);
      } else if (Date.now() - t0 > 3000){
        clearInterval(iv);
      }
    }, 120);
  }

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", () => retryAttach());
  } else {
    retryAttach();
  }
})();
// STREAM_OVERRIDE_UI
(function(){
  const KEY = "shufflizer.stream.override";

  function findPaletteSelect(){
    const sels = Array.from(document.querySelectorAll("select"));
    // your palette select lives in a wrapper whose text includes "Palette"
    const hit = sels.find(sel => sel.parentElement && /palette/i.test(sel.parentElement.textContent || ""));
    return hit || null;
  }

  function addStreamOverrideUI(){
    const paletteSel = findPaletteSelect();
    if (!paletteSel) return false;

    if (document.getElementById("streamOverrideInput")) return true;

    const wrap = document.createElement("div");
    wrap.style.marginTop = "10px";

    const label = document.createElement("label");
    label.textContent = "Custom Stream URL (optional)";
    label.style.display = "block";
    label.style.fontSize = "12px";

    const input = document.createElement("input");
    input.type = "text";
    input.id = "streamOverrideInput";
    input.placeholder = "Leave blank for default. Example: https://example.com/stream.mp3";
    input.style.width = "100%";
    input.style.marginTop = "4px";
    try { input.value = localStorage.getItem(KEY) || ""; } catch(e) {}

    input.addEventListener("change", () => {
      const v = (input.value || "").trim();
      try {
        if (v) localStorage.setItem(KEY, v);
        else localStorage.removeItem(KEY);
      } catch(e) {}
      alert("Stream URL saved. Reload page to apply.");
    });

    wrap.appendChild(label);
    wrap.appendChild(input);

    // Put it right under the Palette selector
    paletteSel.insertAdjacentElement("afterend", wrap);
    return true;
  }

  function retryAttach(){
    const t0 = Date.now();
    const iv = setInterval(() => {
      if (addStreamOverrideUI()){
        clearInterval(iv);
      } else if (Date.now() - t0 > 3000){
        clearInterval(iv);
      }
    }, 120);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", retryAttach);
  } else {
    retryAttach();
  }
})();


// SKIP_TRACK_UI
(function(){
  const KEYNAME = "shufflizer.control.key";

  function findPaletteSelect(){
    const sels = Array.from(document.querySelectorAll("select"));
    const hit = sels.find(sel => sel.parentElement && /palette/i.test(sel.parentElement.textContent || ""));
    return hit || null;
  }

  function addSkipUI(){
    const paletteSel = findPaletteSelect();
    if (!paletteSel) return false;

    if (document.getElementById("shufSkipTrackBtn")) return true;

    const wrap = document.createElement("div");
    wrap.id = "shufSkipWrap";
    wrap.style.marginTop = "10px";
    wrap.style.display = "flex";
    wrap.style.gap = "8px";
    wrap.style.alignItems = "center";

    const btn = document.createElement("button");
    btn.id = "shufSkipTrackBtn";
    btn.textContent = "⏭ Skip track";
    btn.style.padding = "8px 10px";
    btn.style.borderRadius = "10px";
    btn.style.border = "1px solid rgba(255,255,255,.14)";
    btn.style.background = "transparent";
    btn.style.color = "inherit";
    btn.style.cursor = "pointer";

    const small = document.createElement("button");
    small.textContent = "Set key";
    small.style.padding = "8px 10px";
    small.style.borderRadius = "10px";
    small.style.border = "1px solid rgba(255,255,255,.14)";
    small.style.background = "transparent";
    small.style.color = "inherit";
    small.style.cursor = "pointer";
    small.title = "Stores your control key in this browser so Skip works (needed for public tunnel)";

    async function doSkip(){
      const key = (localStorage.getItem(KEYNAME) || "").trim();
      if (!key){
        alert("No control key set in this browser yet. Click 'Set key' first.");
        return;
      }
    }

    // JS-safe (avoid accidental Python tokens)
    btn.addEventListener("click", async () => {
      const key = (localStorage.getItem(KEYNAME) || "").trim();
      if (!key){
        alert("No control key set in this browser yet. Click 'Set key' first.");
        return;
      }
      btn.disabled = true;
      const old = btn.textContent;
      btn.textContent = "Skipping…";
      try{
        const r = await fetch("/control/next", { method: "POST", headers: { "X-Shufflizer-Key": key }});
        if (!r.ok){
          const t = await r.text();
          alert("Skip failed: " + r.status + " " + t);
        }
      }catch(e){
        alert("Skip failed: " + e);
      }finally{
        btn.textContent = old;
        btn.disabled = false;
      }
    });

    small.addEventListener("click", () => {
      const cur = (localStorage.getItem(KEYNAME) || "").trim();
      const v = prompt("Enter control key for Skip (saved in this browser only):", cur);
      if (v === null) return;
      const t = (v || "").trim();
      if (t) localStorage.setItem(KEYNAME, t);
      else localStorage.removeItem(KEYNAME);
      alert("Saved. (This does not change the server key file.)");
    });

    wrap.appendChild(btn);
    wrap.appendChild(small);

    // Put it under the Palette selector
    paletteSel.insertAdjacentElement("afterend", wrap);
    return true;
  }

  function retry(){
    const t0 = Date.now();
    const iv = setInterval(() => {
      if (addSkipUI()) clearInterval(iv);
      else if (Date.now() - t0 > 3000) clearInterval(iv);
    }, 120);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", retry);
  else retry();
})();
