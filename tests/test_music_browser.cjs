// Real local Edge/Web Audio. Synthetic stereo WAV only; never contacts the NAS.
const assert=require('node:assert/strict'),fs=require('node:fs'),http=require('node:http'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../synology/cache/reconnect-test/node_modules/playwright-core');
const root=path.resolve(__dirname,'../synology'),rate=44100,seconds=20;
const wav=Buffer.alloc(44+rate*seconds*4);
wav.write('RIFF');wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);
wav.writeUInt16LE(1,20);wav.writeUInt16LE(2,22);wav.writeUInt32LE(rate,24);wav.writeUInt32LE(rate*4,28);
wav.writeUInt16LE(4,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(wav.length-44,40);
for(let i=0;i<rate*seconds;i++){
  const t=i/rate,hit=t%0.5<0.09;
  const value=t<2.5?.18*Math.sin(2*Math.PI*440*t):(hit?.3:.02)*Math.sin(2*Math.PI*80*t)+.02*Math.sin(2*Math.PI*880*t);
  wav.writeInt16LE(Math.round(value*32767),44+i*4);
  wav.writeInt16LE(Math.round(value*(t>7?.5:1)*32767),46+i*4);
}
let streamRequests=0,browser;
const server=http.createServer((request,response)=>{
  const url=new URL(request.url,'http://localhost');
  if(url.pathname==='/stream.mp3'){streamRequests++;response.writeHead(200,{'Content-Type':'audio/wav'});response.end(wav);return;}
  if(url.pathname==='/api/station'){response.writeHead(200,{'Content-Type':'application/json'});response.end(JSON.stringify({version:1,current:{id:123,title:'Local test',artist:'Synthetic'}}));return;}
  if(url.pathname==='/dr-screen'){response.writeHead(200,{'Content-Type':'text/html'});response.end(fs.readFileSync(path.join(root,'dr-screen.html'),'utf8').replace('<!-- SHUFFLIZER_CONTROLS -->',''));return;}
  if(['/dr-screen.js','/music-features.js','/music-telemetry.js'].includes(url.pathname)){
    response.writeHead(200,{'Content-Type':'text/javascript'});response.end(fs.readFileSync(path.join(root,url.pathname.slice(1))));return;
  }
  response.writeHead(200,{'Content-Type':'text/html'});response.end('<canvas></canvas>');
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  browser=await chromium.launch({executablePath:process.env.EDGE_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--autoplay-policy=no-user-gesture-required']});
  const page=await browser.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>{
    window.testMusic={packets:[],sources:0};
    const original=AudioContext.prototype.createMediaElementSource;
    AudioContext.prototype.createMediaElementSource=function(...args){window.testMusic.sources++;return original.apply(this,args);};
    window.EventBridge={scriptEventReceived:{connect(f){window.testReceive=f;f('{"volume":0}');}},emitWebEvent(raw){
      const p=JSON.parse(raw);if(p.type==='shufflizer.music'){window.testMusic.packets.push(p);if(window.testMusic.packets.length>400)window.testMusic.packets.shift();}
    }};
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/dr-screen`,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>testMusic.packets.some(p=>p.f.pitchHz>435&&p.f.pitchHz<445&&p.f.stereo&&p.f.stereo.width<.01),null,{timeout:8000});
  const initial=await page.evaluate(()=>({gain:gain.gain.value,packet:ShufflizerMusic.last}));
  assert.equal(initial.gain,0);assert(initial.packet.f.rms>.05,'Pre-volume analysis survives gain=0');
  await page.waitForFunction(()=>player.currentTime>10&&ShufflizerMusic.last.f.bpm>=118&&ShufflizerMusic.last.f.bpm<=122,null,{timeout:18000});
  const active=await page.evaluate(()=>({stats:ShufflizerMusic.stats,last:ShufflizerMusic.last,packets:testMusic.packets,sources:testMusic.sources}));
  assert.equal(streamRequests,1);assert.equal(active.sources,1);assert.equal(active.last.stationTrackId,'123');
  assert(active.last.f.stereo.balance<-.2&&active.last.f.stereo.balance>-.5);
  assert(active.packets.every(p=>Buffer.byteLength(JSON.stringify(p))<=1080));
  assert(active.stats.analysisP95Ms<25,JSON.stringify(active.stats));
  assert.equal(active.stats.skipped,0,'No packet budget drops');
  const elapsed=active.packets.at(-1).wall-active.packets[0].wall;
  const measuredHz=(active.packets.length-1)*1000/elapsed;assert(measuredHz<=21&&measuredHz>=12);
  await page.evaluate(()=>context.suspend());
  await page.waitForFunction(()=>ShufflizerMusic.last.state==='suspended',null,{timeout:2500});
  const suspended=await page.evaluate(()=>ShufflizerMusic.last);assert.equal(suspended.f.rms,0);assert.equal(suspended.f.bpm,null);
  await page.evaluate(()=>{window.testReceive('{"volume":75}');context.resume();});
  await page.waitForFunction(()=>ShufflizerMusic.last.state==='playing'&&ShufflizerMusic.last.f.rms>.005);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({result:'PASS',singleStream:streamRequests,singleSource:active.sources,measuredHz,
    maxPacketBytes:Math.max(...active.packets.map(p=>Buffer.byteLength(JSON.stringify(p)))),stats:active.stats,
    bpm:active.last.f.bpm,stereo:active.last.f.stereo,mutedGainAnalysis:true,suspendResume:true},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close();server.close();server.closeAllConnections();
});
