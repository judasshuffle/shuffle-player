// Real Python station, FFmpeg EOF, and the existing screen in local Edge.
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {chromium} = require('../synology/cache/reconnect-test/node_modules/playwright-core');
const rolling = process.argv.includes('--rolling');
const fixture = spawn('python', ['-B', 'tests/station_browser_fixture.py', ...(rolling ? ['--rolling'] : [])], {windowsHide:true});
fixture.stderr.on('data', data=>process.stderr.write(data));
let browser;
(async()=>{
  const port = await new Promise((resolve,reject)=>{fixture.stdout.once('data',data=>resolve(Number(data.toString().trim())));fixture.once('exit',code=>reject(Error('fixture exit '+code)));});
  browser = await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--autoplay-policy=no-user-gesture-required']});
  const page = await browser.newPage();
  let requests=0,navigations=0;
  page.on('request',r=>{if(new URL(r.url()).pathname==='/stream.mp3')requests++;});
  page.on('framenavigated',f=>{if(f===page.mainFrame())navigations++;});
  await page.goto(`http://127.0.0.1:${port}/dr-screen`,{waitUntil:'domcontentloaded'});
  if(rolling) {
    let state, deadline=Date.now()+30000;
    do {
      state=await (await fetch(`http://127.0.0.1:${port}/test-state`)).json();
      if(state.completed>=6) break;
      await page.waitForTimeout(250);
    } while(Date.now()<deadline);
    assert(state.completed>=6,JSON.stringify(state));
    assert.equal(state.playing,true);
    await page.waitForFunction(()=>{
      const a=playerAudio.analyser,data=new Float32Array(a.fftSize);a.getFloatTimeDomainData(data);
      return Math.sqrt(data.reduce((s,n)=>s+n*n,0)/data.length)>0.01;
    });
    assert(state.completed>=6);assert.equal(requests,1);assert.equal(navigations,1);
    console.log(JSON.stringify({result:'PASS',rolling:true,completed:state.completed,streamRequests:requests,navigations}));
    return;
  }
  const audibleFrequency = frequency => page.waitForFunction(frequency=>{
    const a=window.playerAudio?.analyser;if(!a)return false;
    const bins=new Uint8Array(a.frequencyBinCount);a.getByteFrequencyData(bins);
    let peak=0;for(let i=1;i<bins.length;i++)if(bins[i]>bins[peak])peak=i;
    return bins[peak]>80 && Math.abs(peak*playerAudio.audioCtx.sampleRate/a.fftSize-frequency)<70;
  },frequency,{timeout:20000});
  await audibleFrequency(440);
  await audibleFrequency(880);
  const state=await (await fetch(`http://127.0.0.1:${port}/test-state`)).json();
  assert.equal(state.current.id,2);assert.equal(state.playing,true);
  assert.equal(requests,1);assert.equal(navigations,1);
  await fetch(`http://127.0.0.1:${port}/test-toggle`);
  await page.waitForTimeout(1500);
  const paused=await (await fetch(`http://127.0.0.1:${port}/test-state`)).json();
  await page.waitForTimeout(1500);
  const still=await (await fetch(`http://127.0.0.1:${port}/test-state`)).json();
  assert.equal(still.playing,false);assert.equal(still.position,paused.position);
  assert.equal(requests,1);
  console.log(JSON.stringify({result:'PASS',naturalEOF:state,pausePreserved:true,streamRequests:requests,navigations}));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close();
  fixture.stdin.end('\n');
});
