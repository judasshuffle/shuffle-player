const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const Features=require('../synology/music-features.js');
let receive,messageHandler,now=10000,publisher='',local=[],shared=[],sent=[];
const signal=fn=>({connect:fn,disconnect(){}});
const sandbox={Date:{now:()=>now},Settings:{getValue(key,fallback){return key.endsWith('musicPublisherEntity')?publisher:fallback;},setValue(){}},
  MyAvatar:{sessionUUID:'viewer'},Entities:{webEventReceived:signal(f=>receive=f),emitScriptEvent(id,raw){sent.push(JSON.parse(raw));}},
  Messages:{subscribe(){},unsubscribe(){},messageReceived:signal(f=>messageHandler=f),sendLocalMessage(c,r){local.push([c,JSON.parse(r)]);},sendMessage(c,r){shared.push([c,JSON.parse(r)]);}},
  Script:{setInterval(){return 1;},clearInterval(){}}};
const Constructor=vm.runInNewContext(fs.readFileSync('synology/dr-screen-entity.js','utf8'),sandbox);
const entity=new Constructor();entity.preload('screen');
const f=new Features(44100,4096).update(new Float32Array(4096),new Float32Array(2048).fill(-Infinity),0);
let sequence=0;
const packet=()=>({type:'shufflizer.music',v:1,session:'test',epoch:0,seq:++sequence,t:1,wall:now,state:'playing',stationTrackId:'123',f:JSON.parse(JSON.stringify(f))});
function emit(p,id='screen'){receive(id,JSON.stringify(p));now+=50;}
emit(packet(),'other');assert.equal(local.length,0);
emit(packet());assert.equal(local.length,1);assert.equal(shared.length,0,'No implicit domain broadcaster');
assert.equal(local[0][0],'darkride.shufflizer.music.v1');assert.equal(local[0][1].sourceEntity,'screen');
const repeat=packet();emit(repeat);emit(repeat);assert.equal(local.length,2,'Drop duplicate sequence');
const bad=[p=>p.f.rms='1',p=>p.f.bands=[1],p=>p.f.bass=2,p=>p.f.pitchHz='440',p=>p.v=2,
  p=>p.f.extra='world command',p=>p.seq=-1,p=>p.f.silent='yes',p=>p.state='invented'];
for(const corrupt of bad){const p=packet();corrupt(p);emit(p);}assert.equal(local.length,2);
publisher='screen';for(let i=0;i<20;i++)emit(packet());assert.equal(shared.length,10,'Shared output capped at 10Hz');
assert.equal(local.length,22);assert.equal(shared[0][0],'darkride.shufflizer.music.shared.v1');
assert(shared.every(([,p])=>Buffer.byteLength(JSON.stringify(p))<=1200));
publisher='different-screen';emit(packet());assert.equal(shared.length,10);
const unicode=packet();unicode.stationTrackId='\u2603'.repeat(64);emit(unicode);
assert(local.every(([,p])=>Buffer.byteLength(JSON.stringify(p))<=1200));
receive('screen','{"hello":true}');assert.equal(sent.at(-1).volume,100,'Original volume handshake intact');
entity.unload();console.log('PASS music relay validation, source isolation, byte/rate limits, opt-in publishing and handshake');
