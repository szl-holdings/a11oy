// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
// Hosted, local-only qualification of the actual generated Gradio package.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawn, execFileSync} from 'node:child_process';
import {readFile, writeFile, mkdir, mkdtemp, lstat} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const args = Object.fromEntries(process.argv.slice(2).reduce((rows, item, index, all) => {
  if (index % 2 === 0) rows.push([item, all[index + 1]]);
  return rows;
}, []));
assert(args['--module'] && args['--out'] && args['--package'], 'module, out and package required');
const root = process.cwd();
const sha = execFileSync('git', ['rev-parse', 'HEAD'], {encoding: 'utf8'}).trim();
assert.equal(sha, process.env.SOURCE_SHA, 'checkout must be exact candidate');
const pkg = path.resolve(args['--package']);
const outRoot = path.resolve(args['--out']);
await mkdir(outRoot, {recursive: true});
assert((await lstat(outRoot)).isDirectory(), 'output parent must not be a symlink');
const out = await mkdtemp(path.join(outRoot, 'bench-native-'));
const observations = {schema: 'szl.benchmark-frontend-observation/v1',
  classification: 'UNSIGNED_LOCAL_BROWSER_OBSERVATIONS', source_revision: sha,
  scope: 'Actual generated Gradio package with committed fixture output. Browser-context traffic is restricted to one local origin. No model calls, evaluator callbacks, publication or deployment.',
  checks: [], cases: [], files: {}, failures: [], denied_remote: [], denied_non_get: []};
const check = (name, ok, detail = null) => {
  observations.checks.push({name, passed: Boolean(ok), detail});
  if (!ok) observations.failures.push({name, detail});
};
const manifest = JSON.parse(await readFile(path.join(pkg, 'publication-manifest.json'), 'utf8'));
assert.equal(manifest.source_revision, sha);
const expectedFiles = ['LICENSE', 'README.md', 'app.py', 'bench.css', 'leaderboard.json',
  'native_presentation.py', 'publication.json', 'requirements.txt',
  'results/reference-conformance.json', 'szl/PROJECTION.json', 'szl/SOURCE.json',
  'szl/szl-icon-32.svg', 'szl/szl-orbit-holo.svg', 'szl/szl-tokens.css'].sort();
assert.deepEqual(manifest.files.map(f => f.path).sort(), expectedFiles);
for (const name of expectedFiles) {
  const data = await readFile(path.join(pkg, name));
  const hash = createHash('sha256').update(data).digest('hex');
  const row = manifest.files.find(f => f.path === name);
  assert.equal(hash, row.sha256); assert.equal(data.length, row.bytes);
  observations.files[name] = hash;
}
const env = Object.fromEntries(['PATH', 'HOME', 'TMPDIR', 'LANG', 'SYSTEMROOT'].filter(k => process.env[k]).map(k => [k, process.env[k]]));
Object.assign(env, {GRADIO_ANALYTICS_ENABLED: 'False', HF_HUB_OFFLINE: '1',
  HF_HUB_DISABLE_IMPLICIT_TOKEN: '1', GRADIO_SERVER_NAME: '127.0.0.1', GRADIO_SERVER_PORT: '7874',
  PYTHONUNBUFFERED: '1'});
const origin = 'http://127.0.0.1:7874';
const child = spawn('python', ['app.py'], {cwd: pkg, env, stdio: ['ignore', 'pipe', 'pipe']});
let log = '';
const appendLog = data => { if (log.length < 262144) log += data.toString().slice(0, 262144 - log.length); };
child.stdout.on('data', appendLog); child.stderr.on('data', appendLog);
const {chromium} = await import(pathToFileURL(path.resolve(args['--module'])).href);
let browser;
try {
  let ready = false;
  for (let attempt = 0; attempt < 120; attempt++) {
    if (child.exitCode !== null) throw new Error(`Gradio exited ${child.exitCode}: ${log.slice(-4000)}`);
    try { const response = await fetch(origin + '/config', {signal: AbortSignal.timeout(1000)});
      if (response.ok) { const config = await response.json();
        assert.equal(config.dependencies.length, 0, 'no executable callback registered');
        check('generated app has no callbacks', true); ready = true; break; }
    } catch (error) { if (error.code === 'ERR_ASSERTION') throw error; }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  assert(ready, `Gradio did not become ready: ${log.slice(-4000)}`);
  browser = await chromium.launch({headless: true});
  const variants = [
    {name: 'wide', width: 1440, height: 1000},
    {name: 'tablet', width: 768, height: 1024},
    {name: 'phone', width: 375, height: 812},
    {name: 'narrow', width: 320, height: 900},
    {name: 'dark-preference', width: 1280, height: 900, colorScheme: 'dark'},
    {name: 'reduced-motion', width: 375, height: 812, reducedMotion: 'reduce'},
    {name: 'forced-colors', width: 375, height: 812, forcedColors: 'active'},
  ];
  for (const variant of variants) {
    const {name, width, height, ...preferences} = variant;
    const context = await browser.newContext({viewport: {width, height}, ...preferences});
    await context.route('**/*', async route => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.origin !== origin) { observations.denied_remote.push(url.origin + url.pathname); return route.abort(); }
      if (!['GET', 'HEAD'].includes(request.method())) { observations.denied_non_get.push(request.method() + ' ' + url.pathname); return route.abort(); }
      return route.continue();
    });
    const page = await context.newPage();
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin, {waitUntil: 'networkidle', timeout: 30000});
    await page.locator('#bench-title').waitFor();
    check(`${name}: title`, await page.locator('h1').count() === 1);
    check(`${name}: zero eligible submissions`, (await page.locator('.gb-count').innerText()) === '0');
    check(`${name}: five original axes`, await page.locator('.gb-axes li').count() === 5);
    const text = await page.locator('.gb-page').innerText();
    check(`${name}: evidence boundary`, ['SAMPLE', 'COMPUTED', 'STRUCTURE_ONLY', 'false',
      'REFERENCE_ONLY_NO_MODEL_SUBMISSIONS', 'not a model ranking', 'not an independent attestation'].every(v => text.includes(v)));
    check(`${name}: no model control`, await page.locator('#bench-native input, #bench-native button, #bench-native textarea').count() === 0);
    const metrics = await page.evaluate(() => {
      const root = document.querySelector('.gb-page');
      const visible = el => { const r = el.getBoundingClientRect(); return r.width && r.height && getComputedStyle(el).visibility !== 'hidden'; };
      const violations = [];
      for (const element of root.querySelectorAll('*')) {
        if (!visible(element) || element.classList.contains('gb-skip') || element.classList.contains('gb-orbit')) continue;
        const rect = element.getBoundingClientRect();
        if (rect.left < -1 || rect.right > innerWidth + 1) violations.push({tag: element.tagName, class: element.className, left: rect.left, right: rect.right});
      }
      const targets = [...root.querySelectorAll('nav a, .gb-primary, .gb-links a, summary')].filter(visible).map(el => {
        const r = el.getBoundingClientRect(); return {text: el.textContent.trim(), width: r.width, height: r.height};
      });
      // Text-only roles over their actual opaque CSS grounds. Decorative imagery is excluded.
      const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1; const painter = canvas.getContext('2d', {willReadFrequently: true});
      function rgba(value) { painter.clearRect(0, 0, 1, 1); painter.fillStyle = value; painter.fillRect(0, 0, 1, 1); const n = [...painter.getImageData(0, 0, 1, 1).data]; return [...n.slice(0, 3), n[3] / 255]; }
      function luminance(rgb) { return rgb.slice(0, 3).map(v => { v /= 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }).reduce((s,v,i) => s + v * [.2126,.7152,.0722][i], 0); }
      const contrasts = [];
      for (const el of root.querySelectorAll('p,h1,h2,h3,dt,dd,a,summary,.gb-axis-index')) {
        if (!visible(el) || ![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) || el.classList.contains('gb-skip')) continue;
        const style = getComputedStyle(el), fg = rgba(style.color);
        let ancestor = el, bg = null;
        while (ancestor && !bg) { const c = rgba(getComputedStyle(ancestor).backgroundColor); if(c && c[3] === 1) bg = c; ancestor = ancestor.parentElement; }
        if (!fg || !bg) { contrasts.push({text: el.textContent.slice(0, 70), unsupported: true}); continue; }
        const a = luminance(fg), b = luminance(bg), ratio = (Math.max(a,b) + .05)/(Math.min(a,b) + .05);
        const large = parseFloat(style.fontSize) >= 24 || (parseFloat(style.fontSize) >= 18.66 && Number(style.fontWeight) >= 700);
        contrasts.push({text: el.textContent.slice(0,70), ratio, minimum: large ? 3 : 4.5});
      }
      return {width: innerWidth, scrollWidth: document.documentElement.scrollWidth, violations, targets, contrasts,
        font: getComputedStyle(root).fontFamily, mainBackground: getComputedStyle(root).backgroundColor,
        specimenBackground: getComputedStyle(document.querySelector('.gb-specimen')).backgroundColor};
    });
    check(`${name}: reflow`, metrics.scrollWidth <= width + 1 && metrics.violations.length === 0, metrics.violations);
    check(`${name}: 44px primary and navigation targets`, metrics.targets.every(t => t.height >= 44 && t.width >= 24), metrics.targets);
    check(`${name}: native roles resolve`, metrics.font.includes('system-ui') && metrics.mainBackground !== metrics.specimenBackground);
    if (variant.forcedColors !== 'active') check(`${name}: opaque-ground text contrast`, metrics.contrasts.every(c => !c.unsupported && c.ratio >= c.minimum), metrics.contrasts.filter(c => c.unsupported || c.ratio < c.minimum));
    await page.keyboard.press('Tab');
    check(`${name}: first keyboard target is skip link`, await page.locator('.gb-skip').evaluate(el => el === document.activeElement));
    await page.keyboard.press('Enter');
    check(`${name}: skip link focuses main`, await page.locator('#bench-main').evaluate(el => el === document.activeElement));
    const disclosure = page.locator('details').first();
    await disclosure.locator('summary').focus(); await page.keyboard.press('Enter');
    check(`${name}: disclosure keyboard opens`, await disclosure.getAttribute('open') !== null);
    const exact = JSON.parse(await disclosure.locator('pre').innerText());
    assert.deepEqual(exact, JSON.parse(await readFile(path.join(pkg, 'publication.json'), 'utf8')));
    check(`${name}: exact original publication JSON`, true);
    await page.keyboard.press('Enter');
    check(`${name}: disclosure keyboard closes`, await disclosure.getAttribute('open') === null);
    await page.locator('.gb-primary').focus(); await page.keyboard.press('Enter');
    check(`${name}: primary anchor reaches reference`, new URL(page.url()).hash === '#bench-reference');
    check(`${name}: no page errors`, errors.length === 0, errors);
    await page.evaluate(() => scrollTo(0,0));
    await page.screenshot({path: path.join(out, name + '.png'), fullPage: true});
    observations.cases.push({variant, metrics, page_errors: errors});
    await context.close();
  }
  check('no browser-context remote transport attempted', observations.denied_remote.length === 0, observations.denied_remote);
  check('no browser-context write transport attempted', observations.denied_non_get.length === 0, observations.denied_non_get);
} catch (error) {
  check('qualification completed', false, String(error.stack || error));
} finally {
  if (browser) await browser.close();
  child.kill('SIGTERM');
  await writeFile(path.join(out, 'server.log'), log, {flag: 'wx', mode: 0o600});
  observations.passed = observations.checks.filter(c => c.passed).length;
  observations.total = observations.checks.length;
  await writeFile(path.join(out, 'results.json'), JSON.stringify(observations, null, 2) + '\n', {flag: 'wx', mode: 0o600});
}
console.log(JSON.stringify({out, passed: observations.passed, total: observations.total, failures: observations.failures}));
if (observations.failures.length) process.exitCode = 1;
