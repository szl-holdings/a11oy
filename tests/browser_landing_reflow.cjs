// SPDX-License-Identifier: Apache-2.0
// Render the exact landing source/assets with unavailable provider fixtures.
const assert = require('node:assert/strict');
const { createServer } = require('node:http');
const { readFileSync, mkdirSync, writeFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { execFileSync } = require('node:child_process');
const { chromium } = require('playwright');

const root = resolve(__dirname, '..');
const output = process.env.LANDING_EVIDENCE_DIR || '/tmp/landing-browser-evidence';
const base = process.env.LANDING_BASE_SHA || '';
if (base) assert.match(base, /^[0-9a-f]{40}$/);
const source = readFileSync(resolve(root, 'a11oy_landing.html'), 'utf8');
const files = new Map([
  ...['szl-flow.css', 'apex-v2.css', 'szl-holo-v2.css', 'szl-flow.js', 'szl-holo-v2.js'].map(name => [`/assets/${name}`, `console/assets/${name}`]),
  ['/static/landing-honest-bind.js', 'static/landing-honest-bind.js'],
].map(([url, path]) => [url, readFileSync(resolve(root, path))]));

async function main() {
  mkdirSync(output, { recursive: true });
  const results = [];
  let html = source;
  const server = createServer((request, response) => {
    const path = new URL(request.url, 'http://127.0.0.1').pathname;
    const file = files.get(path);
    if (path === '/') {
      response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      response.end(html);
    } else if (file) {
      response.writeHead(200, { 'Content-Type': path.endsWith('.css') ? 'text/css' : 'text/javascript' });
      response.end(file);
    } else {
      response.writeHead(503, { 'Content-Type': 'application/json' });
      response.end('{"state":"UNAVAILABLE","scope":"synthetic-browser-fixture"}');
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  let browser;
  try {
    browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH });
    for (const variant of base ? ['baseline', 'candidate'] : ['candidate']) {
      html = variant === 'baseline' ? execFileSync('git', ['show', `${base}:a11oy_landing.html`], { cwd: root, encoding: 'utf8' }) : source;
      for (const width of [320, 375, 768, 1440]) {
        const page = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: 'reduce' });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', route => {
          if (new URL(route.request().url()).origin === origin) return route.continue();
          return route.fulfill({ status: 503, contentType: 'application/json', headers: { 'Access-Control-Allow-Origin': '*' }, body: '{"state":"UNAVAILABLE","scope":"synthetic-browser-fixture"}' });
        });
        await page.goto(origin);
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const layout = await page.evaluate(() => {
          const viewport = window.innerWidth;
          const menu = document.querySelector('#menu-toggle');
          const subtitle = document.querySelector('header.nav .brand .sub');
          const range = document.createRange();
          range.selectNodeContents(subtitle);
          const identity = range.getBoundingClientRect().toJSON();
          const menuBox = menu.getBoundingClientRect().toJSON();
          const overflowingText = [];
          const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
          let node;
          while ((node = walker.nextNode())) {
            const parent = node.parentElement;
            if (!node.textContent.trim() || !parent || parent.closest('script,style,svg,.skip-link,[aria-hidden="true"],[hidden]')) continue;
            if (!parent.getClientRects().length || getComputedStyle(parent).visibility === 'hidden') continue;
            const text = document.createRange(); text.selectNodeContents(node);
            const box = text.getBoundingClientRect();
            if (box.width && (box.left < -2 || box.right > viewport + 2)) overflowingText.push({ text: node.textContent.trim().slice(0, 90), class: parent.className, box: box.toJSON() });
          }
          return { viewport, scrollWidth: document.documentElement.scrollWidth, identity, menu: menuBox,
            identityText: subtitle.textContent, menuVisible: menuBox.width > 0,
            overflowingText,
          };
        });
        const failures = [];
        if (layout.overflowingText.length) failures.push('visible text overflows');
        if (layout.scrollWidth > width + 2) failures.push('document overflows');
        if (layout.menuVisible && layout.identity.right > layout.menu.left - 4) failures.push('identity overlaps menu');
        if (layout.menuVisible && (layout.menu.width < 48 || layout.menu.height < 48)) failures.push('menu shrank below48px');
        if (!/SZL Holdings \/ software & research/.test(layout.identityText)) failures.push('full identity missing');
        if (errors.length) failures.push('page JavaScript error');
        results.push({ variant, width, ...layout, errors, failures });
        if (width === 320 || failures.length) await page.screenshot({ path: resolve(output, `${variant}-${width}.png`), fullPage: false });
        if (variant === 'candidate' && width === 320) {
          await page.locator('#menu-toggle').click();
          assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'), 'true');
          await page.locator('#site-nav a[href="#platform"]').click();
          assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'), 'false');
        }
        await page.close();
      }
    }
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
    writeFileSync(resolve(output, 'landing-reflow-results.json'), JSON.stringify({ observed_at: new Date().toISOString(), scope: 'LOCAL_SOURCE_BROWSER_UNAVAILABLE_PROVIDER_FIXTURES', base_sha: base || null, results }, null, 2) + '\n');
  }
  const failures = results.filter(row => row.variant === 'candidate' && row.failures.length);
  console.log(JSON.stringify(results.map(row => ({ variant: row.variant, width: row.width, failures: row.failures })), null, 2));
  assert.deepEqual(failures, [], 'candidate must fit without obscuring identity or shrinking controls');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
