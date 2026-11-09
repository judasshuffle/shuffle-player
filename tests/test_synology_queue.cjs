// Exercise the actual queue UI code with a lightweight DOM/WebAudio test double.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor() { this.children = []; this.listeners = {}; this.value = ''; this.paused = true; this.attributes = {}; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  addEventListener(event, callback) { this.listeners[event] = callback; }
  set src(value) { this.attributes.src = value; }
  get src() { return this.attributes.src; }
  getAttribute(name) { return this.attributes[name]; }
  removeAttribute(name) { delete this.attributes[name]; }
  async play() { this.paused = false; if (this.listeners.play) await this.listeners.play(); }
  pause() { this.paused = true; }
  load() {}
}
const elements = Object.fromEntries(['player','title','album','status','visualizer','queue','prev','next','toggle','search','q','results','more','interpretation','playMatches','queueMatches','shuffleAll'].map(id => [id,new Element()]));
const tracks = [{id:1,title:'Copper Pulse',artist:'Preview Synth',album:'Tests',available:true},
                {id:2,title:'Night Orbit',artist:'Preview Synth',album:'Tests',available:true},
                {id:3,title:'Missing',available:false}];
const node = () => ({connect() {}});
const window = {AudioContext: class {
  constructor() { this.destination = node(); }
  createMediaElementSource() { return node(); }
  createAnalyser() { return node(); }
  async resume() {}
}};
const context = vm.createContext({window, document:{getElementById:id=>elements[id],createElement:()=>new Element()},
  fetch:async()=>({ok:true,json:async()=>({tracks,has_more:false})}),console});
vm.runInContext(fs.readFileSync('synology/app.js','utf8'), context);
const flush = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  await flush();
  assert.equal(elements.results.children.length,3);
  assert.equal(elements.results.children[2].children[1].disabled,true);
  elements.results.children[0].children[2].onclick(); // Add Copper.
  elements.results.children[1].children[2].onclick(); // Add Orbit.
  assert.equal(elements.queue.children.length,2);
  await elements.toggle.onclick();
  assert.equal(elements.player.src,'/media/1');
  assert.equal(elements.player.paused,false);
  assert.equal(window.currentTrackTitle,'Preview Synth — Copper Pulse');
  elements.player.listeners.ended(); await flush();
  assert.equal(elements.player.src,'/media/2');
  await elements.prev.onclick();
  assert.equal(elements.player.src,'/media/1');
  await elements.toggle.onclick();
  assert.equal(elements.player.paused,true);
  assert.ok(window.playerAudio.analyser);
  assert.equal(elements.visualizer.children[0].src,'/visualizer/index.html?embed=1');
  elements.q.value = 'play 70s Bob Dylan';
  elements.search.onsubmit({preventDefault() {}}); await flush();
  assert.equal(elements.player.paused,true, 'Typed commands must not autoplay');
  await elements.queueMatches.onclick();
  assert.equal(elements.queue.children.length,4);
  assert.equal(elements.player.paused,true, 'Queue matches must not change playback');
  await elements.playMatches.onclick();
  assert.equal(elements.queue.children.length,2);
  assert.equal(elements.player.paused,false);
  await elements.shuffleAll.onclick();
  assert.equal(elements.queue.children.length,2, 'Shuffle excludes unavailable files');
  console.log('Queue UI tests passed, including command review without autoplay, Play/Queue matches and Shuffle All.');
})().catch(error => { console.error(error);process.exitCode=1; });
