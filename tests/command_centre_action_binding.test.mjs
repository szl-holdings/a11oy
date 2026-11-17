// SPDX-License-Identifier: Apache-2.0
// Synthetic transport/DOM contract tests; no provider, real credentials, or signature proof.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { createHash, webcrypto } from 'node:crypto';
import vm from 'node:vm';
const source = readFileSync(new URL('../routers/command_centre_web/app.js', import.meta.url), 'utf8');
const SHA = 'a'.repeat(40);
const digest = text => createHash('sha256').update(text).digest('hex');
const specs = {
  grok: { prefix: '', endpoint: '/api/a11oy/v1/atelier', provider: 'xai', model: 'grok-4.7' },
  local: { prefix: 'local-', endpoint: '/api/a11oy/v1/atelier/local', provider: 'local_ollama', mode: 'NO_KEY_LOCAL', model: 'fixture-local' },
  cpu: { prefix: 'cpu-', endpoint: '/api/a11oy/v1/atelier/cpu-lab', provider: 'szl_cpu_lab', mode: 'NO_PROVIDER_KEY_PUBLIC_CPU_LAB', model: 'fixture-cpu' },
};
const canonical = value => {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object')
    return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
  return JSON.stringify(value);
};
function completed(lane, request) {
  const s = specs[lane], answer = 'Synthetic answer ? no inference';
  const cpu = lane === 'cpu';
  const evidence_handles = [{nodeId:'public:alpha',nodeKind:'DOCUMENT',label:'Public source',note:'Fixture only'}];
  const citations = ['public:alpha'];
  const payload = { schema: 'a11oy.atelier.single-turn.receipt/v1', phase: 'OUTCOME',
    state: 'COMPLETED', client_request_id: request.client_request_id, request_id: '9ebcb810-a2c4-4005-8608-987e6cdecb08',
    provider: s.provider, ...(s.mode ? { mode: s.mode } : {}), model: request.model || s.model,
    prompt_sha256: digest(request.prompt), answer_sha256: digest(answer),
    source_revision: SHA, decision_receipt_hash: 'b'.repeat(64), classification: 'PUBLIC',
    ...(cpu ? { public_share_acknowledged: true, provider_decision:'PROPOSAL',
      provider_output_signature_status:'UNSIGNED_LOCAL', grounding_required:true,
      authority:'NO_ACTION_AUTHORITY', executed:false, provider_outcome_uncertain:false,
      provider_output_authenticity_verified:false,
      evidence_handles_sha256:digest(canonical(evidence_handles)),
      citations_sha256:digest(canonical(citations)) } : {}) };
  return { state: 'COMPLETED', answer, request_id: payload.request_id, model: payload.model,
    ...(s.mode ? { provider: s.provider, mode: s.mode } : {}),
    ...(cpu ? { provider_decision:'PROPOSAL',provider_output_signature_status:'UNSIGNED_LOCAL',
      grounding_required:true,authority:'NO_ACTION_AUTHORITY',executed:false,
      provider_output_authenticity_verified:false,evidence_handles,citations } : {}), retry_safe: false,
    receipt: { payload, digest: 'c'.repeat(64), persisted: true, signature_verified: true,
      chain_scope: 'SINGLE_PROCESS_RETAINED_METADATA_CHAIN' },
    dsse: { signed: true, payloadType: 'application/vnd.szl.atelier-turn+json',
      payload: Buffer.from(JSON.stringify(payload)).toString('base64'),
      signatures: [{ keyid: 'synthetic-fixture-not-a-key', sig: 'c3ludGhldGlj' }] } };
}
async function harness({ transform = x => x, healthStatus = 200, healthReady = true, post, build = SHA } = {}) {
  const nodes = new Map(), calls = [], windows = new Map();
  function node(id) {
    if (nodes.has(id)) return nodes.get(id);
    const n = { id, value: '', checked: false, disabled: true, hidden: true, textContent: '', listeners: new Map(),
      addEventListener(type, fn) { this.listeners.set(type, fn); }, replaceChildren() {}, append() {} };
    nodes.set(id, n); return n;
  }
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    if ((init.method || 'GET') !== 'GET') {
      const lane = Object.keys(specs).find(k => url === specs[k].endpoint + '/turn');
      assert.ok(lane, 'Only fixed fixture turn paths may be submitted');
      const request = JSON.parse(init.body);
      if (post) return post(lane, request);
      return new Response(JSON.stringify(transform(completed(lane, request), lane)), { status: 200, headers: { 'content-type': 'application/json' } });
    }
    const lane = Object.keys(specs).find(k => url === specs[k].endpoint + '/health');
    let value;
    if (lane) value = { ...specs[lane], ready: healthReady, inference_verified: false,
      blockers: healthReady ? [] : ['FIXTURE_UNAVAILABLE'], source_revision: SHA,
      ready_scope: 'LOCAL_PREREQUISITES_ONLY' };
    else if (url.endsWith('/manifest')) value = { surfaces: [], schema: 'szl.command-centre/v1', source_revision: SHA };
    else if (url === '/api/build-info') value = { build: { revision: build } };
    else if (url.endsWith('/inventory')) value = { state: 'UNAVAILABLE', counts: null };
    else if (url.endsWith('/study')) value = { schema: 'szl.atelier.model-intake.v1', collection: { models: [] } };
    else throw new Error('Unexpected fixture URL');
    return new Response(JSON.stringify(value), { status: lane ? healthStatus : 200, headers: { 'content-type': 'application/json' } });
  };
  const context = { document: { getElementById: node, createElement: node },
    window: { confirm: () => true, addEventListener: (name, fn) => windows.set(name, fn) },
    fetch: fetchImpl, AbortController, setTimeout, clearTimeout, TextEncoder, TextDecoder,
    crypto: webcrypto, atob, btoa, Uint8Array, Response, console };
  vm.runInNewContext(source, context, { filename: 'command_centre_web/app.js', timeout: 1000 });
  for (let i = 0; i < 50 && node('refresh').disabled; i++) await new Promise(resolve => setImmediate(resolve));
  assert.equal(node('refresh').disabled, false, 'initial read phase finished');
  for (const s of Object.values(specs)) {
    node(s.prefix + 'operator-key').value = 'synthetic-operator-fixture';
    node(s.prefix + 'prompt').value = 'Public prompt A';
  }
  node('model').value = 'grok-4.7'; node('effort').value = 'high';
  node('classification').value = 'PUBLIC'; node('local-classification').value = 'PUBLIC';
  const fire = async (id, type) => node(id).listeners.get(type)?.({ preventDefault() {}, target: node(id) });
  const acknowledge = async () => { node('cpu-public-ack').checked = true; await fire('cpu-public-ack', 'change'); };
  const submit = lane => fire(specs[lane].prefix + 'turn-form', 'submit');
  return { node, calls, windows, context, fire, acknowledge, submit,
    posts: () => calls.filter(c => c.init.method === 'POST') };
}
for (const lane of Object.keys(specs)) {
  test(`${lane}: complete matching synthetic evidence displays answer with bounded claim`, async () => {
    const h = await harness(); if (lane === 'cpu') await h.acknowledge();
    await h.submit(lane); assert.equal(h.posts().length, 1);
    assert.equal(h.node(specs[lane].prefix + 'answer').hidden, false);
    assert.match(h.node(specs[lane].prefix + 'turn-status').textContent, lane === 'cpu' ? /Source-grounded proposal.*UNSIGNED_LOCAL/i : /not independently verified in this browser/i);
  });
  test(`${lane}: no configured health means no submission`, async () => {
    const h = await harness({ healthReady: false }); if (lane === 'cpu') await h.acknowledge();
    await h.submit(lane); assert.equal(h.posts().length, 0);
  });
  test(`${lane}: denied health means no submission`, async () => {
    const h = await harness({ healthStatus: 403 }); if (lane === 'cpu') await h.acknowledge();
    await h.submit(lane); assert.equal(h.posts().length, 0);
  });
  for (const [name, change] of [
    ['missing receipt', r => { delete r.receipt; }],
    ['unpersisted receipt', r => { r.receipt.persisted = false; }],
    ['unverified server signature', r => { r.receipt.signature_verified = false; }],
    ['wrong prompt', r => { r.receipt.payload.prompt_sha256 = digest('Different prompt'); }],
    ['wrong answer', r => { r.answer = 'Not the bound answer'; }],
    ['wrong client request', r => { r.receipt.payload.client_request_id = 'a different attempt'; }],
    ['wrong request', r => { r.request_id = 'another-request'; }],
    ['wrong provider', r => { r.receipt.payload.provider = 'different-provider'; }],
    ['wrong model', r => { r.model = 'different-model'; }],
    ['decision not outcome', r => { r.receipt.payload.phase = 'DECISION'; }],
    ['changed source', r => { r.receipt.payload.source_revision = 'd'.repeat(40); }],
    ['missing envelope', r => { delete r.dsse; }],
    ['unsigned envelope', r => { r.dsse.signed = false; }],
    ['altered envelope', r => { r.dsse.payload = Buffer.from('{}').toString('base64'); }],
  ]) {
    test(`${lane}: ${name} is withheld and uncertain, not a completed answer`, async () => {
      const h = await harness({ transform: r => { change(r); return r; } });
      if (lane === 'cpu') await h.acknowledge(); await h.submit(lane);
      assert.equal(h.posts().length, 1); assert.equal(h.node(specs[lane].prefix + 'answer').hidden, true);
      assert.match(h.node(specs[lane].prefix + 'turn-status').textContent, /uncertain|unavailable|not established/i);
      assert.ok(h.calls.every(c => c.init.redirect === 'error'), 'all browser reads and writes refuse redirects');
    });
  }
  test(`${lane}: failed response never retries automatically`, async () => {
    const h = await harness({ post: async () => { throw new Error('synthetic timeout'); } });
    if (lane === 'cpu') await h.acknowledge(); await h.submit(lane);
    assert.equal(h.posts().length, 1); assert.equal(h.node(specs[lane].prefix + 'answer').hidden, true);
    h.context.window.confirm = () => false;
    if (lane === 'cpu') await h.acknowledge(); await h.submit(lane);
    assert.equal(h.posts().length, 1);
  });
}
test('CPU disclosure consent is invalidated by a prompt edit', async () => {
  const h = await harness(); await h.acknowledge(); h.node('cpu-prompt').value = 'Public prompt B';
  await h.fire('cpu-prompt', 'input'); assert.equal(h.node('cpu-public-ack').checked, false);
  await h.submit('cpu'); assert.equal(h.posts().length, 0);
});
test('CPU programmatic draft change cannot reuse prior disclosure consent', async () => {
  const h = await harness(); await h.acknowledge(); h.node('cpu-prompt').value = 'Different draft without input event';
  await h.submit('cpu'); assert.equal(h.posts().length, 0);
});
test('CPU fresh acknowledgement permits exactly the changed prompt once', async () => {
  const h = await harness(); await h.acknowledge(); h.node('cpu-prompt').value = 'Public prompt B';
  await h.fire('cpu-prompt', 'input'); await h.acknowledge(); await h.submit('cpu');
  assert.equal(JSON.parse(h.posts()[0].init.body).prompt, 'Public prompt B');
  assert.equal(h.node('cpu-public-ack').checked, false);
});
test('Build declaration does not become independently observed source', async () => {
  const h = await harness(); assert.match(h.node('source-state').textContent, /declared.*not independently verified/i);
});
test('Pagehide clears credentials and exact disclosure consent', async () => {
  const h = await harness(); await h.acknowledge(); h.windows.get('pagehide')();
  for (const s of Object.values(specs)) assert.equal(h.node(s.prefix + 'operator-key').value, '');
  assert.equal(h.node('cpu-public-ack').checked, false);
  h.node('cpu-operator-key').value = 'synthetic-operator-fixture';
  h.node('cpu-public-ack').checked = true; await h.submit('cpu'); assert.equal(h.posts().length, 0);
});

for (const lane of Object.keys(specs)) {
  test(`${lane}: oversized JSON is withheld without retry`, async () => {
    const h = await harness({ transform: r => ({ ...r, oversized: 'x'.repeat(1048576) }) });
    if (lane === 'cpu') await h.acknowledge(); await h.submit(lane);
    assert.equal(h.posts().length, 1);
    assert.equal(h.node(specs[lane].prefix + 'answer').hidden, true);
    assert.match(h.node(specs[lane].prefix + 'turn-status').textContent, /uncertain/i);
  });
  test(`${lane}: concurrent duplicate submit does not dispatch a second request`, async () => {
    let release;
    const h = await harness({ post: async (kind, request) => new Promise(resolve => {
      release = () => resolve(new Response(JSON.stringify(completed(kind, request)),
        { status: 200, headers: { 'content-type': 'application/json' } }));
    }) });
    if (lane === 'cpu') await h.acknowledge();
    const first = h.submit(lane);
    assert.equal(h.node(specs[lane].prefix + 'send').disabled, true);
    await h.submit(lane); assert.equal(h.posts().length, 1);
    release(); await first;
    assert.equal(h.node(specs[lane].prefix + 'answer').hidden, false);
  });
  test(`${lane}: later draft edits do not rebind an in-flight request`, async () => {
    let release, submitted;
    const h = await harness({ post: async (kind, request) => new Promise(resolve => {
      submitted = request;
      release = () => resolve(new Response(JSON.stringify(completed(kind, request)),
        { status: 200, headers: { 'content-type': 'application/json' } }));
    }) });
    if (lane === 'cpu') await h.acknowledge();
    const first = h.submit(lane);
    h.node(specs[lane].prefix + 'prompt').value = 'A different later draft';
    await h.fire(specs[lane].prefix + 'prompt', 'input');
    release(); await first;
    assert.equal(submitted.prompt, 'Public prompt A');
    assert.equal(h.node(specs[lane].prefix + 'answer').hidden, false);
    assert.match(h.node(specs[lane].prefix + 'turn-status').textContent, /not any later draft/i);
  });
  test(`${lane}: repeated identical text receives distinct correlation IDs`, async () => {
    const h = await harness();
    if (lane === 'cpu') await h.acknowledge(); await h.submit(lane);
    if (lane === 'cpu') await h.acknowledge(); await h.submit(lane);
    assert.equal(h.posts().length, 2);
    const ids = h.posts().map(c => JSON.parse(c.init.body).client_request_id);
    assert.notEqual(ids[0], ids[1]);
    assert.equal(h.node(specs[lane].prefix + 'answer').hidden, false);
  });
}


// Transport and signed-payload ambiguity must fail before answer presentation.
for (const lane of Object.keys(specs)) {
  for (const kind of ['top-level', 'escaped-name', 'nested-receipt', 'signature-array', 'embedded-payload']) {
    test(`${lane}: decoded duplicate evidence ${kind} is withheld`, async () => {
      const h = await harness({ post: async (activeLane, request) => {
        const value = completed(activeLane, request);
        if (kind === 'embedded-payload') {
          const embedded = '{"phase":"DECISION",' + JSON.stringify(value.receipt.payload).slice(1);
          value.dsse.payload = Buffer.from(embedded).toString('base64');
        }
        let raw = JSON.stringify(value);
        if (kind === 'top-level') raw = '{"state":"DENIED",' + raw.slice(1);
        if (kind === 'escaped-name') raw = '{"\\u0073tate":"DENIED",'.replace('\\\\u','\\u') + raw.slice(1);
        if (kind === 'nested-receipt') raw = raw.replace('"persisted":true','"persisted":false,"persisted":true');
        if (kind === 'signature-array') raw = raw.replace('"sig":"c3ludGhldGlj"','"sig":"changed","sig":"c3ludGhldGlj"');
        return new Response(raw,{status:200,headers:{'content-type':'application/json'}});
      }});
      if (lane === 'cpu') await h.acknowledge();
      await h.submit(lane);
      assert.equal(h.posts().length,1);
      assert.equal(h.node(specs[lane].prefix+'answer').hidden,true);
      assert.match(h.node(specs[lane].prefix+'turn-status').textContent,/uncertain/i);
    });
  }
  test(`${lane}: repeated member names in separate objects stay valid`,async()=>{
    const h=await harness({transform:value=>({...value,untrusted_context:{one:{x:1},two:{x:2},text:'"x":1,"x":2'}})});
    if(lane==='cpu') await h.acknowledge();
    await h.submit(lane);
    assert.equal(h.posts().length,1);
    assert.equal(h.node(specs[lane].prefix+'answer').hidden,false);
  });
}


for (const [name, mutate] of [
  ['altered public source handle', value => { value.evidence_handles[0].note = 'CHANGED'; }],
  ['altered public citation list', value => { value.citations = []; }],
  ['claimed executed action', value => { value.executed = true; }],
  ['spoofed signed provider output', value => { value.provider_output_signature_status = 'VERIFIED'; }],
]) {
  test('cpu: ' + name + ' is withheld without retry', async () => {
    const h = await harness({ transform: value => { mutate(value); return value; } });
    await h.acknowledge();
    await h.submit('cpu');
    assert.equal(h.posts().length, 1);
    assert.equal(h.node('cpu-answer').hidden, true);
    assert.equal(h.node('cpu-sources-panel').hidden, true);
    assert.match(h.node('cpu-turn-status').textContent, /uncertain|unavailable/i);
  });
}
