import assert from 'node:assert/strict';
import { mkdtemp } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { chromium } from 'playwright';

// Real UI regression run. All state is isolated in a temporary save directory.
const artifacts = await mkdtemp('/tmp/space-crew-browser-regression-');
const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith('SPACE_CREW_')));
const server = spawn('.venv/bin/python', ['-m', 'uvicorn', 'space_sim_crew.api:app', '--host', '127.0.0.1', '--port', '8013'], {env: {...env, PYTHONPATH: 'server', SPACE_CREW_SAVES: artifacts}});
let serverLog = '';
server.stderr.on('data', data => { serverLog += data; });
const stopped = once(server, 'exit');
let browser;
let page;
try {
  for (let attempt = 0; attempt < 50; attempt++) {
    try { if ((await fetch('http://127.0.0.1:8013/api/v1/health')).ok) break; } catch {}
    if (server.exitCode !== null) throw new Error(serverLog);
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  browser = await chromium.launch({channel:'chrome', headless:true});
  page = await browser.newPage({viewport:{width:1440,height:1000}});
  page.setDefaultTimeout(8000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:8013');
  await page.getByLabel('Universe name').fill('Browser regression');
  await page.getByLabel('Seed (optional)').fill('55');
  await page.getByRole('button', {name:'Create and host'}).click();
  await page.getByRole('button', {name:'Join expedition'}).click();
  await page.getByRole('navigation', {name:'Station shortcuts'}).getByRole('link', {name:'Communications', exact:true}).click();
  assert.equal(await page.getByLabel('Transmit frequency · MHz', {exact:true}).count(), 1);
  await page.getByLabel('Transmit frequency · MHz', {exact:true}).fill('1166.679');
  await page.getByLabel('Plain-language reply').fill('We are peaceful explorers conducting a scientific survey.');
  await page.getByRole('button', {name:'Transmit and wait for response'}).click();
  await page.getByText('Respond in Communications or accept an accord in Command', {exact:true}).waitFor();
  assert.equal(await page.getByRole('button', {name:'Identify your vessel', exact:true}).count(), 0);
  console.log('PASS: single transmitter, station navigation, contact objective follows exchange.');

  const cooling = page.getByRole('slider', {name:'Cooling', exact:true});
  const propulsion = page.getByRole('slider', {name:'Propulsion', exact:true});
  await propulsion.press('Home');
  for(let i=0;i<10;i++) await propulsion.press('ArrowRight');
  await cooling.press('Home');
  for(let i=0;i<30;i++) await cooling.press('ArrowRight');
  await page.getByRole('button', {name:/Route power/}).click();
  await page.waitForTimeout(500);
  assert.equal(await cooling.inputValue(), '0.3');
  await page.getByLabel('Scan purpose').selectOption({label:'Vessel Systems and Weapons Scan · 100%'});
  await page.getByRole('button', {name:'Run Vessel Systems and Weapons Scan', exact:true}).click();
  await page.getByRole('button', {name:'20×', exact:true}).click();
  await page.getByText('SURVEY COMPLETE', {exact:true}).waitFor();
  await page.getByRole('button', {name:'1×', exact:true}).click();
  await page.getByRole('button', {name:'Vector 1, 0', exact:true}).click();
  await page.getByText('Quiet Survey Opportunity', {exact:true}).first().waitFor({timeout:18000});
  assert.equal(await page.getByText('SURVEY COMPLETE', {exact:true}).count(), 0);
  assert.equal(await page.getByRole('button', {name:'Record conclusion', exact:true}).count(), 0);
  console.log('PASS: accessible power controls persist; warp clears previous scan evidence.');

  const channel = page.getByLabel('Conversation channel');
  await channel.selectOption({label:'Remote · Independent Survey Vessel'});
  await page.getByLabel('Transmit frequency · MHz', {exact:true}).fill('1166.679');
  await page.getByLabel('Plain-language reply').fill('We arrived safely in the next system.');
  await page.getByRole('button', {name:'Transmit and wait for response'}).click();
  await page.getByText('Your remote message is received.', {exact:false}).first().waitFor();
  console.log('PASS: remote follow-up can receive a typed reply and return a response.');

  await page.getByRole('button', {name:'Run Composition and Temperature Scan', exact:true}).click();
  await page.getByRole('button', {name:'20×', exact:true}).click();
  await page.getByRole('button', {name:'Record conclusion', exact:true}).waitFor();
  await page.getByRole('button', {name:'1×', exact:true}).click();
  assert.equal(await page.getByRole('button', {name:'Record conclusion', exact:true}).isDisabled(), true);
  await page.locator('#activities input[type=checkbox]').first().check();
  await page.getByLabel('Evidence-backed conclusion').fill('The measured material signatures support further study; origin remains uncertain.');
  await page.getByRole('button', {name:'Record conclusion', exact:true}).click();
  await page.getByRole('button', {name:'Archive privately', exact:true}).click();
  await page.getByText('No unresolved threads', {exact:true}).waitFor();
  await page.reload();
  await page.getByText('No unresolved threads', {exact:true}).waitFor();
  await page.screenshot({path:`${artifacts}/completed.png`, fullPage:true});
  assert.deepEqual(errors, []);
  console.log('PASS: evidence-backed conclusion, finite consequence, reload persistence; no page errors.');
  console.log(`Artifacts and disposable save: ${artifacts}`);
} catch(error) {
  if(page) await page.screenshot({path:`${artifacts}/failure.png`, fullPage:true}).catch(()=>{});
  console.error(`Failure evidence: ${artifacts}`);
  throw error;
} finally {
  await browser?.close();
  server.kill('SIGTERM');
  await stopped;
}
