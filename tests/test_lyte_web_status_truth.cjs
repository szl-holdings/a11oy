// Source-exact, offline LYTE client semantic-readiness tests. No HTTP, browser, credentials or writes.
'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'web', 'lyte.html'), 'utf8');
const match = html.match(/<script>\s*([\s\S]*?)<\/script>/i);
assert.ok(match, 'the source-owned inline LYTE controller must exist');
const script = match[1];

async function render({ status = 200, state = 'BIND', okField = true } = {}) {
  const elements = new Map();
  const reads = [];
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, { textContent: '', innerHTML: '', className: '' });
      return elements.get(id);
    },
  };
  const fetch = async (url, opts) => {
    reads.push({ url, cache: opts?.cache });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => ({
        ok: okField, state,
        hub: { state: 'UNAVAILABLE', running: false },
        honesty: { proven_trust: false, certified: false },
        khipu_receipt: { kind: 'HASH-LINKED', signed: false, proven_trust: false },
        frontiers: [],
      }),
    };
  };
  vm.runInNewContext(script, { document, fetch }, { filename: 'web/lyte.html:inline', timeout: 1200 });
  await new Promise((resolve) => setImmediate(resolve));
  const get = (id) => document.getElementById(id);
  return { reads, dot: get('liveDot').className, tag: get('liveTag').textContent,
    badge: get('organBadge').textContent, state: get('kStatus').textContent,
    trust: get('cTrust').textContent, note: get('bindNote').textContent,
    cells: get('cells').innerHTML };
}
test('qualified BIND stays BIND, explicitly uncertified and untrusted', async () => {
  const r = await render({ state: 'BIND' });
  assert.deepEqual(r.reads, [{url: '/api/a11oy/v1/lyte/status', cache: 'no-store'}]);
  assert.equal(r.dot, 'live-dot ready');
  assert.equal(r.tag, 'LYTE · BIND');
  assert.equal(r.badge, 'BIND · not certified');
  assert.equal(r.state, 'BIND');
  assert.equal(r.trust, 'false');
});
for (const state of ['UNAVAILABLE', 'UNKNOWN', 'DEGRADED', 'LIVE', 'RUNNING', 'PASS', '', null]) {
  test('HTTP 200 with non-BIND semantic state fails closed: ' + String(state), async () => {
    const r = await render({ state });
    assert.equal(r.dot, 'live-dot error');
    assert.equal(r.tag, 'LYTE · UNAVAILABLE');
    assert.equal(r.badge, 'BIND · status UNAVAILABLE');
    assert.equal(r.state, 'UNAVAILABLE');
    assert.match(r.note, /unavailable/i);
    assert.equal(r.trust, 'false');
    assert.match(r.cells, /STRUCTURAL-ONLY/);
  });
}
test('HTTP 200 with explicit ok=false cannot report BIND', async () => {
  const r=await render({state:'BIND',okField:false});
  assert.equal(r.dot,'live-dot error');
  assert.equal(r.state,'UNAVAILABLE');
});
test('HTTP 503 with BIND-shaped body still fails closed', async () => {
  const r=await render({status:503,state:'BIND'});
  assert.equal(r.dot,'live-dot error');
  assert.equal(r.state,'UNAVAILABLE');
});
