// SPDX-License-Identifier: Apache-2.0
// Browser-local trust evidence checks, exercised with real fixture-only P-256 keys.
// These tests do not load a production signer, call a service, or authorize actions.
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const {
  webcrypto, generateKeyPairSync, createHash, sign,
} = require('node:crypto');

const PAGE = fs.readFileSync(path.join(__dirname, '..', 'web', 'trust.html'), 'utf8');
const MARKER = '/* ---------- verify-it-yourself: scoped governance evidence ---------- */';
const start = PAGE.indexOf(MARKER);
assert.ok(start >= 0, 'The serving trust page must contain its scoped evidence verifier');
const end = PAGE.indexOf('</script>', start);
assert.ok(end > start, 'The verifier must be inside the serving script');
const SOURCE = PAGE.slice(start, end);

function loadVerifier(extra = {}) {
  const context = {
    crypto: webcrypto,
    TextEncoder,
    TextDecoder,
    atob,
    btoa,
    setTimeout,
    clearTimeout,
    console,
    ...extra,
  };
  vm.createContext(context);
  vm.runInContext(SOURCE, context, { filename: 'web/trust.html:scoped-verifier', timeout: 2000 });
  assert.equal(typeof context.verifyTrustEvidence, 'function');
  return context;
}

const verifier = loadVerifier();
const sha256 = (value) => createHash('sha256').update(value).digest('hex');
const clone = (value) => structuredClone(value);
const key = generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
const publicPem = key.publicKey.export({ type: 'spki', format: 'pem' }).toString();
const fingerprint = sha256(publicPem.trim());
const PAYLOAD_TYPE = 'application/vnd.szl.khipu+json';

// Independent DSSE byte construction; no production canonicalization helper is used.
function pae(type, payload) {
  const typeBytes = Buffer.from(type, 'utf8');
  return Buffer.concat([
    Buffer.from('DSSEv1 ' + typeBytes.length + ' '), typeBytes,
    Buffer.from(' ' + payload.length + ' '), payload,
  ]);
}

function fixture(options = {}) {
  const prompt = options.prompt === undefined ? 'hello' : options.prompt;
  const receipt = {
    organ: 'vertical-general', ns: 'a11oy', seq: 0, action: 'inference',
    payload_digest: 'a'.repeat(64), ts: 1, prev: '0'.repeat(64),
    digest: 'b'.repeat(64), signature: 'DSSE_PLACEHOLDER', chain_verified: true,
  };
  const gates = [
    { gate: 'threat-signature-scan', fired: false, decision: 'allow' },
    { gate: 'pii-egress-guard', fired: false, decision: 'allow' },
  ];
  const statement = {
    statement_type: 'A11OY_GOVERNANCE_STATEMENT_V1',
    schema_version: 1,
    chain: {
      organ: receipt.organ, namespace: receipt.ns, digest: receipt.digest,
      payload_digest: receipt.payload_digest, action: receipt.action,
    },
    actor: {
      actor_type: 'credential', owner_id: 'fixture-operator',
      namespace: 'a11oy', key_id: 'fixture-operator-key', scope: 'vertical:govern',
    },
    policy: {
      policy_id: 'a11oy.vertical-govern.v1', server_action: 'inference',
      decision: 'allow', sensitivity: 'PUBLIC', lambda: 0.95,
      lambda_floor: 0.9, gates: clone(gates),
    },
    content_digests: {
      input_sha256: sha256(Buffer.from(prompt, 'utf8')),
      context_sha256: sha256(Buffer.from('{}', 'utf8')),
    },
    privacy: 'NO_RAW_INPUT_OR_CONTEXT',
    neuro_citations: [],
  };
  if (options.statement) options.statement(statement);
  const payload = options.payloadBytes || Buffer.from(JSON.stringify(statement), 'utf8');
  const payloadType = options.payloadType || PAYLOAD_TYPE;
  const bytes = pae(payloadType, payload);
  const signature = sign('sha256', bytes, {
    key: key.privateKey,
    dsaEncoding: options.format === 'der' ? 'der' : 'ieee-p1363',
  });
  const data = {
    decision: 'allow',
    answer: 'Fixture answer; not covered by the governance statement.',
    served_by: 'fixture-only',
    governance: {
      lambda: 0.95, lambda_floor: 0.9, lambda_pass: true,
      lambda_kind: 'Conjecture 1 (advisory; NOT a theorem)',
      gates: clone(gates),
    },
    receipt,
    dsse: {
      payloadType, payload: payload.toString('base64'), signed: true,
      signatures: [{
        sig: signature.toString('base64'),
        keyid: options.keyid || fingerprint,
      }],
    },
  };
  if (options.data) options.data(data);
  return { data, prompt, payload, bytes, signature, statement };
}

async function check(item, pem = publicPem) {
  const paths = [];
  const report = await verifier.verifyTrustEvidence(item.data, item.prompt, async (url) => {
    paths.push(url);
    return pem;
  });
  return { report, paths };
}

function assertBoundaries(report) {
  assert.equal(report.chain_integrity, 'NOT_CHECKED');
  assert.equal(report.answer_binding, 'NOT_COVERED');
  assert.equal(report.freshness, 'NOT_ESTABLISHED');
  assert.equal(report.signer_trust, 'SAME_ORIGIN_KEY_NOT_INDEPENDENTLY_PINNED');
  assert.equal(report.execution_authority, 'NOT_ESTABLISHED');
}

// Malformed evidence can throw or return an explicit refusal; it must not pass.
async function assertRefused(item, pem = publicPem) {
  let outcome;
  try {
    outcome = (await check(item, pem)).report;
  } catch (error) {
    assert.equal(typeof error.message, 'string');
    assert.ok(error.message.length > 0);
    return;
  }
  assert.notEqual(outcome.verdict, 'PARTIAL', JSON.stringify(outcome));
  assert.ok(['MISMATCH', 'UNSUPPORTED', 'UNSIGNED'].includes(outcome.verdict));
  assertBoundaries(outcome);
}

test('valid raw P-256 signature yields only scoped partial evidence', async () => {
  const item = fixture();
  const { report, paths } = await check(item);
  assert.equal(report.verdict, 'PARTIAL');
  assert.equal(report.signature, 'VALID');
  assert.equal(report.key_identity, 'MATCH');
  assert.equal(report.input_binding, 'MATCH');
  assert.equal(report.receipt_reference_binding, 'MATCH');
  assert.equal(report.policy_binding, 'MATCH');
  assert.equal(report.payload_sha256, sha256(item.payload));
  assert.equal(report.public_key_sha256, fingerprint);
  assert.deepEqual(paths, ['/cosign.pub']);
  assertBoundaries(report);
});

test('valid DER P-256 signature verifies the same limited statement', async () => {
  const { report } = await check(fixture({ format: 'der' }));
  assert.equal(report.verdict, 'PARTIAL');
  assert.equal(report.signature, 'VALID');
  assertBoundaries(report);
});

test('public inference with dsse null is unsigned without a key fetch', async () => {
  const item = fixture({ data: (data) => { data.dsse = null; } });
  const { report, paths } = await check(item);
  assert.equal(report.verdict, 'UNSIGNED');
  assert.equal(report.signature, 'UNSIGNED');
  assert.equal(report.key_identity, 'NOT_CHECKED');
  assert.deepEqual(paths, []);
  assertBoundaries(report);
});

test('explicit unsigned envelope makes no key fetch or chain-valid claim', async () => {
  const item = fixture({ data: (data) => {
    data.dsse.signed = false;
    data.dsse.signatures = [];
  } });
  const { report, paths } = await check(item);
  assert.equal(report.verdict, 'UNSIGNED');
  assert.equal(report.signature, 'UNSIGNED');
  assert.deepEqual(paths, []);
  assertBoundaries(report);
});

test('demo alias stays explicitly demo-scoped with its fixed key path', async () => {
  const { report, paths } = await check(fixture({ keyid: 'demo-signing-key' }));
  assert.equal(report.signature, 'VALID');
  assert.equal(report.key_identity, 'DEMO_ALIAS');
  assert.equal(report.verdict, 'PARTIAL');
  assert.deepEqual(paths, ['/demo-cosign.pub']);
  assertBoundaries(report);
});

test('supported legacy alias does not gain independently pinned trust', async () => {
  const { report, paths } = await check(fixture({ keyid: 'szlholdings-cosign' }));
  assert.equal(report.signature, 'VALID');
  assert.equal(report.key_identity, 'LEGACY_ALIAS');
  assert.equal(report.verdict, 'PARTIAL');
  assert.deepEqual(paths, ['/cosign.pub']);
  assertBoundaries(report);
});

test('envelope metadata cannot select an arbitrary public-key URL', async () => {
  const item = fixture({ data: (data) => {
    data.dsse.verify_key_url = 'https://attacker.invalid/key.pem';
    data.dsse._signed_at = '2099-01-01T00:00:00Z';
  } });
  const { report, paths } = await check(item);
  assert.equal(report.verdict, 'PARTIAL');
  assert.deepEqual(paths, ['/cosign.pub']);
  assertBoundaries(report);
});

test('substituted key ID cannot pass even with a valid signature', async () => {
  const { report } = await check(fixture({ keyid: '0'.repeat(64) }));
  assert.equal(report.verdict, 'MISMATCH');
  assert.equal(report.key_identity, 'MISMATCH');
  assertBoundaries(report);
});

test('arbitrary key alias is refused', async () => {
  await assertRefused(fixture({ keyid: 'someone-says-trusted' }));
});

test('signature made by another key is refused', async () => {
  const other = generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
  const pem = other.publicKey.export({ type: 'spki', format: 'pem' }).toString();
  await assertRefused(fixture(), pem);
});

test('a payload-byte mutation invalidates the signature', async () => {
  const item = fixture();
  const changed = Buffer.from(item.payload);
  const position = changed.indexOf(Buffer.from('fixture-operator'));
  changed[position] = 'F'.charCodeAt(0);
  item.data.dsse.payload = changed.toString('base64');
  const { report } = await check(item);
  assert.equal(report.verdict, 'MISMATCH');
  assert.equal(report.signature, 'INVALID');
  assertBoundaries(report);
});

test('a raw-signature byte mutation invalidates the signature', async () => {
  const item = fixture();
  const changed = Buffer.from(item.signature);
  changed[12] ^= 1;
  item.data.dsse.signatures[0].sig = changed.toString('base64');
  const { report } = await check(item);
  assert.equal(report.verdict, 'MISMATCH');
  assert.equal(report.signature, 'INVALID');
});

for (const field of ['digest', 'payload_digest', 'organ', 'ns', 'action']) {
  test('valid signature does not cover a substituted receipt reference: ' + field, async () => {
    const item = fixture({ data: (data) => {
      data.receipt[field] = field.includes('digest') ? 'c'.repeat(64) : 'different';
    } });
    const { report } = await check(item);
    assert.equal(report.verdict, 'MISMATCH');
    assert.equal(report.receipt_reference_binding, 'MISMATCH');
    assertBoundaries(report);
  });
}

test('digest suffix is not accepted as exact reference agreement', async () => {
  const item = fixture({ data: (data) => { data.receipt.digest += 'extra'; } });
  await assertRefused(item);
});

test('digest prefix is not accepted as exact reference agreement', async () => {
  const item = fixture({ data: (data) => { data.receipt.payload_digest = data.receipt.payload_digest.slice(0, 63); } });
  await assertRefused(item);
});

test('signed statement from another prompt is not bound to this request', async () => {
  const item = fixture();
  item.prompt = 'a different prompt';
  const { report } = await check(item);
  assert.equal(report.verdict, 'MISMATCH');
  assert.equal(report.input_binding, 'MISMATCH');
});

test('valid signature with a different signed context is not this public request', async () => {
  await assertRefused(fixture({ statement: (statement) => {
    statement.content_digests.context_sha256 = sha256('{"different":true}');
  } }));
});

for (const [name, mutate] of [
  ['response decision', (data) => { data.decision = 'deny'; }],
  ['lambda', (data) => { data.governance.lambda = 0.2; }],
  ['lambda floor', (data) => { data.governance.lambda_floor = 0.8; }],
  ['gate decision', (data) => { data.governance.gates[0].decision = 'deny'; }],
  ['gate fired flag', (data) => { data.governance.gates[0].fired = true; }],
  ['gate name', (data) => { data.governance.gates[0].gate = 'other'; }],
  ['missing gate', (data) => { data.governance.gates.pop(); }],
]) {
  test('valid signature rejects mismatching policy projection: ' + name, async () => {
    const { report } = await check(fixture({ data: mutate }));
    assert.equal(report.verdict, 'MISMATCH');
    assert.equal(report.policy_binding, 'MISMATCH');
    assertBoundaries(report);
  });
}

for (const [name, mutate] of [
  ['string lambda', (statement) => { statement.policy.lambda = '0.95'; }],
  ['string boolean', (statement) => { statement.policy.gates[0].fired = 'false'; }],
  ['wrong actor type', (statement) => { statement.actor.actor_type = 'anonymous'; }],
  ['wrong actor scope', (statement) => { statement.actor.scope = 'arbitrary:write'; }],
  ['wrong actor namespace', (statement) => { statement.actor.namespace = 'other'; }],
  ['non-public classification', (statement) => { statement.policy.sensitivity = 'SECRET'; }],
  ['wrong policy ID', (statement) => { statement.policy.policy_id = 'other'; }],
  ['wrong server action', (statement) => { statement.policy.server_action = 'execute'; }],
  ['missing input digest', (statement) => { delete statement.content_digests.input_sha256; }],
]) {
  test('signed but invalid native statement is refused: ' + name, async () => {
    await assertRefused(fixture({ statement: mutate }));
  });
}

test('unknown signed statement is unsupported, not a verified response', async () => {
  const { report } = await check(fixture({ statement: (statement) => {
    statement.statement_type = 'OTHER_STATEMENT';
  } }));
  assert.equal(report.verdict, 'UNSUPPORTED');
  assertBoundaries(report);
});

test('changing the answer never turns governance signature into answer proof', async () => {
  const item = fixture({ data: (data) => { data.answer = 'An entirely different answer.'; } });
  const { report } = await check(item);
  assert.equal(report.verdict, 'PARTIAL');
  assert.equal(report.answer_binding, 'NOT_COVERED');
  assertBoundaries(report);
});

test('server chain claim is not promoted into browser chain verification', async () => {
  const item = fixture({ data: (data) => { data.receipt.chain_verified = true; } });
  const { report } = await check(item);
  assert.equal(report.chain_integrity, 'NOT_CHECKED');
  assert.equal(report.answer_binding, 'NOT_COVERED');
});

test('missing payload type is not silently supplied', async () => {
  await assertRefused(fixture({ data: (data) => { delete data.dsse.payloadType; } }));
});

test('a signed unrecognized payload type is refused', async () => {
  await assertRefused(fixture({ payloadType: 'application/example+json' }));
});

test('malformed Base64 is refused', async () => {
  await assertRefused(fixture({ data: (data) => { data.dsse.payload = '%%%'; } }));
});

test('extra Base64 padding is refused', async () => {
  await assertRefused(fixture({ data: (data) => { data.dsse.payload += '=='; } }));
});

test('invalid UTF-8 cannot become a supported signed statement', async () => {
  await assertRefused(fixture({ payloadBytes: Buffer.from([0xc3, 0x28]) }));
});

test('invalid JSON cannot become a supported signed statement', async () => {
  await assertRefused(fixture({ payloadBytes: Buffer.from('{"statement_type":') }));
});

test('oversized signed payload is bounded', async () => {
  await assertRefused(fixture({ payloadBytes: Buffer.from(' '.repeat(1024 * 1024)) }));
});

test('valid DER with trailing bytes is refused', async () => {
  const item = fixture({ format: 'der' });
  item.data.dsse.signatures[0].sig = Buffer.concat([item.signature, Buffer.from([0])]).toString('base64');
  await assertRefused(item);
});

test('truncated DER is refused', async () => {
  const item = fixture({ format: 'der' });
  item.data.dsse.signatures[0].sig = item.signature.subarray(0, item.signature.length - 1).toString('base64');
  await assertRefused(item);
});

test('raw signature starting with DER tag byte is still recognized as raw', async () => {
  const item = fixture();
  let candidate;
  for (let index = 0; index < 8192; index++) {
    const result = sign('sha256', item.bytes, { key: key.privateKey, dsaEncoding: 'ieee-p1363' });
    if (result[0] === 0x30) { candidate = result; break; }
  }
  assert.ok(candidate, 'Could not obtain a fixture raw signature beginning with 0x30');
  item.data.dsse.signatures[0].sig = candidate.toString('base64');
  const { report } = await check(item);
  assert.equal(report.verdict, 'PARTIAL');
  assert.equal(report.signature, 'VALID');
});

test('key retrieval failure cannot preserve a partial success', async () => {
  const item = fixture();
  await assert.rejects(
    verifier.verifyTrustEvidence(item.data, item.prompt, async () => { throw new Error('key unavailable'); }),
  );
});


function uiHarness(fetchImpl, timers = {}) {
  const elements = new Map();
  function element() {
    return {
      disabled: false, textContent: '', style: {}, children: [],
      replaceChildren() { this.children = []; this.textContent = ''; },
      appendChild(child) { this.children.push(child); return child; },
    };
  }
  for (const id of ['tv-run', 'tv-verdict', 'tv-out', 'tv-status']) elements.set(id, element());
  const calls = [];
  const context = loadVerifier({
    AbortController,
    document: { createElement: element },
    $: (id) => elements.get(id),
    fetch: async (url, options) => {
      calls.push({ url, options });
      return fetchImpl(url, options);
    },
    ...timers,
  });
  return { context, calls, elements, get: (id) => elements.get(id) };
}

function jsonResponse(value, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json; charset=utf-8' } });
}

test('serving UI makes one anonymous bounded inference and accurately renders unsigned evidence', async () => {
  const item = fixture({ data: (data) => { data.dsse = null; } });
  const ui = uiHarness(async () => jsonResponse(item.data));
  await ui.context.trustVerify();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.calls[0].url, '/api/a11oy/v1/govern/infer');
  assert.equal(ui.calls[0].options.method, 'POST');
  assert.equal(ui.calls[0].options.credentials, 'omit');
  assert.equal(ui.calls[0].options.redirect, 'error');
  assert.equal(ui.calls[0].options.cache, 'no-store');
  assert.deepEqual(JSON.parse(ui.calls[0].options.body), { prompt: 'hello', vertical: 'general', declared: 'PUBLIC' });
  const report = JSON.parse(ui.get('tv-out').textContent);
  assert.equal(report.verdict, 'UNSIGNED');
  assertBoundaries(report);
  assert.equal(ui.get('tv-verdict').children.length, 1);
  assert.match(ui.get('tv-verdict').children[0].textContent, /UNSIGNED/);
  assert.equal(ui.get('tv-run').disabled, false);
});

test('serving UI does not label a valid signature plus mismatched references as verified', async () => {
  const item = fixture({ data: (data) => { data.receipt.digest = 'c'.repeat(64); } });
  const ui = uiHarness(async (url) => url === '/cosign.pub'
    ? new Response(publicPem)
    : jsonResponse(item.data));
  await ui.context.trustVerify();
  assert.equal(ui.calls.length, 2);
  assert.equal(JSON.parse(ui.get('tv-out').textContent).verdict, 'MISMATCH');
  const banner = ui.get('tv-verdict').children[0];
  assert.match(banner.textContent, /MISMATCH/);
  assert.match(banner.className, /fail/);
  assert.equal(ui.get('tv-run').disabled, false);
});

test('non-JSON response clears old success and restores the control without retry', async () => {
  const ui = uiHarness(async () => new Response('<html>not an API response</html>', {
    status: 200, headers: { 'content-type': 'text/html' },
  }));
  ui.get('tv-verdict').children = [{ textContent: 'OLD SUCCESS' }];
  ui.get('tv-out').textContent = 'OLD SUCCESS';
  await ui.context.trustVerify();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.get('tv-verdict').children.length, 0);
  assert.equal(ui.get('tv-out').textContent, '');
  assert.match(ui.get('tv-status').textContent, /NON_JSON_RESPONSE/);
  assert.equal(ui.get('tv-run').disabled, false);
});

test('HTTP inference refusal does not fetch a key or retry', async () => {
  const ui = uiHarness(async () => jsonResponse({ error: 'unavailable' }, 503));
  await ui.context.trustVerify();
  assert.equal(ui.calls.length, 1);
  assert.match(ui.get('tv-status').textContent, /INFERENCE_HTTP_503/);
  assert.equal(ui.get('tv-verdict').children.length, 0);
  assert.equal(ui.get('tv-run').disabled, false);
});

test('invalid response JSON leaves no stale verification banner', async () => {
  const ui = uiHarness(async () => new Response('{"incomplete":', {
    headers: { 'content-type': 'application/json' },
  }));
  await ui.context.trustVerify();
  assert.equal(ui.calls.length, 1);
  assert.match(ui.get('tv-status').textContent, /Evidence unavailable/);
  assert.equal(ui.get('tv-verdict').children.length, 0);
  assert.equal(ui.get('tv-run').disabled, false);
});

test('response stream is bounded before parsing', async () => {
  const ui = uiHarness(async () => new Response(' '.repeat(262145), {
    headers: { 'content-type': 'application/json' },
  }));
  await ui.context.trustVerify();
  assert.equal(ui.calls.length, 1);
  assert.match(ui.get('tv-status').textContent, /RESPONSE_TOO_LARGE/);
  assert.equal(ui.get('tv-run').disabled, false);
});

test('public-key HTTP failure does not become a signature verdict', async () => {
  const item = fixture();
  const ui = uiHarness(async (url) => url === '/cosign.pub'
    ? new Response('not available', { status: 503 })
    : jsonResponse(item.data));
  await ui.context.trustVerify();
  assert.equal(ui.calls.length, 2);
  assert.match(ui.get('tv-status').textContent, /PUBLIC_KEY_HTTP_503/);
  assert.equal(ui.get('tv-verdict').children.length, 0);
  assert.equal(ui.get('tv-run').disabled, false);
});

test('public-key response stream is bounded', async () => {
  const item = fixture();
  const ui = uiHarness(async (url) => url === '/cosign.pub'
    ? new Response('x'.repeat(8193))
    : jsonResponse(item.data));
  await ui.context.trustVerify();
  assert.equal(ui.calls.length, 2);
  assert.match(ui.get('tv-status').textContent, /RESPONSE_TOO_LARGE/);
  assert.equal(ui.get('tv-verdict').children.length, 0);
  assert.equal(ui.get('tv-run').disabled, false);
});

test('double submission cannot send concurrent inference requests', async () => {
  const item = fixture({ data: (data) => { data.dsse = null; } });
  let release;
  const waiting = new Promise((resolve) => { release = resolve; });
  const ui = uiHarness(async () => { await waiting; return jsonResponse(item.data); });
  const first = ui.context.trustVerify();
  await ui.context.trustVerify();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.get('tv-run').disabled, true);
  release();
  await first;
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.get('tv-run').disabled, false);
});

test('deadline aborts once, reports uncertainty, and cannot paint a late success', async () => {
  const item = fixture({ data: (data) => { data.dsse = null; } });
  let release, observedSignal, deadlineMs;
  const pending = new Promise((resolve) => { release = resolve; });
  const ui = uiHarness(async (_url, options) => {
    observedSignal = options.signal;
    await pending; // Intentionally emulate transport that resolves after abort.
    return jsonResponse(item.data);
  }, {
    setTimeout(callback, milliseconds) {
      deadlineMs = milliseconds;
      queueMicrotask(callback);
      return 1;
    },
    clearTimeout() {},
  });
  await ui.context.trustVerify();
  assert.equal(deadlineMs, 45000);
  assert.equal(observedSignal.aborted, true);
  assert.equal(ui.calls.length, 1);
  assert.match(ui.get('tv-status').textContent, /OUTCOME_UNCERTAIN_TIMEOUT/);
  assert.equal(ui.get('tv-run').disabled, false);
  assert.equal(ui.get('tv-verdict').children.length, 0);
  const status = ui.get('tv-status').textContent;
  release();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(ui.get('tv-status').textContent, status);
  assert.equal(ui.get('tv-verdict').children.length, 0);
  assert.equal(ui.calls.length, 1);
});
