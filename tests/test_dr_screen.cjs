const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync('synology/dr-screen.js', 'utf8');
async function pageTest(blocked) {
  const elements = {};
  function element() { return {hidden:false, listeners:{}, addEventListener(k,f){this.listeners[k]=f;}, append(f){this.frame=f;}}; }
  for (const id of ['player','status','start','visualizer','volume']) elements[id] = element();
  elements.player.paused = true;
  elements.player.play = () => { if (blocked) return Promise.reject({name:'NotAllowedError'}); elements.player.paused=false; return Promise.resolve(); };
  const edges = [], gains = [], messages = [];
  const node = name => ({connect(other){edges.push([name,other.name]);},name});
  const analyser = node('analyser'), gain = node('gain');
  gain.gain = {setValueAtTime(value){gains.push(value);}};
  let receive;
  const context = {state:blocked?'suspended':'running',currentTime:0,destination:node('speaker'),
    createMediaElementSource(p){assert.equal(p,elements.player);return node('player');},
    createAnalyser(){return analyser;},createGain(){return gain;},resume(){return Promise.resolve();},addEventListener(){}};
  const window = {AudioContext: function(){return context;},addEventListener(){},EventBridge:{scriptEventReceived:{connect(f){receive=f;}},emitWebEvent(raw){messages.push(JSON.parse(raw));}}};
  vm.runInNewContext(code,{window,document:{getElementById:id=>elements[id],createElement:element},setInterval(){return 1;},clearInterval(){},setTimeout,clearTimeout});
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(edges,[['player','analyser'],['analyser','gain'],['gain','speaker']]);
  assert.equal(window.playerAudio.analyser,analyser);
  assert.deepEqual(messages,[{hello:true}]);
  elements.visualizer.frame.listeners.load();
  assert.deepEqual(messages[1],{ready:true});
  receive('{"volume":0}'); receive('{"volume":75}'); receive('{"volume":120}');
  receive('{"volume":"50"}'); receive('broken'); receive('{"state":{}}');
  assert.deepEqual(gains,[0,0.75,1]);
  elements.volume.value='35';elements.volume.listeners.input();
  assert.equal(gains.at(-1),0.35);assert.deepEqual(messages.at(-1),{sound:35});
  if (blocked) {
    // A volume update must not hide the gesture fallback while suspended.
    assert.match(elements.status.textContent,/Autoplay blocked/);
    assert.equal(elements.start.hidden,false);
  } else assert.match(elements.status.textContent,/Live screen audio/);
}
function entityTest() {
  let handler, messageHandler, timer;
  const sent=[], values=[];
  const signal = setter => ({connect:setter,disconnect(){}});
  const sandbox = {Settings:{getValue(){return 80;},setValue(...args){values.push(args);}},MyAvatar:{sessionUUID:'me'},
    Entities:{webEventReceived:signal(f=>handler=f),emitScriptEvent(id,raw){sent.push([id,JSON.parse(raw)]);}},
    Messages:{subscribe(){},unsubscribe(){},messageReceived:signal(f=>messageHandler=f)},
    Script:{setInterval(f){timer=f;return 1;},clearInterval(){}}};
  const Constructor=vm.runInNewContext(fs.readFileSync('synology/dr-screen-entity.js','utf8'),sandbox);
  const entity=new Constructor(); entity.preload('screen');
  handler('other','{"hello":true}'); assert.equal(sent.length,0);
  handler('screen','{"hello":true}'); handler('screen','{"ready":true}');
  assert.equal(sent.length,2); assert.equal(sent[0][1].volume,80);
  timer(); assert.equal(sent.length,2);
  messageHandler('darkride.shufflizer','{"sound":25}','someone',false);
  assert.equal(values.length,0);
  messageHandler('darkride.shufflizer','{"sound":25}','me',true);
  assert.equal(values[0][0],'darkride/shufflizer/sound'); assert.equal(values[0][1],25);
  entity.unload();
}
(async()=>{await pageTest(false);await pageTest(true);entityTest();console.log('DR screen graph, handshake, volume, autoplay and entity isolation passed');})().catch(error=>{console.error(error);process.exitCode=1;});
