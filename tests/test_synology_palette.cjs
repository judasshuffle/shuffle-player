const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const storage = new Map();
function boot(parent) {
  const props = new Map(), elements = {}, events = {};
  function element() {
    return {children:[], style:{}, value:'', listeners:{},
      get options() { return [...String(this.innerHTML || '').matchAll(/value="([^"]+)"/g)].map(m=>({value:m[1]})); },
      appendChild(child) { this.children.push(child); if (child.id) elements[child.id] = child; },
      addEventListener(name, callback) { this.listeners[name] = callback; }};
  }
  elements.ui = element();
  const document = {head:element(), documentElement:{style:{setProperty:(k,v)=>props.set(k,v)}},
    createElement:element, getElementById:id=>elements[id], readyState:'complete',
    querySelector:()=>document.frame || null};
  const window = {addEventListener:(name, fn)=>events[name]=fn,
    dispatchEvent:event=>events[event.type]?.(event)};
  window.parent = parent || window;
  window.document = document;
  const context = vm.createContext({window,document,CSS:{supports:(_,v)=>/^(#|rgba?\()/.test(v)},
    localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},
    CustomEvent:class {constructor(type, opts) {this.type=type;this.detail=opts.detail;}}});
  vm.runInContext(fs.readFileSync('synology/palette.js','utf8'),context);
  return {window,document,context,props,elements};
}
const parent = boot();
const child = boot(parent.window);
parent.document.frame = {contentWindow:child.window};
const ui = fs.readFileSync('web/shufflizer/js/ui.js','utf8');
for (const id of ['bank','preset','muted','glow','phosphor','titleParticles','spin','trail','zap','spawn','shockwave','beatThresh']) {
  parent.elements[id] = parent.document.createElement('input');
}
const presets = fs.readFileSync('web/shufflizer/js/presets.js','utf8').replace(/\bexport /g,'');
const core = ui.slice(0,ui.indexOf('// --- SHUFFLIZER_PALETTE_UI ---'))
  .replace(/import[^\r\n]+;\r?\n/,'').replace('export function initUI','function initUI');
vm.runInContext('(() => { const document = window.parent.document;\n' + presets + '\n' + core +
  '\nwindow.testControls = initUI(); })();',child.context);
assert.equal(child.window.testControls.els.bank,parent.elements.bank);
parent.elements.preset.value = 'Hot & Zappy';
parent.elements.preset.listeners.change();
assert.equal(child.window.testControls.state.spin,2.2,'External preset changes must reach renderer state');
const anotherBank = parent.elements.bank.options[1].value;
parent.elements.bank.value = anotherBank;
parent.elements.bank.listeners.change();
assert.equal(child.window.testControls.state.bank,anotherBank);
assert.ok(child.window.testControls.state.effectId);
vm.runInContext('(() => { const document = window.parent.document;\n' +
  ui.slice(ui.indexOf('// --- SHUFFLIZER_PALETTE_UI ---'),
  ui.indexOf('// --- /SHUFFLIZER_PALETTE_UI ---')) + '\n})();',child.context);
const select = parent.elements.paletteSelect;
assert.equal(child.elements.paletteSelect,undefined,'Controls must mount outside the visualizer frame');
assert.equal(select.children.length,6, 'Presets must exist before the actual selector mounts');
select.value = 'Phosphor Prime';
select.listeners.change();
assert.equal(child.window.SHUF.name,'Phosphor Prime');
assert.equal(child.props.get('--shuf-primary'),parent.props.get('--shuf-primary'));
assert.equal(child.window.SHUF_GLOW,child.window.SHUF.glow);
assert.equal(storage.get('shufflizer.palette.name'),'Phosphor Prime');
child.window.SHUF_setCustomPalette({primary:'rgba(20,40,200,.9)',accent:'#ffaaff',glow:'#224488',tint:.8});
child.window.SHUF_applyPaletteByName('Custom');
assert.equal(parent.props.get('--shuf-primary'),'rgba(20,40,200,.9)');
assert.equal(child.window.SHUF_TINT,.8);
const reloaded = boot();
assert.equal(reloaded.window.SHUF.name,'Custom');
assert.equal(reloaded.props.get('--shuf-primary'),'rgba(20,40,200,.9)');
parent.window.applyPlayerPalette({primary:'#ffffff'},{});
assert.equal(parent.props.get('--shuf-primary'),'rgba(20,40,200,.9)', 'Unrelated frames cannot set theme');
console.log('Palette tests passed: actual selector, renderer globals, parent theme, custom colours and reload persistence.');
