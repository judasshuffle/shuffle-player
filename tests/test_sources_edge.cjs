// Real headless Edge against the isolated NAS preview. No production controls.
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {chromium} = require('../synology/cache/reconnect-test/node_modules/playwright-core');
const base = 'http://192.168.68.81:8095';
let browser;
const errors = [];
async function signal(page, label) {
  await page.waitForFunction(() => {
    const graph = window.playerAudio;
    if (!graph || graph.audioCtx.state !== 'running') return false;
    const data = new Float32Array(graph.analyser.fftSize);
    graph.analyser.getFloatTimeDomainData(data);
    return Math.sqrt(data.reduce((sum, value) => sum + value * value, 0) / data.length) > 0.0005;
  }, null, {timeout:30000});
  const result = await page.evaluate(() => {
    const graph = window.playerAudio, data = new Float32Array(graph.analyser.fftSize);
    graph.analyser.getFloatTimeDomainData(data);
    return {rms:Math.sqrt(data.reduce((sum, value) => sum + value * value, 0) / data.length),
            source:document.querySelector('audio').currentSrc, state:graph.audioCtx.state};
  });
  console.log(label, JSON.stringify(result));
  const frame = page.frames().find(frame => frame.url().includes('/visualizer/index.html'));
  assert(frame, 'Visualizer frame loaded');
  await frame.waitForSelector('canvas');
}
(async () => {
  // Key remains in process/browser memory and is never printed or written to disk.
  const key = execFileSync('C:/Windows/System32/OpenSSH/ssh.exe', ['-o','BatchMode=yes','Dan@GreatATuin',
    'cat /volume1/docker/shuffle-player/secrets/owner-key'], {encoding:'utf8',windowsHide:true}).trim();
  browser = await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    headless:true,args:['--autoplay-policy=no-user-gesture-required']});
  const context = await browser.newContext();
  const main = await context.newPage();
  main.on('pageerror', error => errors.push(error.message));
  await main.goto(base, {waitUntil:'domcontentloaded'});
  await main.locator('#ownerKey').fill(key);
  await main.locator('#rememberOwner').check();
  await main.locator('#ownerLogin button').first().click();
  await main.locator('#ownerStatus').filter({hasText:'Remembered on this browser'}).waitFor();
  await main.waitForFunction(() => !document.querySelector('#sourceSelect').disabled);
  await main.locator('#sourceSelect').selectOption('library');
  await main.waitForFunction(() => !document.querySelector('#next').disabled);
  await main.locator('#quality').selectOption('mp3');
  await main.locator('#listenHere').check();
  const screen = await context.newPage();
  screen.on('pageerror', error => errors.push(error.message));
  await screen.addInitScript(() => {
    window.testPackets = [];
    window.EventBridge = {scriptEventReceived:{connect(){}}, emitWebEvent(raw){
      const packet = JSON.parse(raw);
      if (packet.type === 'shufflizer.music') { window.testPackets.push(packet); if (window.testPackets.length > 300) window.testPackets.shift(); }
    }};
  });
  await screen.goto(base + '/dr-screen', {waitUntil:'domcontentloaded'});
  await signal(main, 'library browser');
  await signal(screen, 'library screen');
  const saved = await main.evaluate(async () => (await (await fetch('/api/sources')).json()).stations);
  assert(saved.length > 0, 'A saved tested external source is required');
  const ident = saved.at(-1).id;
  await main.locator('#sourceSelect').selectOption(ident);
  await main.waitForFunction(() => document.querySelector('audio').currentSrc.endsWith('/stream.mp3'));
  await signal(main, 'external browser');
  await screen.waitForFunction(id => window.ShufflizerMusic?.last?.stationTrackId === id && window.ShufflizerMusic.last.f.rms > .0005, ident);
  await signal(screen, 'external screen');
  assert(await screen.evaluate(() => window.testPackets.some(packet => packet.f.rms > .0005 && packet.state === 'playing')), 'External music-analysis packets reach EventBridge');
  await main.locator('#sourceSelect').selectOption('library');
  await main.waitForFunction(() => document.querySelector('audio').currentSrc.includes('/media/'));
  await signal(main, 'returned library browser');
  await signal(screen, 'returned library screen');
  await main.locator('#q').fill('Shuffle Preview Sample');
  await main.locator('#search button').click();
  await main.waitForFunction(() => document.querySelector('#results').textContent.includes('Preview tone 1'));
  const initial = await main.locator('#title').textContent();
  await main.locator('#next').click();
  await main.waitForFunction(previous => document.querySelector('#title').textContent !== previous, initial);
  await main.locator('#shuffleAll').click();
  await main.waitForFunction(() => !document.querySelector('#shuffleAll').disabled);
  await main.goto(base + '/sources', {waitUntil:'domcontentloaded'});
  await main.waitForFunction(() => !document.querySelector('#scanLibrary').disabled);
  assert(await main.locator('#ownerStatus').textContent().then(text => text.includes('Remembered')), 'Navigation keeps unlock');
  await main.reload({waitUntil:'domcontentloaded'});
  await main.waitForFunction(() => !document.querySelector('#scanLibrary').disabled);
  assert.deepEqual(errors, []);
  console.log('PASS Edge: two audio graphs/visualizers, radio and library switches, lighting EventBridge analysis, search/skip/shuffle, remembered owner navigation/refresh.');
})().catch(error => {console.error(error);process.exitCode=1;}).finally(async () => {if (browser) await browser.close();});
