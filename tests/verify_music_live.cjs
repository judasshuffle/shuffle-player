// Read-only public listener probe. Adds one temporary listener; never sends DJ
// commands, changes a queue, changes visitor settings or edits world entities.
const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../synology/cache/reconnect-test/node_modules/playwright-core');
const base='http://shuffle.tplinkdns.com:8001';let browser;
(async()=>{
  browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--autoplay-policy=no-user-gesture-required']});
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>{
    window.musicProbe=[];
    window.EventBridge={scriptEventReceived:{connect(f){f('{"volume":0}');}},emitWebEvent(raw){
      const p=JSON.parse(raw);if(p.type==='shufflizer.music'){musicProbe.push(p);if(musicProbe.length>400)musicProbe.shift();}
    }};
  });
  await page.goto(base+'/dr-screen',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>musicProbe.filter(p=>p.state==='playing'&&p.f.rms>.003).length>=120,null,{timeout:30000});
  const result=await page.evaluate(()=>({packets:musicProbe,stats:ShufflizerMusic.stats,error:ShufflizerMusic.error||null,
    audioElements:document.querySelectorAll('audio').length,gain:gain.gain.value}));
  assert.equal(result.error,null);assert.equal(result.audioElements,1);assert.equal(result.gain,0);
  assert.equal(result.stats.skipped,0);assert(result.packets.some(p=>p.f.beatId>0));
  assert(result.packets.every(p=>Buffer.byteLength(JSON.stringify(p))<=1080));
  const active=result.packets.filter(p=>p.state==='playing');
  const relayBytes=Math.max(...active.map(p=>Buffer.byteLength(JSON.stringify({...p,
    sourceEntity:'{00000000-0000-0000-0000-000000000001}',sourceSession:'{00000000-0000-0000-0000-000000000002}'}))));
  assert(relayBytes<=1200);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({result:'PASS',url:base+'/dr-screen',frames:active.length,
    rmsRange:[Math.min(...active.map(p=>p.f.rms)),Math.max(...active.map(p=>p.f.rms))],
    detectedAttacks:active.at(-1).f.beatId,relayMaxBytes:relayBytes,stats:result.stats,
    source:'real live station, headless Edge; not embedded DarkRide',worldEdits:0},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();});
