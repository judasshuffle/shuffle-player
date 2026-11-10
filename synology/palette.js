// Shared by the player and its same-origin visualizer; preferences stay in this browser.
(() => {
  const sheet = document.createElement('style');
  sheet.textContent = `
    :root { color-scheme:dark; --green:var(--shuf-primary); --panel:color-mix(in srgb,var(--shuf-glow) 14%,#10151c); }
    body { background:color-mix(in srgb,var(--shuf-primary) 7%,#0a0e14); color:color-mix(in srgb,var(--shuf-accent) 12%,white); }
    section,#ui,.embedded #ui { background:color-mix(in srgb,var(--shuf-glow) 14%,#10151c); border-color:color-mix(in srgb,var(--shuf-primary) 40%,#354a50); }
    h1,h2,#title,#ui,.embedded #ui,.npTextUi { color:color-mix(in srgb,var(--shuf-primary) 55%,white); }
    .muted,.small { color:color-mix(in srgb,var(--shuf-accent) 30%,#c3cbd0); }
    button { background:color-mix(in srgb,var(--shuf-primary) 70%,white); color:#10151c; }
    input,select { background:color-mix(in srgb,var(--shuf-primary) 8%,#10151c); color:#f5f7fa; border-color:var(--shuf-primary); accent-color:var(--shuf-primary); }
    button:focus-visible,input:focus-visible,select:focus-visible { outline:2px solid var(--shuf-accent); outline-offset:3px; }
    .track,#ui hr { border-color:color-mix(in srgb,var(--shuf-primary) 25%,#354a50); }
    #status { color:color-mix(in srgb,var(--shuf-accent) 60%,white); }
    #artwork,iframe { box-shadow:0 0 18px color-mix(in srgb,var(--shuf-glow) 22%,transparent); }
    audio { accent-color:var(--shuf-primary); }
    a { color:color-mix(in srgb,var(--shuf-accent) 65%,white); }
    #paletteRow { flex-wrap:wrap; }
    #shufCustomPalettePanel { flex-basis:100%; }
  `;
  document.head.appendChild(sheet);
  const presets = {
    'Phosphor Prime': ['rgba(0,255,102,.95)', 'rgba(102,255,208,.9)', 'rgba(0,170,68,.9)', .65],
    'Ember Grid': ['rgba(255,146,0,.95)', 'rgba(255,205,115,.9)', 'rgba(215,123,95,.9)', .65],
    'Copper Pulse': ['rgba(241,142,63,.95)', 'rgba(229,149,121,.9)', 'rgba(193,76,50,.9)', .65],
    'Overdrive': ['rgba(255,197,0,.95)', 'rgba(236,65,11,.9)', 'rgba(179,0,25,.9)', .7],
    'Midnight Alloy': ['rgba(255,164,0,.95)', 'rgba(108,52,0,.9)', 'rgba(65,34,42,.9)', .7],
    'Analog Drift': ['rgba(255,205,135,.95)', 'rgba(188,117,118,.9)', 'rgba(105,107,126,.9)', .6]
  };
  window.SHUF_PRESETS = Object.fromEntries(Object.entries(presets).map(([name, p]) =>
    [name, {primary:p[0], accent:p[1], glow:p[2], glowFill:p[2], tint:p[3]}]));
  const read = key => { try { return localStorage.getItem(key); } catch { return null; } };
  const save = (key, value) => { try { localStorage.setItem(key, value); } catch {} };
  const valid = color => typeof color === 'string' && CSS.supports('color', color);
  function custom() {
    let stored = {};
    try { stored = JSON.parse(read('shufflizer.palette.custom')) || {}; } catch {}
    const result = {...window.SHUF_PRESETS['Ember Grid']};
    for (const key of ['primary', 'accent', 'glow', 'glowFill']) {
      if (valid(stored[key])) result[key] = stored[key];
    }
    if (Number.isFinite(Number(stored.tint))) result.tint = Math.max(0, Math.min(1, Number(stored.tint)));
    return result;
  }
  function theme(palette) {
    const style = document.documentElement.style;
    for (const key of ['primary', 'accent', 'glow', 'glowFill']) {
      if (valid(palette[key])) style.setProperty('--shuf-' + key, palette[key]);
    }
  }
  // Called by the embedded frame. Only that frame may update the player theme.
  window.applyPlayerPalette = (palette, source) => {
    const frame = document.querySelector('#visualizer iframe');
    if (frame && source === frame.contentWindow) theme(palette);
  };
  function publish() {
    const p = window.SHUF;
    window.SHUF_PRIMARY = p.primary;
    window.SHUF_ACCENT = p.accent;
    window.SHUF_GLOW = p.glow;
    window.SHUF_GLOW_FILL = p.glowFill;
    window.SHUF_TINT = p.tint;
    theme(p);
    if (window.parent !== window && typeof window.parent.applyPlayerPalette === 'function') {
      window.parent.applyPlayerPalette(p, window);
    }
  }
  window.SHUF_getCustomPalette = custom;
  window.SHUF_setCustomPalette = partial => {
    const next = {...custom(), ...partial};
    save('shufflizer.palette.custom', JSON.stringify(next));
    if (window.SHUF.name === 'Custom') window.SHUF_applyPaletteByName('Custom');
    return next;
  };
  window.SHUF_applyPaletteByName = name => {
    if (name !== 'Custom' && !window.SHUF_PRESETS[name]) name = 'Ember Grid';
    window.SHUF = {name, ...(name === 'Custom' ? custom() : window.SHUF_PRESETS[name])};
    save('shufflizer.palette.name', name);
    publish();
  };
  window.addEventListener('shufflizer:palette', publish);
  window.SHUF_applyPaletteByName(read('shufflizer.palette.name') || 'Ember Grid');
})();
