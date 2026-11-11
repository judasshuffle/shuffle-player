// Exercise the actual queue UI code with a lightweight DOM/WebAudio test double.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor() { this.children = []; this.listeners = {}; this.value = ''; this.paused = true; this.attributes = {}; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  addEventListener(event, callback) { this.listeners[event] = callback; }
  removeEventListener(event, callback) { if (this.listeners[event] === callback) delete this.listeners[event]; }
  canPlayType() { return 'probably'; }
  set src(value) { this.attributes.src = value; }
  get src() { return this.attributes.src; }
  getAttribute(name) { return this.attributes[name]; }
  removeAttribute(name) { delete this.attributes[name]; }
  async play() { this.paused = false; if (this.listeners.play) await this.listeners.play(); }
  pause() { this.paused = true; }
  load() { this.currentTime = 0; this.duration = 300; this.listeners.loadedmetadata?.(); }
}
const elements = Object.fromEntries(['originalLink','mp3Link','quality','qualityInfo','styleSelect','styleInfo','artwork','player','title','album','status','visualizer','queue','prev','next','toggle','search','q','results','more','interpretation','playMatches','queueMatches','shuffleAll'].map(id => [id,new Element()]));
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

for (const id of ['listenHere','stationSeek','stationTime','stationStatus','queueInfo']) elements[id] = new Element();
let station = {version:1,index:0,playing:true,position:8,current:{...tracks[0],duration:300},queue_count:2,queue:tracks.slice(0,2),queue_start:0,can_control:true,control_token:'test-token'};
const commands = [], timers = [];
const context = vm.createContext({window, document:{getElementById:id=>elements[id],createElement:()=>new Element()},
  performance:{now:()=>0}, localStorage:{getItem:()=>null,setItem:()=>{}},
  fetch:async (url, options)=>{
    if (options?.method === 'POST') { commands.push(JSON.parse(options.body)); return {ok:true,json:async()=>station}; }
    return {ok:true,json:async()=>url.startsWith('/api/station') ? station : url === '/api/styles' ? {styles:[],tagged:2,untagged:1} : {tracks,has_more:false}};
  }, console,setTimeout:(fn,ms)=>{ if(ms===1000) {timers.push(fn);return 1;} return setTimeout(fn,ms); },clearTimeout});
vm.runInContext(fs.readFileSync('synology/app.js','utf8'), context);
vm.runInContext(fs.readFileSync('synology/station.js','utf8'), context);
const flush = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  await flush();
  assert.ok(elements.title.textContent.includes('Copper Pulse'));
  assert.equal(elements.player.paused,true,'Monitor defaults off to avoid double audio with DarkRide');
  await elements.playMatches.onclick();
  assert.deepEqual(commands.at(-1),{action:'replace',ids:[1,2],repeat:false});
  await elements.queueMatches.onclick();
  assert.equal(commands.at(-1).action,'append');
  await elements.next.onclick(); assert.equal(commands.at(-1).action,'next');
  await elements.toggle.onclick(); assert.equal(commands.at(-1).action,'toggle');
  elements.stationSeek.value = '42'; await elements.stationSeek.onchange();
  assert.deepEqual(commands.at(-1),{action:'seek',position:42});
  await elements.queue.children[1].children[0].onclick();
  assert.deepEqual(commands.at(-1),{action:'select',index:1});
  elements.listenHere.checked=true; elements.listenHere.onchange(); await flush();
  assert.equal(elements.player.src,'/media/1');
  assert.equal(elements.player.currentTime,8);
  assert.equal(elements.player.paused,false);
  const count=commands.length;
  elements.quality.value='mp3'; await elements.quality.onchange();
  assert.equal(elements.player.src,'/media/1?quality=mp3');
  assert.equal(commands.length,count,'Quality changes never alter the shared station');
  elements.player.listeners.ended(); await flush();
  assert.equal(commands.length,count,'Browser end never advances station');
  elements.listenHere.checked=false; elements.listenHere.onchange();
  assert.equal(elements.player.paused,true);
  assert.equal(commands.length,count,'Disabling monitor does not pause DarkRide');
  station={...station,can_control:false}; await timers.shift()(); await flush();
  await elements.next.onclick(); assert.equal(commands.length,count,'Public page cannot command station');
  console.log('Shared station UI tests passed: queue, transport, seek, monitor, quality and public read-only mode.');
})().catch(error=>{console.error(error);process.exitCode=1;});
