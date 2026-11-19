// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const moduleSource = await readFile(new URL('../pages/training-observations.js', import.meta.url), 'utf8');
const {
  OBSERVATION_ENDPOINT, MAX_OBSERVATION_BYTES, validateTrainingObservation,
  candidateObservationState, readBoundedObservationJson, bootTrainingObservations,
} = await import('data:text/javascript;base64,' + Buffer.from(moduleSource).toString('base64'));

const EVALUATED = Date.parse('2026-01-01T12:00:00Z');
const iso = milliseconds => new Date(milliseconds).toISOString();
const clone = value => structuredClone(value);
function fixture() {
  return {
    schema: 'szl.training-observation-view/v1', available: true, state: 'OBSERVED',
    evaluatedAt: iso(EVALUATED), sourceObservedAt: iso(EVALUATED - 30000),
    reportSha256: 'a'.repeat(64), sourceKind: 'LOCAL_FILE_OBSERVATION',
    signatureVerified: false, producerAuthenticated: false, durableRetentionVerified: false,
    trainingCompleteVerified: false, promotionAuthorized: false, trainerProcessLivenessVerified: false,
    authority: {training: false, inference: false, publication: false, promotion: false,
      deletion: false, toolExecution: false}, returned: 1,
    candidates: [{id: 'SZLHOLDINGS/fixture-candidate', producerState: 'TERMINAL_METADATA_PRESENT',
      state: 'OBSERVED', observedAt: iso(EVALUATED - 60000), expiresAt: iso(EVALUATED + 600000),
      ageSeconds: 60, hubRevision: 'b'.repeat(40), checkpointStep: 100, targetSteps: 100,
      trainerGlobalStep: 100, trainerMaxSteps: 100, trainerStateSha256: 'c'.repeat(64),
      trainerStateIntegrityReported: 'PINNED_OBJECT_BYTES_VERIFIED',
      finalFiles: {adapter: true, config: true, tokenizer: true}, providerReadyCount: 1,
      trainingCompleteVerified: false, promotionAuthorized: false, trainerProcessLivenessVerified: false,
      evaluationVerified: false, artifactIntegrityVerified: false, proofVerified: false}],
  };
}
const response = value => new Response(JSON.stringify(value), {headers: {'Content-Type': 'application/json'}});

test('accepts the bounded read-only contract while preserving false verification flags', () => {
  const value = fixture();
  assert.equal(validateTrainingObservation(value), value);
  assert.equal(value.candidates[0].trainingCompleteVerified, false);
});

test('rejects malformed, inconsistent and unavailable success payloads', () => {
  const mutations = [
    value => { value.schema = 'unknown/v9'; },
    value => { value.available = false; },
    value => { value.returned = 2; },
    value => { value.returned = 0; value.candidates = []; },
    value => { value.returned = 33; value.candidates = Array.from({length: 33}, () => clone(value.candidates[0])); },
    value => { value.candidates.push(clone(value.candidates[0])); value.returned++; },
    value => { value.reportSha256 = 'bad'; },
    value => { value.sourceKind = 'REMOTE_LIVE_ATTESTATION'; },
    value => { value.evaluatedAt = '2026-02-31T12:00:00Z'; },
    value => { value.candidates[0].observedAt = '2026-01-01T11:59:00'; },
    value => { value.candidates[0].expiresAt = iso(EVALUATED + 660001); },
    value => { value.candidates[0].ageSeconds = Infinity; },
    value => { value.candidates[0].ageSeconds = 0; },
    value => { value.candidates[0].producerState = '<script>alert(1)</script>'; },
    value => { value.candidates[0].producerState = 'TRAINING_VERIFIED'; },
    value => { value.candidates[0].id = 'SZLHOLDINGS/../fixture'; },
    value => { value.candidates[0].targetSteps = 0; },
    value => { value.candidates[0].checkpointStep = true; },
    value => { value.candidates[0].trainerGlobalStep = 99; },
    value => { value.candidates[0].trainerStateSha256 = null; },
    value => { value.candidates[0].trainerStateIntegrityReported = 'INDEPENDENTLY_VERIFIED'; },
    value => { value.candidates[0].finalFiles.adapter = 'true'; },
    value => { value.candidates[0].providerReadyCount = Number.MAX_SAFE_INTEGER + 1; },
    value => { value.candidates[0].state = 'VERIFIED'; },
    value => { value.state = 'STALE'; },
  ];
  for (const mutate of mutations) {
    const value = fixture(); mutate(value);
    assert.throws(() => validateTrainingObservation(value), /read-only contract/);
  }
  for (const value of [null, [], true, {}, 'payload'])
    assert.throws(() => validateTrainingObservation(value), /read-only contract/);
});

test('rejects every false-authority or fabricated verification upgrade', () => {
  for (const field of Object.keys(fixture().authority)) {
    const value = fixture(); value.authority[field] = true;
    assert.throws(() => validateTrainingObservation(value), /read-only contract/);
  }
  const extra = fixture(); extra.authority.extra = false;
  assert.throws(() => validateTrainingObservation(extra), /read-only contract/);
  for (const field of ['signatureVerified', 'producerAuthenticated', 'durableRetentionVerified',
    'trainingCompleteVerified', 'promotionAuthorized', 'trainerProcessLivenessVerified']) {
    const value = fixture(); value[field] = true;
    assert.throws(() => validateTrainingObservation(value), /read-only contract/);
  }
  for (const field of ['trainingCompleteVerified', 'promotionAuthorized', 'trainerProcessLivenessVerified',
    'evaluationVerified', 'artifactIntegrityVerified', 'proofVerified']) {
    const value = fixture(); value.candidates[0][field] = true;
    assert.throws(() => validateTrainingObservation(value), /read-only contract/);
    delete value.candidates[0][field];
    assert.throws(() => validateTrainingObservation(value), /read-only contract/);
  }
});

test('candidate expiry is absolute and terminal target metadata cannot verify completion', () => {
  const value = validateTrainingObservation(fixture()), row = value.candidates[0];
  assert.equal(row.checkpointStep, row.targetSteps);
  assert.equal(candidateObservationState(value, row, EVALUATED), 'OBSERVED');
  assert.equal(candidateObservationState(value, row, Date.parse(row.expiresAt) - 1), 'OBSERVED');
  assert.equal(candidateObservationState(value, row, Date.parse(row.expiresAt)), 'STALE');
  value.evaluatedAt = iso(Date.parse(row.expiresAt) + 1);
  assert.equal(candidateObservationState(value, row, Date.parse(row.expiresAt) + 1), 'STALE');
  assert.equal(row.trainingCompleteVerified, false);
  assert.equal(row.promotionAuthorized, false);
});

test('clock discrepancies remain explicit and unavailable candidates require PARTIAL', () => {
  const value = fixture(), row = value.candidates[0];
  assert.equal(candidateObservationState(value, row, EVALUATED - 1), 'CLOCK_SKEW');
  assert.equal(candidateObservationState(value, row, EVALUATED, true), 'CLOCK_SKEW');
  row.producerState = 'UNAVAILABLE'; row.state = 'UNAVAILABLE';
  assert.throws(() => validateTrainingObservation(value), /read-only contract/);
  value.state = 'PARTIAL'; validateTrainingObservation(value);
  assert.equal(candidateObservationState(value, row, EVALUATED), 'UNAVAILABLE');
});

test('valid server observations retain microsecond precision at expiry and clock boundaries', () => {
  const value = fixture(), row = value.candidates[0];
  row.observedAt = '2026-01-01T11:59:00.000200Z';
  row.expiresAt = '2026-01-01T12:10:00.000200Z';
  value.evaluatedAt = '2026-01-01T12:10:00.000100Z'; row.ageSeconds = 660;
  assert.equal(validateTrainingObservation(value), value);
  value.evaluatedAt = '2026-01-01T12:00:00.000100Z';
  value.sourceObservedAt = '2026-01-01T12:00:00.000200Z';
  value.state = row.state = 'CLOCK_SKEW'; row.ageSeconds = 60;
  assert.equal(validateTrainingObservation(value), value);
});

test('bounded JSON rejects excess bytes, invalid UTF-8, invalid JSON and unexpected content', async () => {
  assert.deepEqual(await readBoundedObservationJson(response({fixture: true})), {fixture: true});
  await assert.rejects(readBoundedObservationJson(new Response('x', {
    headers: {'Content-Type': 'text/html'},
  })), /not JSON/);
  await assert.rejects(readBoundedObservationJson(new Response('{}', {
    headers: {'Content-Type': 'application/json', 'Content-Length': String(MAX_OBSERVATION_BYTES + 1)},
  })), /size limit/);
  await assert.rejects(readBoundedObservationJson(new Response('x'.repeat(MAX_OBSERVATION_BYTES + 1), {
    headers: {'Content-Type': 'application/json'},
  })), /size limit/);
  await assert.rejects(readBoundedObservationJson(new Response(new Uint8Array([0xff]), {
    headers: {'Content-Type': 'application/json'},
  })), /invalid JSON/);
  await assert.rejects(readBoundedObservationJson(new Response('{', {
    headers: {'Content-Type': 'application/json'},
  })), /invalid JSON/);
});

class Element extends EventTarget {
  constructor(tag = 'div') { super(); this.tagName = tag; this.children = []; this._text = '';
    this.value = ''; this.disabled = false; this.hidden = false; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(' '); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this._text = ''; this.children = children; }
}
class Document extends EventTarget {
  constructor() {
    super(); this.defaultView = new EventTarget(); this.visibilityState = 'visible';
    this.elements = new Map([['training-observations', new Element()]]);
    for (const id of ['tenant', 'token', 'load', 'disconnect', 'status', 'results', 'summary', 'cards',
      'evaluated', 'source-observed', 'report-hash'])
      this.elements.set(`training-observation-${id}`, new Element());
  }
  getElementById(id) { return this.elements.get(id) || null; }
  createElement(tag) { return new Element(tag); }
}
function harness(fetcher) {
  const document = new Document(), timers = new Map(); let nextTimer = 0;
  const clock = {wall: EVALUATED, monotonic: 1000};
  const ui = bootTrainingObservations({document, fetch: fetcher,
    now: () => clock.wall, monotonic: () => clock.monotonic,
    setTimer: (fn, delay) => { const id = ++nextTimer; timers.set(id, {fn, delay}); return id; },
    clearTimer: id => timers.delete(id),
  });
  const element = name => document.getElementById(`training-observation-${name}`);
  const enter = () => { element('tenant').value = 'fixture-tenant'; element('token').value = 'fixture-token'; };
  return {document, timers, clock, ui, element, enter};
}

test('manual GET uses same-origin endpoint with explicit headers and no persisted credentials', async () => {
  const calls = [], h = harness(async (url, options) => { calls.push({url, options}); return response(fixture()); });
  assert.equal(calls.length, 0);
  h.enter(); const pending = h.ui.load();
  assert.equal(h.element('token').value, '');
  await pending;
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, OBSERVATION_ENDPOINT);
  assert.deepEqual(calls[0].options.headers, {Accept: 'application/json',
    Authorization: 'Bearer fixture-token', 'X-A11oy-Tenant': 'fixture-tenant'});
  for (const [key, value] of Object.entries({method: 'GET', cache: 'no-store', credentials: 'omit', redirect: 'error'}))
    assert.equal(calls[0].options[key], value);
  assert.equal(h.element('results').hidden, false);
  assert.match(h.element('cards').textContent, /Training completion: unverified/);
  assert.match(h.element('cards').textContent, /Promotion: not authorized/);
  assert.match(h.element('cards').textContent, /Target steps declared 100/);
  assert.match(h.element('cards').children[0].children.find(element =>
    element.className === 'training-observation-progress').textContent,
  /Checkpoint step reported: 100 · Target declared: 100/);
  await h.ui.load();
  assert.equal(calls.length, 1, 'empty token cannot trigger another private fetch');
  assert.equal(h.element('results').hidden, true);
  h.ui.dispose();
});

test('prominent checkpoint metadata preserves overshoot and missing checkpoint without claiming completion', async () => {
  const overshoot = fixture(), row = overshoot.candidates[0];
  row.checkpointStep = row.trainerGlobalStep = 101; row.producerState = 'TERMINAL_STEP_OVERSHOOT';
  const missing = fixture(), absent = missing.candidates[0];
  absent.checkpointStep = absent.trainerGlobalStep = absent.trainerMaxSteps = absent.trainerStateSha256 = null;
  absent.trainerStateIntegrityReported = 'UNAVAILABLE'; absent.producerState = 'NO_CHECKPOINT_OBSERVED';
  for (const [value, expected] of [[overshoot, 'Checkpoint step reported: 101 · Target declared: 100.'],
    [missing, 'Checkpoint unavailable · Target declared: 100.']]) {
    const h = harness(async () => response(value)); h.enter(); await h.ui.load();
    const progress = h.element('cards').children[0].children.find(element =>
      element.className === 'training-observation-progress');
    assert.equal(progress.textContent, expected);
    assert.match(h.element('cards').textContent, /Training completion: unverified/);
    h.ui.dispose();
  }
});

test('failure and access denial clear previously displayed private observations immediately', async () => {
  for (const failure of [401, 403, 503, 'invalid']) {
    let calls = 0;
    const h = harness(async () => ++calls === 1 ? response(fixture())
      : failure === 'invalid' ? response({schema: 'unknown'}) : new Response('', {status: failure}));
    h.enter(); await h.ui.load(); assert.equal(h.element('cards').children.length, 1);
    h.enter(); const request = h.ui.load();
    assert.equal(h.element('cards').children.length, 0);
    assert.equal(h.element('report-hash').textContent, 'Unavailable');
    await request;
    assert.equal(h.element('results').hidden, true);
    assert.match(h.element('status').textContent, /No private observations are displayed/);
    h.ui.dispose();
  }
});

test('editing tenant or token clears old observations without erasing the new input', async () => {
  for (const name of ['tenant', 'token']) {
    const h = harness(async () => response(fixture())); h.enter(); await h.ui.load();
    h.element(name).value = 'replacement-fixture'; h.element(name).dispatchEvent(new Event('input'));
    assert.equal(h.element('cards').children.length, 0);
    assert.equal(h.element('results').hidden, true);
    assert.equal(h.element('report-hash').textContent, 'Unavailable');
    assert.equal(h.element(name).value, 'replacement-fixture');
    assert.match(h.element('status').textContent, /Access fields changed/);
    h.ui.dispose();
  }
});

test('fresh display expires locally at deadline and on return to the visible page', async () => {
  for (const trigger of ['timer', 'visibility']) {
    let calls = 0; const h = harness(async () => { calls++; return response(fixture()); });
    h.enter(); await h.ui.load();
    assert.match(h.element('cards').textContent, /within reported time window/);
    h.clock.wall += 600000; h.clock.monotonic += 600000;
    if (trigger === 'timer') [...h.timers.values()][0].fn();
    else h.document.dispatchEvent(new Event('visibilitychange'));
    assert.match(h.element('cards').textContent, /Expired observation/);
    assert.equal(calls, 1, 'local freshness checks must not refetch private data');
    h.clock.wall -= 700000;
    h.document.dispatchEvent(new Event('visibilitychange'));
    assert.doesNotMatch(h.element('cards').textContent, /within reported time window/);
    assert.match(h.element('cards').textContent, /Clock discrepancy/);
    h.ui.dispose();
  }
});

test('disconnect and pagehide clear observations, fields and pending generations', async () => {
  let finish;
  const h = harness(() => new Promise(resolve => { finish = resolve; }));
  h.enter(); const request = h.ui.load(); h.ui.disconnect();
  finish(response(fixture())); await request;
  assert.equal(h.element('results').hidden, true);
  assert.equal(h.element('cards').children.length, 0);
  assert.equal(h.element('tenant').value, '');
  assert.equal(h.element('token').value, '');
  h.enter(); h.document.defaultView.dispatchEvent(new Event('pagehide'));
  assert.equal(h.element('tenant').value, '');
  assert.equal(h.element('token').value, '');
  assert.equal(h.timers.size, 0);
  h.ui.dispose();
});

test('an older response cannot overwrite a later manual request', async () => {
  const pending = [], h = harness(() => new Promise(resolve => pending.push(resolve)));
  h.enter(); const first = h.ui.load(); h.enter(); const second = h.ui.load();
  const newer = fixture(); newer.reportSha256 = 'd'.repeat(64);
  pending[1](response(newer)); await second;
  pending[0](response(fixture())); await first;
  assert.equal(h.element('report-hash').textContent, 'd'.repeat(64));
  h.ui.dispose();
});

test('timeout clears data even when the JSON body stalls', async () => {
  const body = new ReadableStream({start() {}});
  const h = harness(async () => new Response(body, {headers: {'Content-Type': 'application/json'}}));
  h.enter(); const request = h.ui.load();
  await Promise.resolve(); await Promise.resolve();
  const timeout = [...h.timers.values()].find(timer => timer.delay === 15000);
  assert.ok(timeout); timeout.fn(); await request;
  assert.equal(h.element('results').hidden, true);
  assert.match(h.element('status').textContent, /timed out/);
  h.ui.dispose();
});

test('partial reports and browser clock discrepancies are prominent without verified completion', async () => {
  const value = fixture(); value.state = 'PARTIAL';
  value.candidates[0].state = 'UNAVAILABLE'; value.candidates[0].producerState = 'UNAVAILABLE';
  const h = harness(async () => response(value));
  h.enter(); await h.ui.load();
  assert.match(h.element('status').textContent, /Report contains unavailable observations/);
  assert.match(h.element('cards').textContent, /Observation unavailable/);
  h.ui.dispose();
  const skew = harness(async () => response(fixture())); skew.clock.wall--;
  skew.enter(); await skew.ui.load();
  assert.match(skew.element('status').textContent, /Clock discrepancy/);
  assert.match(skew.element('cards').textContent, /freshness unknown/);
  skew.ui.dispose();
});

test('module has no persistent credential storage, HTML insertion, or producer-supplied navigation', async () => {
  const source = await readFile(new URL('../pages/training-observations.js', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /localStorage|sessionStorage|indexedDB|document\.cookie/);
  assert.doesNotMatch(source, /innerHTML|outerHTML|insertAdjacentHTML|\.href\s*=/);
});
