// One local MP3 interruption in real headless Edge. Never contacts the NAS.
// Requires ffmpeg and playwright-core (or PLAYWRIGHT_MODULE pointing to it).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || '../synology/cache/reconnect-test/node_modules/playwright-core');
const root = path.resolve(__dirname, '..');
const keepMuted = process.env.RECONNECT_MUTED !== '0';
let requests = 0, maxStreams = 0, offlineUntil = 0, navigations = 0;
const streams = new Set(), events = [];
let encoder;
function encode() {
if (encoder) return;
encoder = spawn('ffmpeg', ['-v','error','-re','-f','lavfi','-i',
  "aevalsrc='0.12*sin(2*PI*if(lt(t,4),440,660)*t)':s=44100",
  '-c:a','libmp3lame','-b:a','128k','-f','mp3','pipe:1'], {windowsHide:true});
encoder.stderr.on('data', data => process.stderr.write(data));
encoder.stdout.on('data', chunk => {for(const response of streams) response.write(chunk);});
}
const server = http.createServer((request,response) => {
  const url = new URL(request.url,'http://localhost');
  if(url.pathname === '/stream.mp3') {
    requests++;events.push({request:requests,time:Date.now(),offline:Date.now()<offlineUntil});
    if(Date.now()<offlineUntil) {response.writeHead(503);response.end();return;}
    response.writeHead(200,{'Content-Type':'audio/mpeg','Cache-Control':'no-store'});
    streams.add(response);maxStreams=Math.max(maxStreams,streams.size);
    encode();
    response.on('close',()=>streams.delete(response));return;
  }
  if(url.pathname === '/dr-screen') {
    response.writeHead(200,{'Content-Type':'text/html'});
    response.end(fs.readFileSync(path.join(root,'synology/dr-screen.html'),'utf8').replace('<!-- SHUFFLIZER_CONTROLS -->',''));return;
  }
  if(url.pathname === '/dr-screen.js') {
    response.writeHead(200,{'Content-Type':'text/javascript'});
    response.end(fs.readFileSync(path.join(root,'synology/dr-screen.js')));return;
  }
  // Rendering isn't under test; the real screen page and audio graph are.
  response.writeHead(200,{'Content-Type':'text/html'});response.end('<canvas></canvas>');
});
let browser;
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  browser=await chromium.launch({executablePath:process.env.EDGE_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    headless:true,args:['--autoplay-policy=no-user-gesture-required']});
  const page=await browser.newPage();
  page.setDefaultTimeout(20000);
  page.on('framenavigated',frame=>{if(frame===page.mainFrame())navigations++;});
  await page.addInitScript(()=>{
    window.testStats={sources:0,playing:0};
    const original=AudioContext.prototype.createMediaElementSource;
    AudioContext.prototype.createMediaElementSource=function(...args){window.testStats.sources++;return original.apply(this,args);};
    window.EventBridge={scriptEventReceived:{connect(callback){callback('{"volume":37}');}},emitWebEvent(){}};
    document.addEventListener('playing',()=>window.testStats.playing++,true);
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/dr-screen`,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!document.querySelector('audio').paused && window.playerAudio.audioCtx.state==='running');
  const sample = () => page.evaluate(()=>{
    const analyser=window.playerAudio.analyser, spectrum=new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(spectrum);
    let peak=0;for(let i=1;i<spectrum.length;i++)if(spectrum[i]>spectrum[peak])peak=i;
    const wave=new Uint8Array(analyser.fftSize);analyser.getByteTimeDomainData(wave);
    const rms=Math.sqrt(wave.reduce((sum,n)=>sum+((n-128)/128)**2,0)/wave.length);
    return {frequency:peak*window.playerAudio.audioCtx.sampleRate/analyser.fftSize,rms};
  });
  await page.waitForFunction(()=>document.querySelector('audio').currentTime>0.4);
  const before=await sample();assert(Math.abs(before.frequency-440)<90,JSON.stringify(before));assert(before.rms>0.02);
  await page.waitForFunction(()=>document.querySelector('audio').currentTime>4.5);
  const changed=await sample();assert(Math.abs(changed.frequency-660)<90,JSON.stringify(changed));
  assert.equal(requests,1,'Normal programme change keeps the MP3 connection');
  await page.evaluate(muted=>{player.volume=0.8;player.muted=muted;window.playingBeforeDrop=window.testStats.playing;},keepMuted);
  const droppedAt=Date.now();offlineUntil=droppedAt+3500;
  for(const response of [...streams])response.destroy(); // The only interruption.
  await page.waitForFunction(()=>window.testStats.playing>window.playingBeforeDrop,{},{timeout:25000});
  const preserved=await page.evaluate(()=>({muted:player.muted,nativeVolume:player.volume,gain:gain.gain.value,
    elements:document.querySelectorAll('audio').length,sources:window.testStats.sources,
    recoveries:window.testStats.playing-window.playingBeforeDrop}));
  assert.equal(preserved.muted,keepMuted);assert.equal(preserved.nativeVolume,0.8);
  assert(Math.abs(preserved.gain-0.37)<0.00001);assert.equal(preserved.elements,1);assert.equal(preserved.sources,1);
  assert.equal(preserved.recoveries,1);assert.equal(maxStreams,1);assert.equal(navigations,1);
  // Verify the preserved mute, then restore the visitor's unmuted state and hear
  // measurable PCM return through the existing post-analysis volume gain.
  await page.waitForTimeout(100);
  if(keepMuted) assert((await sample()).rms<0.002,'Mute remains effective after reconnection');
  await page.evaluate(wasMuted=>{
    if(wasMuted) player.muted=false;
    window.outputProbe=context.createAnalyser();
    gain.connect(window.outputProbe);
    window.probeReadyAt=performance.now()+100;
  },keepMuted);
  await page.waitForFunction(()=>{
    const data=new Float32Array(window.outputProbe.fftSize);window.outputProbe.getFloatTimeDomainData(data);
    // A new analyser initially contains zero-filled history. Let its complete
    // window fill before comparing input/output RMS rather than sampling half
    // a window immediately when the first PCM arrives.
    return performance.now()>=window.probeReadyAt && Math.sqrt(data.reduce((sum,n)=>sum+n*n,0)/data.length)>0.005;
  });
  const output=await page.evaluate(()=>{
    function rms(node){const a=new Float32Array(node.fftSize);node.getFloatTimeDomainData(a);return Math.sqrt(a.reduce((s,n)=>s+n*n,0)/a.length);}
    return {input:rms(analyser),output:rms(window.outputProbe),recoveries:window.testStats.playing-window.playingBeforeDrop};
  });
  assert(Math.abs(output.output/output.input-0.37)<0.04,JSON.stringify(output));
  assert.equal(output.recoveries,1);
  const retries=events.slice(1).map(event=>({afterDropMs:event.time-droppedAt,offline:event.offline}));
  assert(retries.some(event=>event.offline),'Outage exercises increasing retries');
  console.log(JSON.stringify({result:'PASS',normalTrackChange:'same connection',localInterruptions:1,retries,
    preserved,outputGainRatio:output.output/output.input,pageNavigations:navigations,maxConcurrentStreams:maxStreams},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close();for(const response of streams)response.destroy();server.close();if(encoder)encoder.kill();
});
