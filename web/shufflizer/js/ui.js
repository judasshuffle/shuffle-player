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

  function normHex(s){
    if (!s) return null;
    s = String(s).trim();
    if (!s) return null;
    if (s[0] !== "#") s = "#" + s;
    const m3 = /^#([0-9a-fA-F]{3})$/.exec(s);
    if (m3){
      const a = m3[1];
      return ("#" + a[0]+a[0] + a[1]+a[1] + a[2]+a[2]).toUpperCase();
    }
    const m6 = /^#([0-9a-fA-F]{6})$/.exec(s);
    if (m6) return ("#" + m6[1]).toUpperCase();
    return null;
  }

  function normHex6or8(s){
    if (!s) return null;
    s = String(s).trim();
    if (!s) return null;
    if (s[0] !== "#") s = "#" + s;
    const m6 = /^#([0-9a-fA-F]{6})$/.exec(s);
    if (m6) return ("#" + m6[1]).toUpperCase();
    const m8 = /^#([0-9a-fA-F]{8})$/.exec(s);
    if (m8) return ("#" + m8[1]).toUpperCase();
    const m3 = /^#([0-9a-fA-F]{3})$/.exec(s);
    if (m3){
      const a = m3[1];
      return ("#" + a[0]+a[0] + a[1]+a[1] + a[2]+a[2]).toUpperCase();
    }
    return null;
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
    if (window.SHUF_getCustomPalette) return window.SHUF_getCustomPalette();
    try{
      const raw = localStorage.getItem(KEY_CUSTOM);
      if (raw) return JSON.parse(raw);
    }catch(e){}
    return { primary:"#39FF14", accent:"#7CFF5B", glow:"#39FF14", glowFill:"#39FF1440", tint:0.25 };
  }

  function writeCustom(partial){
    if (window.SHUF_setCustomPalette) return window.SHUF_setCustomPalette(partial);
    const cur = readCustom();
    const next = Object.assign({}, cur, partial);
    try{ localStorage.setItem(KEY_CUSTOM, JSON.stringify(next)); }catch(e){}
    return next;
  }

  function applyName(name){
    if (window.SHUF_applyPaletteByName) window.SHUF_applyPaletteByName(name);
    else try{ localStorage.setItem(KEY_NAME, name); }catch(e){}
  }

  function findPaletteSelect(){
    const presets = window.SHUF_PRESETS ? Object.keys(window.SHUF_PRESETS) : [];
    const selects = Array.from(document.querySelectorAll("select"));
    for (const s of selects){
      const opts = Array.from(s.options || []).map(o => (o.value || o.textContent || "").trim());
      if (presets.some(p => opts.includes(p))) return s;
    }
    return document.querySelector('select[id*="palette" i],select[name*="palette" i]') || null;
  }

  function ensureCustomOption(sel){
    if (!sel) return;
    const has = Array.from(sel.options).some(o => (o.value || o.textContent) === "Custom");
    if (!has){
      const opt = document.createElement("option");
      opt.value = "Custom";
      opt.textContent = "Custom";
      sel.appendChild(opt);
    }
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
    const err = el("div", {
      id:"shufCustomPaletteError",
      "class":"shuf-pal-error",
      "text":"One or more hex values are invalid. Use #RGB, #RRGGBB, and Glow fill may also use #RRGGBBAA."
    });

    const inPrimary  = el("input", { type:"text", placeholder:"#RRGGBB" });
    const inAccent   = el("input", { type:"text", placeholder:"#RRGGBB" });
    const inGlow     = el("input", { type:"text", placeholder:"#RRGGBB" });
    const inGlowFill = el("input", { type:"text", placeholder:"#RRGGBB or #RRGGBBAA" });
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
    function scheduleApply(){
      if (tmr) clearTimeout(tmr);
      tmr = setTimeout(applyNow, 80);
    }

    function applyNow(){
      const p  = normHex(inPrimary.value);
      const a  = normHex(inAccent.value);
      const g  = normHex(inGlow.value);
      const gf = normHex6or8(inGlowFill.value);
      const tv = clamp01(tint.value);

      const ok = !!p && !!a && !!g && !!gf;
      err.style.display = ok ? "none" : "block";

      const partial = { tint: tv };
      if (p)  partial.primary  = p;
      if (a)  partial.accent   = a;
      if (g)  partial.glow     = g;
      if (gf) partial.glowFill = gf;

      writeCustom(partial);

      if (sel && sel.value === "Custom"){
        applyName("Custom");
      }
    }

    [inPrimary, inAccent, inGlow, inGlowFill].forEach(inp => {
      inp.addEventListener("input", scheduleApply);
      inp.addEventListener("change", scheduleApply);
    });
    tint.addEventListener("input", scheduleApply);
    tint.addEventListener("change", scheduleApply);

    return panel;
  }

  function attach(){
    const sel = findPaletteSelect();
    if (!sel) return;

    ensureCustomOption(sel);

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
        const cur = readCustom();
        writeCustom(cur);
        applyName("Custom");
      } else {
        applyName(sel.value);
      }
      refresh();
    });

    refresh();
  }

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", () => setTimeout(attach, 0));
  } else {
    setTimeout(attach, 0);
  }
})();
