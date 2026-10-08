// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
// Local fixture measurement only. Python owns the browser and context request guard.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import crypto from 'node:crypto';

const [toolRoot, port, origin, output, mode, view, guardLog, ownedProfile] = process.argv.slice(2);
if (!toolRoot || !/^\d+$/.test(port) || !['mobile', 'desktop'].includes(mode) ||
    !['fleet', 'readiness', 'estate'].includes(view) || !guardLog || !ownedProfile ||
    !/^http:\/\/127\.0\.0\.1:\d+$/.test(origin)) throw new Error('Invalid loopback measurement arguments');
const require = createRequire(path.join(toolRoot, 'package.json'));
const puppeteer = require('puppeteer-core');
const lh = await import(pathToFileURL(path.join(toolRoot, 'node_modules/lighthouse/core/index.js')));
const {Fetcher} = await import(pathToFileURL(path.join(toolRoot, 'node_modules/lighthouse/core/gather/fetcher.js')));
const protocolRequests = [];
const originalFetch = Fetcher.prototype.fetchResource;
Fetcher.prototype.fetchResource = async function(url, ...args) {
  const allowed = new URL(url).origin === origin;
  protocolRequests.push({url, action: allowed ? 'FORWARD_LOOPBACK' : 'ABORT', acknowledged: true});
  if (!allowed) return {content: null, status: null};
  return originalFetch.call(this, url, ...args);
};
const evidence = {
  source: 'LOCAL TEST FIXTURE; NOT PRODUCTION', mode, view, scores: null, protocolRequests,
  isolation_scope: 'Fixture browser context requests; service workers blocked; WebSockets closed; Lighthouse resource fetches allow loopback only. OS-wide egress is unmeasured.',
};
let browser, page;
const probes = ['https://example.invalid/szl-egress-probe', 'http://192.0.2.1/szl-egress-probe'];
function guardRows() {
  return fs.readFileSync(guardLog, 'utf8').trim().split('\n').filter(Boolean).map(row => JSON.parse(row));
}
async function verifyGuard(name) {
  const start = guardRows().length;
  await page.goto('about:blank');
  const results = await page.evaluate(async urls => Promise.all(urls.map(async url => {
    try { await fetch(url, {signal: AbortSignal.timeout(5000)}); return {url, resolved: true}; }
    catch { return {url, resolved: false}; }
  })), probes);
  let captured = [];
  for (let attempt = 0; attempt < 50; attempt++) {
    captured = guardRows().slice(start);
    if (probes.every(url => captured.some(r => r.url === url && r.action === 'ABORT' && r.acknowledged))) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (results.some(r => r.resolved) || captured.some(r => !r.acknowledged) ||
      probes.some(url => !captured.some(r => r.url === url && r.action === 'ABORT' && r.acknowledged)))
    throw new Error(`Browser request blocking failed: ${name}`);
  return {results, captured};
}
fs.mkdirSync(output, {recursive: true});
try {
  browser = await puppeteer.connect({browserURL: `http://127.0.0.1:${port}`, defaultViewport: null, protocolTimeout: 20000});
  const ownershipSession = await browser.target().createCDPSession();
  const command = await ownershipSession.send('Browser.getBrowserCommandLine');
  const profileArg = command.arguments.find(arg => arg.startsWith('--user-data-dir='));
  if (!profileArg || path.resolve(profileArg.slice('--user-data-dir='.length)).toLowerCase() !== path.resolve(ownedProfile).toLowerCase())
    throw new Error('Debugger is not bound to the owned browser profile');
  evidence.owned_profile_verified = true;
  await ownershipSession.detach();
  page = await browser.newPage();
  page.setDefaultTimeout(20000);
  page.setDefaultNavigationTimeout(20000);
  evidence.browser = await browser.version();
  evidence.lighthouse = JSON.parse(fs.readFileSync(path.join(toolRoot, 'node_modules/lighthouse/package.json'), 'utf8')).version;
  evidence.preflight = await verifyGuard('preflight');
  for (const url of probes) {
    const response = await Fetcher.prototype.fetchResource.call({}, url);
    if (response.content !== null || response.status !== null) throw new Error('Protocol resource guard failed');
  }
  console.log('Acknowledged browser and protocol guards passed preflight');
  await page.emulateMediaFeatures([{name: 'prefers-color-scheme', value: 'dark'}, {name: 'prefers-reduced-motion', value: 'reduce'}]);
  const config = mode === 'desktop' ? structuredClone(lh.desktopConfig) : {extends: 'lighthouse:default', settings: {}};
  config.settings = {...config.settings,
    onlyCategories: ['performance', 'accessibility', 'best-practices'],
    formFactor: mode,
    screenEmulation: {mobile: mode === 'mobile', width: mode === 'mobile' ? 390 : 1280,
      height: mode === 'mobile' ? 844 : 900, deviceScaleFactor: 1, disabled: false},
  };
  const result = await lh.default(`${origin}/console?view=${view}`, {logLevel: 'error'}, config, page);
  if (!result || result.lhr.runtimeError) throw new Error(JSON.stringify(result?.lhr.runtimeError || 'No Lighthouse result'));
  evidence.scores = Object.fromEntries(Object.entries(result.lhr.categories).map(([key, value]) => [key, value.score === null ? null : Math.round(value.score * 100)]));
  evidence.settings = result.lhr.configSettings;
  evidence.final_url = result.lhr.finalDisplayedUrl;
  if (new URL(evidence.final_url).searchParams.get('view') !== view) throw new Error(`View changed during audit: ${evidence.final_url}`);
  fs.writeFileSync(path.join(output, 'lighthouse.json'), JSON.stringify(result.lhr, null, 2));
  fs.writeFileSync(path.join(output, 'lighthouse.html'), lh.generateReport(result.lhr, 'html'));
  evidence.postflight = await verifyGuard('postflight');
  evidence.requests = guardRows();
  if (evidence.requests.some(r => !r.acknowledged ||
      (r.action === 'FORWARD_LOOPBACK' && (new URL(r.url).origin !== origin || r.method !== 'GET'))))
    throw new Error('Browser context guard invariant failed');
  evidence.compatibility_and_isolation_passed = true;
} catch (error) {
  evidence.compatibility_and_isolation_passed = false;
  evidence.error = String(error.stack || error);
  process.exitCode = 1;
} finally {
  evidence.requests = guardRows();
  evidence.guard_sha256 = crypto.createHash('sha256').update(fs.readFileSync(new URL(import.meta.url))).digest('hex');
  fs.writeFileSync(path.join(output, 'isolation.json'), JSON.stringify(evidence, null, 2));
  if (page) await page.close().catch(() => {});
  if (browser) await browser.disconnect();
  Fetcher.prototype.fetchResource = originalFetch;
  console.log(JSON.stringify({mode, view, scores: evidence.scores, passed: evidence.compatibility_and_isolation_passed, error: evidence.error}));
}
