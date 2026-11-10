const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync('synology/app.js','utf8');
const storage = new Map();
function boot({blockedStorage=false, native=true}={}) {
  class Element {
    constructor() { this.children=[]; this.listeners={}; this.value=''; this.paused=true; this.currentTime=0; this.duration=300; this.attributes={}; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children=children; }
    addEventListener(event, fn) { (this.listeners[event] ||= new Set()).add(fn); }
    removeEventListener(event, fn) { this.listeners[event]?.delete(fn); }
    emit(event) { for (const fn of [...(this.listeners[event] || [])]) fn(); }
    set src(value) { this.attributes.src=value; this.currentTime=0; }
    get src() { return this.attributes.src; }
    getAttribute(name) { return this.attributes[name]; }
    removeAttribute(name) { delete this.attributes[name]; }
    canPlayType(type) { return type==='audio/mpeg' || native ? 'probably' : ''; }
    load() { if (!this.deferMetadata) this.emit('loadedmetadata'); }
    play() { this.paused=false; this.emit('play'); return Promise.resolve(); }
    pause() { this.paused=true; }
  }
  const ids=[...fs.readFileSync('synology/index.html','utf8').matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
  const elements=Object.fromEntries(ids.map(id=>[id,new Element()]));
  const tracks=[{id:11,artist:'Test',title:'First',album:'Album',available:true,mime_type:'audio/flac'},
    {id:12,artist:'Test',title:'Second',album:'Album',available:true,mime_type:'audio/flac'}];
  const node=()=>({connect(){}});
  const window={AudioContext:class {constructor(){this.destination=node();} createMediaElementSource(){return node();} createAnalyser(){return node();} async resume(){} }};
  const localStorage={getItem(key){if(blockedStorage)throw Error('blocked');return storage.get(key)||null;},
    setItem(key,value){if(blockedStorage)throw Error('blocked');storage.set(key,value);}};
  const context=vm.createContext({window,document:{getElementById:id=>elements[id],createElement:()=>new Element()},
    localStorage,setTimeout,clearTimeout,console,
    fetch:async url=>({ok:true,json:async()=>url==='/api/styles'?{styles:[],tagged:2,untagged:0}:{tracks,has_more:false}})});
  vm.runInContext(code,context);
  return elements;
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  const e=boot(); await flush();
  assert.equal(e.quality.value,'original','Lossless/original must be the default');
  await e.playMatches.onclick();
  assert.equal(e.player.src,'/media/11');
  e.player.currentTime=87.25;
  e.player.muted=true;
  e.quality.value='mp3'; await e.quality.onchange();
  assert.equal(e.player.src,'/media/11?quality=mp3');
  assert.equal(e.player.currentTime,87.25);
  assert.equal(e.player.paused,false);
  assert.equal(e.player.muted,true,'Changing quality preserves mute state');
  assert.equal(e.queue.children.length,2);
  assert.equal(e.title.textContent,'Test — First');
  const reload=boot(); await flush();
  assert.equal(reload.quality.value,'mp3','Choice must restore per browser');
  await e.toggle.onclick();
  e.player.currentTime=132.5;
  e.quality.value='original'; await e.quality.onchange();
  assert.equal(e.player.currentTime,132.5);
  assert.equal(e.player.paused,true,'Paused playback must stay paused');
  await e.next.onclick();
  assert.equal(e.player.src,'/media/12');
  assert.equal(e.player.currentTime,0,'Next track starts at its beginning');
  e.player.currentTime=42;
  e.player.deferMetadata=true;
  e.quality.value='mp3'; const first=e.quality.onchange();
  e.quality.value='original'; const second=e.quality.onchange();
  e.player.emit('loadedmetadata'); await Promise.all([first,second]);
  assert.equal(e.player.src,'/media/12');
  assert.equal(e.player.currentTime,42,'Rapid switching keeps the requested position');
  assert.equal(e.player.paused,false);
  e.quality.value='mp3'; const cancelled=e.quality.onchange();
  await e.toggle.onclick(); // Pause while waiting for conversion.
  e.player.emit('loadedmetadata'); await cancelled;
  assert.equal(e.player.paused,true);
  const unavailable=boot({native:false,blockedStorage:true}); await flush();
  assert.equal(unavailable.quality.value,'original','Storage failures preserve the default');
  await unavailable.playMatches.onclick();
  assert.match(unavailable.qualityInfo.textContent,/does not report support/);
  unavailable.player.currentTime=55;
  unavailable.player.deferMetadata=true;
  unavailable.quality.value='mp3'; const failed=unavailable.quality.onchange();
  unavailable.player.emit('error'); await failed;
  assert.equal(unavailable.queue.children.length,2,'Conversion errors preserve the queue');
  unavailable.player.deferMetadata=false;
  unavailable.quality.value='original'; await unavailable.quality.onchange();
  assert.equal(unavailable.player.currentTime,55,'Recovery preserves the requested position');
  console.log('Quality UI tests passed: default, persistence, position, pause, queue, rapid changes, conversion cancellation and recovery.');
})().catch(error=>{console.error(error);process.exitCode=1;});
