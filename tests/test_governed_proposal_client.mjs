/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
 * Behavior contract for the real served client against the real worker schema.
 * All network and AI calls below are in-process fixtures; no live inference.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import {createRequire} from 'node:module';
import {buildContract, handleRequest} from '../cloudflare/a11oy-governed-inference-worker.mjs';
const require = createRequire(import.meta.url);
const client = require('../console/assets/szl-governed-proposal.js');
const REVISION = 'a'.repeat(40);
const LOCKED = ['F1','F4','F7','F11','F12','F18','F19','F22'];
const doctrine = {
  organ: 'a11oy', git_sha: 'b'.repeat(40),
  doctrine_lock: {doctrine: 'v11', state: 'LOCKED', lambda: 'Conjecture 1'},
  locked_formula_count: 8, locked_formula_ids: LOCKED
};
const brain = {
  schema: 'szl.khipu.compound-second-brain.v1', state: 'BLOCKED_ARTIFACT_AND_EVAL_GATES', ready_for_grounded_navigation: false,
  profile: {expected_model: 'fixture-khipu', served_model: 'fixture-fallback', exact_tag_observed: false, artifact_binding: 'UNAVAILABLE'},
  public_chunk_count: 0, memory: {built: true, status: 'INDEX_METADATA_ONLY', document_count: 23, corpus_chunk_count: 47, brain_handle_count: 9, integrity_state: 'CONTENT_ADDRESSED'}
};
const env = {
  SZL_SOURCE_REVISION: REVISION,
  AI: {run: async () => ({response: '<img src=x onerror=alert(1)> A proposal [U1].'})}
};
async function evidenceFetch(url) {
  if (String(url).endsWith('/api/a11oy/v1/honest')) return Response.json(doctrine);
  if (String(url).endsWith('/api/a11oy/v1/ayllu/second-brain')) return Response.json(brain);
  throw new Error('Unexpected fixture request: ' + url);
}
async function worker(path, init) {
  return handleRequest(new Request('https://a-11-oy.com' + path, init), env, evidenceFetch);
}
const contract = buildContract(REVISION);
const health = await (await worker('/api/v2/governed-health')).json();
const proposal = await (await worker('/api/v2/governed-infer', {
  method: 'POST', headers: {'content-type': 'application/json'},
  body: JSON.stringify({prompt: 'Review the supplied evidence.', effort: 'lora', evidence: ['A supplied excerpt.']})
})).json();
const clone = value => structuredClone(value);

// Minimal DOM with observable text/attributes/events. Any innerHTML assignment
// fails: this client must use text nodes, including model and metadata strings.
class Element {
  constructor(tag, doc) {
    this.tagName = tag.toUpperCase(); this.ownerDocument = doc; this.children = [];
    this.listeners = new Map(); this.attributes = {}; this._text = ''; this.value = '';
    this.disabled = false; this.hidden = false; this.parentNode = null;
  }
  appendChild(child) { child.parentNode = this; this.children.push(child); return child; }
  replaceChildren(...children) {
    this.children.forEach(child => {child.parentNode = null;}); this.children = []; this._text = '';
    children.forEach(child => this.appendChild(child));
  }
  remove() {
    if (!this.parentNode) return;
    this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1);
    this.parentNode = null;
  }
  set textContent(value) { this.replaceChildren(); this._text = String(value); }
  get textContent() { return this._text + this.children.map(child => child.textContent).join('\n'); }
  set innerHTML(value) { throw new Error('Unsafe HTML sink: ' + value); }
  get isConnected() { return this === this.ownerDocument.body || Boolean(this.parentNode && this.parentNode.isConnected); }
  setAttribute(key, value) { this.attributes[key] = value; }
  addEventListener(name, fn) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(fn);
  }
  async fire(name) {
    if (this.disabled) return;
    await Promise.all((this.listeners.get(name) || []).map(fn => fn({preventDefault() {}})));
  }
  click() { return this.fire('click'); }
  focus() { this.ownerDocument.activeElement = this; }
  querySelector(selector) {
    return walk(this).find(node => selector === '[data-governed-proposal]' && 'data-governed-proposal' in node.attributes) || null;
  }
}
function walk(root) { return [root, ...root.children.flatMap(walk)]; }
function harness(overrides = {}) {
  const calls = [], pending = [], timers = new Map(), observers = [];
  const doc = {createElement: tag => new Element(tag, doc)};
  const win = {
    AbortController, Blob, URL,
    crypto: Object.prototype.hasOwnProperty.call(overrides, 'crypto') ? overrides.crypto : globalThis.crypto,
    setTimeout: (fn, ms) => { const id = Symbol(); timers.set(id, {fn, ms}); return id; },
    clearTimeout: id => timers.delete(id),
    addEventListener() {}, removeEventListener() {},
    MutationObserver: class {
      constructor(callback) { this.callback = callback; observers.push(this); }
      observe() {} disconnect() { this.disconnected = true; }
    }
  };
  doc.defaultView = win; doc.body = new Element('body', doc);
  const shell = doc.createElement('div'); doc.body.appendChild(shell);
  const container = doc.createElement('main'); shell.appendChild(container);
  let post = () => Promise.resolve(Response.json(proposal));
  const fetcher = async (url, init) => {
    calls.push({url, ...init});
    if (init.method === 'GET' && url.endsWith('governed-contract')) return overrides.contractResponse ? overrides.contractResponse() : Response.json(overrides.contract || contract);
    if (init.method === 'GET' && url.endsWith('governed-health')) return overrides.healthResponse ? overrides.healthResponse() : Response.json(overrides.health || health);
    if (init.method === 'POST' && url === '/api/v2/governed-infer') return post(url, init);
    throw new Error('Unexpected request');
  };
  const api = client.mount(container, {fetch: fetcher, setTimeout: win.setTimeout, clearTimeout: win.clearTimeout, AbortController});
  const all = () => walk(container);
  const get = suffix => all().find(node => node.id && node.id.endsWith('-' + suffix));
  const button = label => all().find(node => node.tagName === 'BUTTON' && node.textContent === label);
  const status = () => all().find(node => node.attributes.role === 'status').textContent;
  const form = () => all().find(node => node.tagName === 'FORM');
  const setPost = fn => {post = fn;};
  const deferred = () => { let resolve; const promise = new Promise(fn => {resolve = fn;}); pending.push(resolve); setPost(() => promise); return resolve; };
  return {api, container, shell, all, get, button, status, form, calls, timers, observers, setPost, deferred};
}
async function ready(options) {
  const h = harness(options); await h.api.ready; return h;
}
async function fillLora(h) {
  h.get('prompt').value = 'Review the supplied evidence.';
  h.get('effort').value = 'lora'; await h.get('effort').fire('change');
}
const postCalls = h => h.calls.filter(call => call.method === 'POST');
const flush = () => new Promise(resolve => setImmediate(resolve));

test('real worker contract drives readiness, only GETs on mount, and LoRA is opt-in', async () => {
  const h = await ready();
  assert.match(h.status(), /^AVAILABLE/);
  assert.equal(h.calls.length, 2);
  assert.ok(h.calls.every(call => call.method === 'GET' && call.credentials === 'same-origin' && call.redirect === 'error' && call.cache === 'no-store'));
  assert.equal(h.get('effort').value, 'fast');
  assert.match(h.container.textContent, /Grounded navigation ready \(reported\)\nNo/);
  assert.match(h.container.textContent, /Expected Khipu model\nfixture-khipu/);
  assert.match(h.container.textContent, /Observed served model\nfixture-fallback/);
  assert.match(h.container.textContent, /Exact model tag observed\nNo/);
  assert.match(h.container.textContent, /Memory integrity \(reported\)\nCONTENT_ADDRESSED/);
  assert.equal(h.button('Generate proposal').disabled, false);
  await fillLora(h);
  assert.match(h.container.textContent, /Experimental.*qualification pending/);
  assert.match(h.container.textContent, /Evaluation: NOT_RUN/);
  assert.equal(postCalls(h).length, 0);
  h.api.destroy();
});

test('incompatible, HTML, cross-origin, stale, and contradictory contracts fail closed', async () => {
  const malformed = clone(contract); delete malformed.input_limits;
  const unsafe = clone(contract); unsafe.endpoint.infer = 'https://other.example/infer';
  const drift = clone(health); drift.source_revision = 'c'.repeat(40);
  const contradiction = clone(health); contradiction.doctrine.lambda_can_authorize = true;
  const falseGreen = clone(health); falseGreen.ai_binding = false;
  for (const options of [
    {contract: malformed}, {contract: unsafe}, {health: drift}, {health: contradiction}, {health: falseGreen},
    {contractResponse: () => new Response('PRIVATE_INVALID_JSON', {headers: {'content-type': 'application/json'}})},
    {contractResponse: () => new Response('<html>SPA fallback</html>', {headers: {'content-type': 'text/html'}})},
    {healthResponse: () => Response.json({status: 'READY'}, {status: 503})}
  ]) {
    const h = await ready(options);
    assert.match(h.status(), /^UNAVAILABLE/);
    assert.doesNotMatch(h.container.textContent, /PRIVATE_INVALID_JSON/);
    assert.equal(h.button('Generate proposal').disabled, true);
    assert.equal(postCalls(h).length, 0);
    h.api.destroy();
  }
});

test('available efforts are the contract-health intersection; lora-only never defaults to lora', async () => {
  const frontier = clone(health); frontier.efforts = ['frontier', 'unknown'];
  const h = await ready({health: frontier});
  assert.equal(h.get('effort').value, 'frontier');
  assert.deepEqual(h.get('effort').children.map(node => node.value), ['', 'frontier']);
  h.api.destroy();
  const lora = clone(health); lora.efforts = ['lora'];
  const onlyLora = await ready({health: lora});
  assert.equal(onlyLora.get('effort').value, '');
  assert.match(onlyLora.container.textContent, /requires explicit selection/);
  onlyLora.api.destroy();
});

test('input limits reject excessive prompt, fractional tokens, and aggregate evidence', () => {
  const capability = client.prepareCapability(contract, health);
  assert.throws(() => client.validateInput(capability, 'x'.repeat(12001), 'fast', 256, []), /prompt/);
  assert.throws(() => client.validateInput(capability, 'ask', 'fast', 16.5, []), /integer/);
  assert.throws(() => client.validateInput(capability, 'ask', 'fast', 256, [{text: 'x'.repeat(4001)}]), /evidence/);
  assert.throws(() => client.validateInput(capability, 'ask', 'fast', 256, Array.from({length: 4}, () => ({text: 'x'.repeat(4000)}))), /Combined evidence/);
  assert.throws(() => client.validateInput(capability, 'ask', 'unadvertised', 256, []), /available effort/);
  assert.deepEqual(client.validateInput(capability, ' ask ', 'fast', 256, [{text: '', source: ''}]), {prompt: 'ask', effort: 'fast', max_new_tokens: 256, evidence: []});
});

test('explicit LoRA submission renders actual worker provenance safely and separates memory counts', async () => {
  const h = await ready(); await fillLora(h);
  await h.button('Add evidence item').fire('click');
  const excerpt = h.all().find(node => node.id && node.id.includes('-excerpt-'));
  excerpt.value = 'An operator excerpt.';
  const source = h.all().find(node => node.id && node.id.includes('-source-'));
  source.value = 'operator-reference';
  const enriched = clone(proposal);
  enriched.private_graph = {secret: 'PRIVATE_GRAPH_SECRET'};
  enriched.evidence_handles[0].private_reasoning = 'PRIVATE_REASONING_SECRET';
  enriched.claims[0].private_payload = 'PRIVATE_CLAIM_SECRET';
  enriched.second_brain = {state: 'NOT_READY', public_chunk_count: null, memory_observation: {status: 'INDEX_METADATA_ONLY', document_count: 23, corpus_chunk_count: 47, brain_handle_count: 9}};
  h.setPost(() => Response.json(enriched));
  await h.form().fire('submit');
  assert.equal(postCalls(h).length, 1);
  const call = postCalls(h)[0], input = JSON.parse(call.body);
  assert.equal(call.url, '/api/v2/governed-infer');
  assert.equal(call.headers['content-type'], 'application/json');
  assert.equal(input.effort, 'lora');
  assert.equal(input.max_new_tokens, contract.input_limits.max_new_tokens.default);
  assert.deepEqual(input.evidence, [{text: 'An operator excerpt.', source: 'operator-reference'}]);
  assert.match(h.status(), /^PROPOSAL RECEIVED/);
  assert.match(h.container.textContent, /<img src=x onerror=alert\(1\)>/);
  assert.equal(h.all().filter(node => node.tagName === 'IMG').length, 0);
  assert.match(h.container.textContent, new RegExp(proposal.attempt_id));
  assert.match(h.container.textContent, new RegExp(proposal.request_id));
  assert.match(h.container.textContent, /Public chunks \(reported\)\nUNAVAILABLE/);
  assert.match(h.container.textContent, /Corpus chunks \(reported\)\n47/);
  assert.match(h.container.textContent, /UNSIGNED_EDGE/);
  assert.match(h.container.textContent, /Conjecture 1/);
  assert.match(h.container.textContent, /does not prove this generated answer/);
  assert.doesNotMatch(h.container.textContent, /PRIVATE_(GRAPH|REASONING|CLAIM)_SECRET/);
  assert.ok(h.button('Download unsigned receipt'));
  h.api.destroy();
});

test('contradictory authority and unsupported receipt payloads are never displayed as successful proposals', async () => {
  const unauthorized = clone(proposal); unauthorized.executed = true;
  const privateReceipt = clone(proposal); privateReceipt.receipt.payload.private_graph = 'PRIVATE_RECEIPT_SECRET';
  const mismatched = clone(proposal); mismatched.receipt.payload.output_sha256 = 'f'.repeat(64);
  for (const body of [unauthorized, privateReceipt, mismatched]) {
    const h = await ready(); await fillLora(h); h.setPost(() => Response.json(body));
    await h.form().fire('submit');
    assert.match(h.status(), /^OUTCOME UNKNOWN/);
    assert.doesNotMatch(h.container.textContent, /PRIVATE_RECEIPT_SECRET|<img/);
    assert.equal(h.button('Download unsigned receipt'), undefined);
    h.api.destroy();
  }
});

test('HTTP error shows a returned attempt identifier and never retries', async () => {
  const h = await ready(); await fillLora(h);
  h.setPost(() => Response.json({
    schema: 'szl.cloudflare-governed-inference-error/v1', error: 'all_model_candidates_failed',
    executed: false, authority_state: 'NO_ACTION_AUTHORITY', attempt_id: proposal.attempt_id
  }, {status: 502}));
  await h.form().fire('submit');
  assert.match(h.status(), /^FAILED/);
  assert.match(h.status(), new RegExp(proposal.attempt_id));
  assert.equal(postCalls(h).length, 1);
  assert.equal(h.button('Generate proposal').disabled, false);
  h.api.destroy();
});

test('cancel and timeout abort waiting, admit unknown server outcome, and ignore late success', async () => {
  for (const mode of ['cancel', 'timeout']) {
    const h = await ready(); await fillLora(h); const resolve = h.deferred();
    const submitted = h.form().fire('submit');
    await flush();
    assert.equal(postCalls(h).length, 1);
    assert.equal(h.button('Generate proposal').disabled, true);
    if (mode === 'cancel') await h.button('Stop waiting').fire('click');
    else [...h.timers.values()].find(timer => timer.ms === 90000).fn();
    assert.equal(postCalls(h)[0].signal.aborted, true);
    assert.match(h.status(), /server outcome unknown/);
    const stopped = h.status();
    resolve(Response.json(proposal)); await submitted;
    assert.equal(h.status(), stopped);
    assert.equal(h.button('Download unsigned receipt'), undefined);
    assert.equal(postCalls(h).length, 1);
    h.api.destroy();
  }
});

test('leaving Ask aborts requests, clears inputs, and ignores detached-view completion', async () => {
  const h = await ready(); await fillLora(h); const resolve = h.deferred();
  const submitted = h.form().fire('submit'); await flush();
  const card = h.api.element, prompt = h.get('prompt');
  card.remove(); h.observers.forEach(observer => observer.callback());
  assert.equal(postCalls(h)[0].signal.aborted, true);
  assert.equal(prompt.value, '');
  resolve(Response.json(proposal)); await submitted;
  assert.doesNotMatch(card.textContent, /PROPOSAL RECEIVED/);
  assert.ok(h.observers.every(observer => observer.disconnected));
});

test('memory binding display accepts only literal booleans and string labels', async () => {
  const malformed = clone(health);
  malformed.second_brain = {
    state: 'NOT_READY', ready_for_grounded_navigation: 'true',
    model_binding: {expected_model: {private: 'PRIVATE_BINDING'}, served_model: null, exact_tag_observed: 'true', artifact_binding: {}},
    memory_observation: {integrity_state: {private: 'PRIVATE_INTEGRITY'}}
  };
  const h = await ready({health: malformed});
  assert.match(h.container.textContent, /Grounded navigation ready \(reported\)\nUNAVAILABLE/);
  assert.match(h.container.textContent, /Exact model tag observed\nUNAVAILABLE/);
  assert.match(h.container.textContent, /Expected Khipu model\nUNAVAILABLE/);
  assert.match(h.container.textContent, /Memory integrity \(reported\)\nUNAVAILABLE/);
  assert.doesNotMatch(h.container.textContent, /PRIVATE_BINDING|PRIVATE_INTEGRITY|object Object/);
  h.api.destroy();
});

test('real worker hashes verify locally; tampered output or canonical receipt payload is rejected', async () => {
  assert.deepEqual(await client.verifyHashes(proposal, globalThis.crypto), {output: true, receipt: true});
  const changedOutput = clone(proposal); changedOutput.output += ' changed';
  const changedPayload = clone(proposal); changedPayload.receipt.payload.prompt_sha256 = 'e'.repeat(64);
  for (const body of [changedOutput, changedPayload]) {
    const h = await ready(); await fillLora(h); h.setPost(() => Response.json(body));
    await h.form().fire('submit');
    assert.match(h.status(), /hash does not match/);
    assert.equal(h.button('Download unsigned receipt'), undefined);
    assert.doesNotMatch(h.container.textContent, /<img/);
    h.api.destroy();
  }
});

test('missing WebCrypto fails closed and cancellation during hashing discards the response', async () => {
  const unavailable = await ready({crypto: null}); await fillLora(unavailable);
  await unavailable.form().fire('submit');
  assert.match(unavailable.status(), /Hash verification is unavailable/);
  assert.equal(unavailable.button('Download unsigned receipt'), undefined);
  unavailable.api.destroy();
  const waits = [];
  const delayedCrypto = {subtle: {digest: (algorithm, bytes) => new Promise(resolve => {
    waits.push(async () => resolve(await globalThis.crypto.subtle.digest(algorithm, bytes)));
  })}};
  const h = await ready({crypto: delayedCrypto}); await fillLora(h);
  const submitted = h.form().fire('submit'); await flush();
  assert.equal(waits.length, 2);
  await h.button('Stop waiting').fire('click');
  const stopped = h.status();
  await Promise.all(waits.map(resolve => resolve())); await submitted;
  assert.equal(h.status(), stopped);
  assert.equal(h.button('Download unsigned receipt'), undefined);
  assert.equal(postCalls(h).length, 1);
  h.api.destroy();
});

test('ancestor detachment during hashing or availability clears inputs without an observer delivery', async () => {
  const waits = [];
  const delayedCrypto = {subtle: {digest: (algorithm, bytes) => new Promise(resolve => {
    waits.push(async () => resolve(await globalThis.crypto.subtle.digest(algorithm, bytes)));
  })}};
  const h = await ready({crypto: delayedCrypto}); await fillLora(h);
  const prompt = h.get('prompt');
  const submitted = h.form().fire('submit'); await flush();
  assert.equal(waits.length, 2);
  h.shell.remove();
  assert.equal(h.api.element.isConnected, false);
  await Promise.all(waits.map(resolve => resolve())); await submitted;
  assert.equal(prompt.value, '');
  assert.equal(postCalls(h)[0].signal.aborted, true);
  assert.equal(h.button('Download unsigned receipt'), undefined);
  assert.doesNotMatch(h.container.textContent, /PROPOSAL RECEIVED|<img/);
  assert.ok(h.observers.every(observer => observer.disconnected));
  let release;
  const loading = harness({contractResponse: () => new Promise(resolve => {release = resolve;})});
  const pendingPrompt = loading.get('prompt'); pendingPrompt.value = 'local private draft';
  loading.shell.remove();
  release(Response.json(contract)); await loading.api.ready;
  assert.equal(pendingPrompt.value, '');
  assert.equal(loading.button('Generate proposal').disabled, true);
  assert.equal(postCalls(loading).length, 0);
});
