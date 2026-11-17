// Read-only acceptance check of the promoted live station. Never resumes it.
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {chromium} = require('../synology/cache/reconnect-test/node_modules/playwright-core');
const base = 'http://192.168.68.81:8094';
let browser;
(async () => {
  const key = execFileSync('C:/Windows/System32/OpenSSH/ssh.exe', ['-o','BatchMode=yes','Dan@GreatATuin',
    'cat /volume1/docker/shuffle-player/secrets/owner-key'], {encoding:'utf8',windowsHide:true}).trim();
  browser = await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    headless:true,args:['--autoplay-policy=no-user-gesture-required']});
  const context = await browser.newContext(), page = await context.newPage(), errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const before = await (await context.request.get(base + '/api/station')).json();
  assert.equal(before.playing, false);
  await page.goto(base, {waitUntil:'domcontentloaded'});
  await page.locator('#ownerKey').fill(key);
  await page.locator('#rememberOwner').check();
  await page.locator('#ownerLogin button').first().click();
  await page.waitForFunction(() => !document.querySelector('#toggle').disabled);
  assert.equal(await page.locator('#toggle').textContent(), 'Play station');
  await page.goto(base + '/sources', {waitUntil:'domcontentloaded'});
  await page.waitForFunction(() => !document.querySelector('#saveConnection').disabled && document.querySelector('#publicPlayerBase').value.length > 0);
  const result = await page.evaluate(async () => ({
    sources: await (await fetch('/api/sources')).json(),
    connection: await (await fetch('/api/listening')).json(),
    sample: await (await fetch('/api/search?q=Shuffle%20Preview%20Sample')).json()
  }));
  assert.equal(result.sources.active, 'library');
  assert(result.sources.stations.some(station => station.name === 'Dismuke'));
  assert.equal(result.sample.tracks.length, 2);
  assert.equal(new URL(result.connection.screen_url).port, '8001');
  await page.locator('summary').filter({hasText:'Show me what goes in the router'}).click();
  assert.equal(await page.locator('#routerPort').textContent(), '8001');
  assert.equal((await context.request.get('http://192.168.68.81:8001/api/listening')).status(), 403);
  const screen = await context.newPage();
  screen.on('pageerror', error => errors.push(error.message));
  const publicScreen = result.connection.screen_url + '?music-feed=1794856696594';
  const response = await screen.goto(publicScreen, {waitUntil:'domcontentloaded',timeout:30000});
  assert.equal(response.status(), 200, 'Existing public screen URL still serves the screen');
  await screen.waitForFunction(() => document.querySelector('audio').currentTime > .2, null, {timeout:30000});
  const state = await (await context.request.get(base + '/api/station')).json();
  assert.equal(state.playing, false, 'Acceptance checks never resumed the deliberately paused station');
  assert.equal(state.source, 'library');
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({result:'PASS',liveSources:true,DismukeSaved:true,sampleSearch:2,ownerKeyWorks:true,
    listenerPort:8001,existingPublicScreen:true,paused:true,publicSettingsHidden:true}));
})().catch(error => {console.error(error);process.exitCode=1;}).finally(async () => {if(browser) await browser.close();});
