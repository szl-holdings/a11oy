#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
// Offline execution of shipped client helpers. No HTTP or application server runs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createHash, generateKeyPairSync, sign, webcrypto} = require('node:crypto');
const source = fs.readFileSync(path.join(__dirname, '../pages/console.html'), 'utf8');
function between(first, last) {
  const start = source.indexOf(first), end = source.indexOf(last, start);
  assert(start >= 0 && end > start, `Shipped source boundaries unavailable: ${first}`);
  return source.slice(start, end);
}
const nodes = new Map();
function node(id) {
  if (!id) return null;
  if (!nodes.has(id)) nodes.set(id, {value:'', textContent:'', style:{}, disabled:false});
  return nodes.get(id);
}
const observations = {fetches:[], reads:[], waterfalls:[]};
let fetchBehavior, envelope, keyText, keyStatus = 200;
const context = vm.createContext({
  window:{}, document:{getElementById:node}, E:node,
  T:(id, text) => { if (id) node(id).textContent = String(text); },
  B1:{receiptWaterfall:(id, spans) => observations.waterfalls.push(JSON.parse(JSON.stringify(spans)))},
  CREAM:'neutral', TEAL:'success', RED:'failure', TextEncoder, TextDecoder, Uint8Array,
  crypto:webcrypto, atob, AbortController, setTimeout, clearTimeout, performance,
  fetch:async (url, options) => {
    observations.fetches.push({url, headers:{...options.headers}, body:options.body,
      method:options.method, cache:options.cache, credentials:options.credentials,
      redirect:options.redirect, inputValue:node('credential').value});
    return fetchBehavior();
  },
  gj:async url => { observations.reads.push(url); return structuredClone(envelope); },
});
vm.runInContext(between('window._a11oyGovernPost=async function', 'function esc(s)'), context);
vm.runInContext(between('window._a11oyEnergyReading=function(reading)', '// ===== VISUAL HELPERS'), context);
vm.runInContext(between('window._meshRows=function(raw)', 'function _meshSortRows'), context);
vm.runInContext(between('function _b64ToBytes(b64)', 'async function getText(p)'), context);
vm.runInContext(between('window._a11oyRequireSampleExport=function(env)', 'window._a11oyLedgerReading=function(d)'), context);
vm.runInContext(between('window._a11oyLedgerReading=function(d)', '/* ---- CHAIN:'), context);
context.window.verifyReceipt = context.verifyReceipt;
context.window._szlFetch = async (url, options) => {
  observations.reads.push(url);
  assert.equal(options.redirect, 'error');
  assert.equal(options.credentials, 'same-origin');
  return {ok:keyStatus === 200, status:keyStatus, text:async () => keyText};
};
const ids = {signature:'signature', pae:'pae', message:'message', envelope:'envelope',
  waterfall:'waterfall', buttons:['verify', 'tamper']};
const results = [];
async function check(name, fn) {
  try { await fn(); results.push({name, passed:true}); }
  catch (error) { results.push({name, passed:false, error:error.stack}); }
}
function reset() {
  observations.fetches.length = observations.reads.length = observations.waterfalls.length = 0;
  nodes.clear(); keyStatus = 200;
  fetchBehavior = async () => ({ok:true, status:200, json:async () => ({signed:false})});
}
function plain(value) { return JSON.parse(JSON.stringify(value)); }
function sample(payload = {}) {
  return {state:'SAMPLE', data_kind:'sample', operational:false, receipt_minted:false, signed:false,
    payloadType:'application/vnd.szl.receipt+json', signatures:[],
    payload:Buffer.from(JSON.stringify({state:'SAMPLE', data_kind:'sample', operational:false, ...payload})).toString('base64')};
}
const pair = generateKeyPairSync('ec', {namedCurve:'prime256v1'});
keyText = pair.publicKey.export({type:'spki', format:'pem'}).toString();
function signedSample() {
  const result = sample({_signing_identity:{verify_key_url:'/api/a11oy/cosign.pub',
    key_fingerprint_sha256:createHash('sha256').update(keyText.trim()).digest('hex')}});
  const body = Buffer.from(result.payload, 'base64');
  const prefix = Buffer.from(`DSSEv1 ${Buffer.byteLength(result.payloadType)} ${result.payloadType} ${body.length} `);
  result.signatures = [{sig:sign('sha256', Buffer.concat([prefix, body]), pair.privateKey).toString('base64')}];
  result.signed = true;
  return result;
}
(async () => {
  await check('All shipped classic inline scripts parse', () => {
    let count = 0;
    // Consume comments and raw script bodies separately, as HTML does. A literal
    // '<script>' in an HTML comment must not become executable test input.
    const opening = /<!--[\s\S]*?-->|<script\b([^>]*)>/gi;
    const closing = /<\/script\s*>/gi;
    let match;
    while ((match = opening.exec(source))) {
      if (match[1] === undefined) continue;
      const start = opening.lastIndex;
      closing.lastIndex = start;
      const end = closing.exec(source);
      assert(end, 'Script closing tag missing');
      opening.lastIndex = closing.lastIndex;
      if (/\bsrc\s*=|\btype\s*=\s*["'](?:application\/[^"']*json|module)/i.test(match[1])) continue;
      const body = source.slice(start, end.index);
      if (!body.trim()) continue;
      new vm.Script(body, {filename:`console-inline-${++count}.js`});
    }
    assert(count > 10);
  });
  await check('Absent credential clears input and makes no request', async () => {
    reset(); node('credential').value = '   ';
    await assert.rejects(context.window._a11oyGovernPost('/api/a11oy/v1/vert/legal/govern', {}, 'credential'), /No mutation was attempted/);
    assert.equal(node('credential').value, ''); assert.equal(observations.fetches.length, 0);
  });
  await check('Off-origin and unapproved paths reject before network', async () => {
    for (const url of ['https://example.invalid/govern', '//example.invalid/govern', '/api/a11oy/v1/vert/legal/govern?next=elsewhere', '/api/a11oy/v1/vert/../govern']) {
      reset(); node('credential').value = 'LOCAL_TEST_CREDENTIAL';
      await assert.rejects(context.window._a11oyGovernPost(url, {}, 'credential'), /No mutation was attempted/);
      assert.equal(observations.fetches.length, 0); assert.equal(node('credential').value, '');
    }
  });
  await check('Authorized request consumes credential once and sends it only in a header', async () => {
    reset(); node('credential').value = '  LOCAL_TEST_CREDENTIAL  ';
    const result = await context.window._a11oyGovernPost('/api/a11oy/v1/vert/legal/govern', {action:'local fixture'}, 'credential');
    assert.equal(result.signed, false); assert.equal(observations.fetches.length, 1);
    const request = observations.fetches[0];
    assert.equal(request.headers.Authorization, 'Bearer LOCAL_TEST_CREDENTIAL');
    assert.equal(request.inputValue, ''); assert.equal(request.method, 'POST');
    assert.equal(request.redirect, 'error'); assert.equal(request.cache, 'no-store');
    assert.equal(request.credentials, 'same-origin');
    assert(!request.url.includes('CREDENTIAL') && !request.body.includes('CREDENTIAL'));
    await assert.rejects(context.window._a11oyGovernPost(request.url, {}, 'credential'), /credential required/);
    assert.equal(observations.fetches.length, 1);
  });
  await check('Network ambiguity never retries or exposes credential/error payload', async () => {
    reset(); node('credential').value = 'LOCAL_TEST_CREDENTIAL';
    fetchBehavior = async () => {throw new Error('LOCAL_TEST_CREDENTIAL transport detail');};
    await assert.rejects(context.window._a11oyGovernPost('/api/a11oy/v1/deva/finance/govern', {}, 'credential'), error => /Inspect the receipt ledger/.test(error.message) && !/CREDENTIAL/.test(error.message));
    assert.equal(observations.fetches.length, 1); assert.equal(node('credential').value, '');
  });
  await check('HTTP refusal and malformed response do not retry', async () => {
    for (const malformed of [false, true]) {
      reset(); node('credential').value = 'LOCAL_TEST_CREDENTIAL';
      fetchBehavior = async () => ({ok:malformed, status:malformed?200:401, json:async () => {throw Error('bad JSON');}});
      await assert.rejects(context.window._a11oyGovernPost('/api/a11oy/v1/devb/enterprise/govern', {}, 'credential'), malformed?/not valid JSON/:/HTTP 401/);
      assert.equal(observations.fetches.length, 1);
    }
  });
  await check('Anonymous mesh arrays cannot inherit a known identity or observed health', () => {
    const rows = context.window._meshRows([{status:'ok', latency_ms:0, http_code:200}]);
    assert.equal(rows[0].name, 'Unidentified capability'); assert.equal(rows[0].observed, false);
    assert.equal(rows[0].status, 'unavailable'); assert.equal(context.window._meshIsUp(rows[0]), false);
    assert.equal(context._meshHealthScore(rows), null);
  });
  await check('Identified observations preserve zero latency and leave absent HTTP unavailable', () => {
    const rows = context.window._meshRows({core:{status:'ok', latency_ms:0}});
    assert.equal(rows[0].id, 'core'); assert.equal(rows[0].latency_ms, 0); assert.equal(rows[0].http_code, null);
    assert.equal(context.window._meshIsUp(rows[0]), true);
    assert.equal(context._meshHealthScore(context.window._meshRows({core:{status:'ok'}})), null);
    assert.equal(context.window._meshRows({core:{status:'ok', observed:false}})[0].observed, false);
  });
  await check('Sample declaration is required in envelope and decoded payload', () => {
    assert.equal(context.window._a11oyRequireSampleExport(sample()).state, 'SAMPLE');
    for (const env of [{}, {...sample(), operational:true}, sample({state:'LIVE'}), {...sample(), payload:'!invalid'}]) {
      assert.throws(() => context.window._a11oyRequireSampleExport(env), /SAMPLE|malformed/);
    }
  });
  await check('Operational ledger distinguishes live empty, live records, and unavailable evidence', () => {
    const empty = {state:'live', data_kind:'live', operational:true, receipt_minted:false, count:0, receipts:[]};
    assert.deepEqual(plain(context.window._a11oyLedgerReading(empty)),
      {label:'LIVE · EMPTY', receipts:[], count:0, digest:'UNAVAILABLE'});
    const record = {index:19, digest:'a'.repeat(64), schema:'szl.operator/v1', signed:false};
    const live = {...empty, count:1, receipts:[record]};
    const value = plain(context.window._a11oyLedgerReading(live));
    assert.equal(value.label, 'LIVE · REPORTED'); assert.equal(value.digest, record.digest);
    assert.deepEqual(value.receipts, [record]);
    for (const invalid of [null, {}, {...live, state:'SAMPLE'}, {...live, data_kind:'sample'},
      {...live, operational:false}, {...live, receipt_minted:true}, {...live, count:0},
      {...live, receipts:[null]}, {...live, receipts:[[]]}]) {
      assert.throws(() => context.window._a11oyLedgerReading(invalid), /consistent live operational ledger/);
    }
  });
  await check('Ledger graph uses operational fields and reports adjacency without verification claims', () => {
    let rendered;
    const graph = {getElementById:() => ({addClass(){}}), on(){}};
    context.cytoscape = options => {rendered=options; return graph;};
    context.window.cytoscape = context.cytoscape;
    context.GOLD='gold';
    vm.runInContext(between('function chainDagre(id, receipts, finalHash)', '/* =========================================================================\n     4) RECEIPTS'), context);
    context.chainDagre('graph', [{index:19,digest:'a'.repeat(64),schema:'operator-a'},
      {index:7,digest:'b'.repeat(64),schema:'operator-b'}]);
    assert.equal(rendered.elements[0].data.label, '#19\noperator-a\naaaaaaaa');
    assert.equal(rendered.elements[1].data.label, '#7\noperator-b\nbbbbbbbb');
    assert(!rendered.elements.some(item => 'verified' in item.data));
    const view = between('V.chain={', '/* ---- RECEIPTS:');
    assert.match(view, /Operational Receipt Ledger/);
    assert.match(view, /not verified parent links/);
    assert(!view.includes('Sample Hash-Link Chain'));
    assert.match(between('V.ledger3d={', '/* ---- LINEAGE:'), /No sample records are substituted/);
  });
  await check('Energy reports a paired window average, preserving a real zero', () => {
    const measured = {stub_mode:false, joules_measured_label:'MEASURED', measured_jobs:1,
      measured_tokens:40, measured_token_joules:45};
    assert.deepEqual(plain(context.window._a11oyEnergyReading(measured)), {label:'MEASURED', value:1.125});
    assert.deepEqual(plain(context.window._a11oyEnergyReading({...measured, measured_token_joules:0})), {label:'MEASURED', value:0});
    const sample = {stub_mode:true, joules_sample_label:'SAMPLE', sample_jobs:2,
      tokens_total:10, measured_tokens:0, joules_sample_total:20};
    assert.deepEqual(plain(context.window._a11oyEnergyReading(sample)), {label:'SAMPLE', value:2});
  });
  await check('Energy flags and invalid or unpaired values never become measurements', () => {
    for (const reading of [null, {}, {stub_mode:false, measured_token_joules:8, measured_tokens:2},
      {stub_mode:false, joules_measured_label:'MEASURED', measured_jobs:1, measured_token_joules:8, measured_tokens:0},
      {stub_mode:false, joules_measured_label:'MEASURED', measured_jobs:1, measured_token_joules:Infinity, measured_tokens:2},
      {stub_mode:true, joules_sample_label:'SAMPLE', sample_jobs:1, joules_sample_total:10}]) {
      assert.deepEqual(plain(context.window._a11oyEnergyReading(reading)), {label:'UNAVAILABLE', value:null});
    }
  });
  await check('Unmeasured jobs with the stock zero sample accumulator stay unavailable', () => {
    const stock = {stub_mode:true, joules_sample_label:'SAMPLE', sample_jobs:1,
      tokens_total:40, measured_tokens:0, joules_sample_total:0};
    assert.deepEqual(plain(context.window._a11oyEnergyReading(stock)), {label:'UNAVAILABLE', value:null});
    assert.deepEqual(plain(context.window._a11oyEnergyReading({...stock, joules_sample_total:null})), {label:'UNAVAILABLE', value:null});
  });
  await check('Unsigned sample never fetches a key or claims verification', async () => {
    reset(); envelope = sample(); await context.window._a11oyVerifySample(ids, false);
    assert.equal(node('signature').textContent, 'UNSIGNED · DIGEST ONLY');
    assert.deepEqual(observations.reads, ['/api/a11oy/v1/receipt/export']);
    assert.equal(node('verify').disabled, false); assert.equal(node('tamper').disabled, false);
  });
  await check('Real local ECDSA check authenticates only the sample, with measured aggregate spans', async () => {
    reset(); envelope = signedSample(); await context.window._a11oyVerifySample(ids, false);
    assert.equal(node('signature').textContent, 'SAMPLE SIGNATURE VERIFIED');
    assert.match(node('message').textContent, /no operational action inferred/);
    assert.match(node('message').textContent, /Chain inclusion was not checked/);
    assert.equal(node('pae').textContent.length, 64);
    const spans = observations.waterfalls.at(-1);
    assert.equal(spans.length, 3); assert(spans.every(span => span.state === 'pass' && span.dur >= 0));
    assert(!spans.some(span => /chain-link|base64-decode/.test(span.label)));
  });
  await check('A tampered local sample fails the actual ECDSA check', async () => {
    reset(); envelope = signedSample(); await context.window._a11oyVerifySample(ids, true);
    assert.equal(node('signature').textContent, 'SAMPLE SIGNATURE FAILED');
    assert.match(node('message').textContent, /Tampered SAMPLE signature did not verify/);
    assert.equal(observations.waterfalls.at(-1)[2].state, 'fail');
  });
  await check('Wrong key identity and off-origin key discovery are rejected', async () => {
    for (const identity of [{verify_key_url:'https://example.invalid/key',key_fingerprint_sha256:'a'.repeat(64)},
      {verify_key_url:'/api/a11oy/cosign.pub',key_fingerprint_sha256:'0'.repeat(64)}]) {
      reset(); envelope = sample({_signing_identity:identity}); envelope.signed = true;
      await context.window._a11oyVerifySample(ids, false);
      assert.equal(node('signature').textContent, 'UNAVAILABLE');
      assert(observations.reads.every(url => url.startsWith('/api/a11oy/')));
      assert(!observations.waterfalls.at(-1).some(span => /verify SAMPLE/.test(span.label) && span.state === 'pass'));
    }
  });
  await check('Failed sample reads replace a prior success and release both controls', async () => {
    reset(); node('signature').textContent = 'SAMPLE SIGNATURE VERIFIED'; envelope = {};
    await context.window._a11oyVerifySample(ids, false);
    assert.equal(node('signature').textContent, 'UNAVAILABLE'); assert.equal(node('pae').textContent, '—');
    assert.match(node('message').textContent, /did not declare SAMPLE evidence/);
    assert.equal(node('verify').disabled, false); assert.equal(node('tamper').disabled, false);
  });
  console.log(JSON.stringify({scope:'offline shipped client helpers; no production actions', checks:results.length,
    passed:results.filter(row => row.passed).length, failures:results.filter(row => !row.passed)}, null, 2));
  process.exitCode = results.some(row => !row.passed) ? 1 : 0;
})();
