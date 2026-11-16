const assert=require('node:assert/strict');
const {performance}=require('node:perf_hooks');
const Features=require('../synology/music-features.js');
const rate=44100, size=4096;
function tone(hz,amplitude=0.15){return Float32Array.from({length:size},(_,i)=>amplitude*Math.sin(2*Math.PI*hz*i/rate));}
function spectrum(hz,db=-20){const b=new Float32Array(size/2).fill(-Infinity);b[Math.round(hz*size/rate)]=db;return b;}
function finite(value){if(typeof value==='number')assert(Number.isFinite(value));else if(value&&typeof value==='object')Object.values(value).forEach(finite);}
const quiet=new Features(rate,size);
for(let i=0;i<40;i++){
  const f=quiet.update(new Float32Array(size),new Float32Array(size/2).fill(-Infinity),i*.05);
  finite(f);assert.equal(f.silent,true);assert.equal(f.beat,false);assert.equal(f.bpm,null);assert.equal(f.pitchHz,null);
  assert.equal(f.bands.reduce((a,b)=>a+b),0);
}
for(const [hz,band]of[[80,'bass'],[440,'mid'],[8000,'treble']]){
  const f=new Features(rate,size).update(tone(hz),spectrum(hz),0);
  assert(f[band]>.99);assert(Math.abs(f.centroid-hz)<12);assert.equal(f.beat,false,'No startup beat');
}
const steady=new Features(rate,size);let steadyBeats=0;
for(let i=0;i<120;i++)steadyBeats+=steady.update(tone(440),spectrum(440),i*.05).beat;
assert.equal(steadyBeats,0,'Sustained tones are not repeated beats');
const pitch=steady.update(tone(440),spectrum(440),6.05);
assert(Math.abs(pitch.pitchHz-440)<3);assert(pitch.pitchConfidence>.9);assert(pitch.chroma[9]>.99);
// Deterministic regular bass attacks, no actual music or network dependency.
const pulse=new Features(rate,size);let final,beats=0;const costs=[];
for(let i=0;i<360;i++){
  const hit=i%10===0, start=performance.now();
  final=pulse.update(tone(80,hit?.3:.03),spectrum(80,hit?-12:-45),i*.05);
  costs.push(performance.now()-start);if(final.beat)beats++;finite(final);
}
assert(beats>=30&&beats<=36,`Detected ${beats} beats`);
assert(Math.abs(final.bpm-120)<=2,JSON.stringify(final));assert(final.tempoConfidence>.35);
const discontinuity=pulse.update(tone(80),spectrum(80),30);
assert.equal(discontinuity.bpm,null);assert.equal(discontinuity.beat,false);
assert(discontinuity.beatId>=final.beatId,'Beat IDs never restart on a gap');
for(const sampleRate of [44100,48000])for(const hz of [70,440,980,1000,12440]){
  const w=Float32Array.from({length:size},(_,i)=>.15*Math.sin(2*Math.PI*hz*i/sampleRate));
  const b=new Float32Array(size/2).fill(-Infinity);b[Math.round(hz*size/sampleRate)]=-20;
  const f=new Features(sampleRate,size).update(w,b,0);
  if(hz>1000)assert.equal(f.pitchHz,null,'High-only tone cannot alias into a pitch');
  else assert(Math.abs(f.pitchHz-hz)<3,`${sampleRate}Hz: ${hz} -> ${f.pitchHz}`);
}
for(const bpm of [70,90,120,150,180]){
  const detector=new Features(rate,size);let f;
  for(let i=0;i<400;i++){
    const hit=(i*.05)%(60/bpm)<.08;
    f=detector.update(tone(80,hit?.3:.03),spectrum(80,hit?-12:-45),i*.05);
  }
  assert(f.bpm!==null&&Math.abs(f.bpm-bpm)<=3,`${bpm} BPM -> ${f.bpm}`);
}
const sparse=new Features(rate,size);
for(let i=0;i<220;i++){
  const hit=i===20||i===30;
  const f=sparse.update(tone(80,hit?.3:.03),spectrum(80,hit?-12:-45),i*.05);
  assert.equal(f.bpm,null,'Two isolated attacks do not establish tempo');
}
// Random full-spectrum / clipped samples: finite and bounded summaries.
let seed=123;function random(){seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;}
const noisy=new Features(48000,size);
for(let i=0;i<80;i++){
  const w=Float32Array.from({length:size},()=>random()*2-1), b=Float32Array.from({length:size/2},()=>-100+random()*80);
  const f=noisy.update(w,b,i*.05);finite(f);assert(f.energy>=0&&f.energy<=1);assert(f.flatness>=0&&f.flatness<=1);
  assert(Math.abs(f.bands.reduce((a,b)=>a+b)-1)<.006);
}
costs.sort((a,b)=>a-b);
console.log(JSON.stringify({result:'PASS',beats,bpm:final.bpm,tempoConfidence:final.tempoConfidence,
  pitchHz:pitch.pitchHz,p95Ms:costs[Math.floor(costs.length*.95)],maxMs:costs.at(-1)},null,2));
