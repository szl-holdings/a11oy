/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
 * Restricted, manual observation reader. No execution or promotion authority.
 */
export const OBSERVATION_ENDPOINT = '/api/a11oy/v1/models/training-observations';
export const MAX_OBSERVATION_BYTES = 1024 * 1024;
const SCHEMA = 'szl.training-observation-view/v1';
const AUTHORITY = ['training', 'inference', 'publication', 'promotion', 'deletion', 'toolExecution'];
const ROOT_UNVERIFIED = ['signatureVerified', 'producerAuthenticated', 'durableRetentionVerified',
  'trainingCompleteVerified', 'promotionAuthorized', 'trainerProcessLivenessVerified'];
const ROW_UNVERIFIED = ['trainingCompleteVerified', 'promotionAuthorized', 'trainerProcessLivenessVerified',
  'evaluationVerified', 'artifactIntegrityVerified', 'proofVerified'];
const STATES = ['OBSERVED', 'STALE', 'CLOCK_SKEW', 'UNAVAILABLE'];
const PRODUCER_STATES = ['UNAVAILABLE', 'NO_CHECKPOINT_OBSERVED', 'TARGET_CONTRACT_MISMATCH',
  'TERMINAL_STEP_OVERSHOOT', 'CHECKPOINT_PROGRESS_OBSERVED', 'TERMINAL_METADATA_PRESENT',
  'TARGET_CHECKPOINT_WITHOUT_FINAL_BUNDLE'];
const STATE_LABEL = {
  OBSERVED: 'Observation within reported time window',
  STALE: 'Expired observation',
  CLOCK_SKEW: 'Clock discrepancy · freshness unknown',
  UNAVAILABLE: 'Observation unavailable',
};
const CONTRACT_ERROR = 'Observation response does not satisfy the read-only contract.';
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const requireValue = condition => { if (!condition) throw new Error(CONTRACT_ERROR); };
const integer = (value, minimum = 0) => Number.isSafeInteger(value) && value >= minimum;
const optionalInteger = (value, minimum = 0) => value === null || integer(value, minimum);
const digest = (value, size) => typeof value === 'string' && new RegExp(`^[a-f0-9]{${size}}$`).test(value);

function timestamp(value) {
  requireValue(typeof value === 'string' && value.length <= 64
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value));
  const milliseconds = Date.parse(value);
  requireValue(Number.isFinite(milliseconds)
    && new Date(milliseconds).toISOString().slice(0, 19) === value.slice(0, 19));
  // Preserve the producer's microseconds when validating boundary states.
  // Browser display expiry still rounds conservatively to milliseconds.
  const fraction = /\.(\d{1,6})/.exec(value)?.[1] || '';
  return milliseconds + Number(fraction.padEnd(6, '0').slice(3)) / 1000;
}

export function validateTrainingObservation(value) {
  requireValue(record(value) && value.schema === SCHEMA && value.available === true
    && ['OBSERVED', 'STALE', 'CLOCK_SKEW', 'PARTIAL'].includes(value.state)
    && value.sourceKind === 'LOCAL_FILE_OBSERVATION'
    && digest(value.reportSha256, 64) && ROOT_UNVERIFIED.every(key => value[key] === false));
  requireValue(record(value.authority) && Object.keys(value.authority).length === AUTHORITY.length
    && AUTHORITY.every(key => value.authority[key] === false));
  const evaluated = timestamp(value.evaluatedAt), sourceObserved = timestamp(value.sourceObservedAt);
  requireValue(Array.isArray(value.candidates) && value.candidates.length >= 1 && value.candidates.length <= 32
    && integer(value.returned) && value.returned === value.candidates.length);
  const seen = new Set();
  for (const row of value.candidates) {
    requireValue(record(row) && typeof row.id === 'string'
      && /^SZLHOLDINGS\/[A-Za-z0-9][A-Za-z0-9._-]{0,159}$/.test(row.id)
      && !row.id.includes('..') && !seen.has(row.id)
      && PRODUCER_STATES.includes(row.producerState)
      && STATES.includes(row.state) && ROW_UNVERIFIED.every(key => row[key] === false));
    seen.add(row.id);
    const observed = timestamp(row.observedAt), expires = timestamp(row.expiresAt);
    requireValue(observed <= sourceObserved && expires > observed && expires <= observed + 660000
      && typeof row.ageSeconds === 'number' && Number.isFinite(row.ageSeconds)
      && Math.abs(row.ageSeconds - (evaluated - observed) / 1000) <= 0.002
      && (row.hubRevision === null || digest(row.hubRevision, 40))
      && optionalInteger(row.checkpointStep) && integer(row.targetSteps, 1)
      && optionalInteger(row.trainerGlobalStep) && optionalInteger(row.trainerMaxSteps, 1)
      && (row.trainerStateSha256 === null || digest(row.trainerStateSha256, 64))
      && ['PINNED_OBJECT_BYTES_VERIFIED', 'UNAVAILABLE'].includes(row.trainerStateIntegrityReported)
      && optionalInteger(row.providerReadyCount)
      && record(row.finalFiles) && Object.keys(row.finalFiles).length === 3
      && ['adapter', 'config', 'tokenizer'].every(key => row.finalFiles[key] === null
        || typeof row.finalFiles[key] === 'boolean'));
    const trainerPresent = row.trainerStateIntegrityReported === 'PINNED_OBJECT_BYTES_VERIFIED';
    requireValue(trainerPresent
      ? row.hubRevision !== null && row.checkpointStep !== null
        && row.trainerGlobalStep === row.checkpointStep && row.trainerMaxSteps !== null
        && row.trainerStateSha256 !== null
      : row.trainerGlobalStep === null && row.trainerMaxSteps === null && row.trainerStateSha256 === null);
    requireValue(row.hubRevision !== null
      ? Object.values(row.finalFiles).every(flag => typeof flag === 'boolean')
      : row.checkpointStep === null && Object.values(row.finalFiles).every(flag => flag === null));
    const expected = sourceObserved > evaluated ? 'CLOCK_SKEW' : evaluated >= expires ? 'STALE'
      : row.producerState === 'UNAVAILABLE' ? 'UNAVAILABLE' : 'OBSERVED';
    requireValue(row.state === expected);
  }
  const expectedOverall = value.candidates.some(row => row.state === 'CLOCK_SKEW') ? 'CLOCK_SKEW'
    : value.candidates.some(row => row.state === 'STALE') ? 'STALE'
    : value.candidates.some(row => row.state === 'UNAVAILABLE') ? 'PARTIAL' : 'OBSERVED';
  requireValue(value.state === expectedOverall);
  return value;
}

export function candidateObservationState(value, row, now, clockDiscrepancy = false) {
  if (clockDiscrepancy || !Number.isFinite(now) || row.state === 'CLOCK_SKEW'
      || Date.parse(value.evaluatedAt) > now || Date.parse(value.sourceObservedAt) > now
      || Date.parse(row.observedAt) > now) return 'CLOCK_SKEW';
  if (row.state === 'STALE' || now >= Date.parse(row.expiresAt)) return 'STALE';
  return row.state === 'UNAVAILABLE' ? 'UNAVAILABLE' : 'OBSERVED';
}

export async function readBoundedObservationJson(response, signal) {
  if (!/^application\/json(?:\s*;|$)/i.test(response.headers.get('content-type') || ''))
    throw new Error('Observation response is not JSON.');
  const declared = response.headers.get('content-length');
  if (declared !== null && (!/^\d+$/.test(declared) || Number(declared) > MAX_OBSERVATION_BYTES))
    throw new Error('Observation response exceeds its size limit.');
  if (!response.body) throw new Error('Observation response has no body.');
  const reader = response.body.getReader(), chunks = [];
  const abort = () => { void reader.cancel().catch(() => {}); };
  const checkAbort = () => { if (signal?.aborted) throw new DOMException('Request aborted.', 'AbortError'); };
  signal?.addEventListener('abort', abort, {once: true});
  let length = 0;
  try {
    checkAbort();
    while (true) {
      const {done, value} = await reader.read();
      checkAbort();
      if (done) break;
      length += value.byteLength;
      if (length > MAX_OBSERVATION_BYTES) throw new Error('Observation response exceeds its size limit.');
      chunks.push(value);
    }
  } finally {
    signal?.removeEventListener('abort', abort);
    void reader.cancel().catch(() => {});
    reader.releaseLock();
  }
  const bytes = new Uint8Array(length); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try { return JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes)); }
  catch { throw new Error('Observation response contains invalid JSON.'); }
}

export function bootTrainingObservations({
  document: doc = globalThis.document,
  fetch: fetcher = globalThis.fetch,
  now = () => Date.now(),
  monotonic = () => globalThis.performance.now(),
  setTimer = globalThis.setTimeout,
  clearTimer = globalThis.clearTimeout,
} = {}) {
  if (!doc?.getElementById('training-observations')) return null;
  const $ = name => doc.getElementById(`training-observation-${name}`);
  let value = null, generation = 0, active = null, expiryTimer = null, disposed = false;
  let receivedWall = 0, receivedMonotonic = 0, latestNow = 0, clockDiscrepancy = false;
  let stateLabels = [];
  const text = (tag, content, className) => {
    const element = doc.createElement(tag); element.textContent = content;
    if (className) element.className = className;
    return element;
  };
  function clearResults() {
    if (expiryTimer !== null) clearTimer(expiryTimer);
    expiryTimer = null; value = null; stateLabels = []; clockDiscrepancy = false;
    $('results').hidden = true; $('cards').replaceChildren(); $('summary').textContent = '';
    for (const name of ['evaluated', 'source-observed', 'report-hash']) $(name).textContent = 'Unavailable';
  }
  function effectiveNow() {
    const wall = now(), elapsed = Math.max(0, monotonic() - receivedMonotonic);
    if (!Number.isFinite(wall) || !Number.isFinite(elapsed)) {
      clockDiscrepancy = true; return latestNow;
    }
    if (wall < receivedWall || wall + 1000 < receivedWall + elapsed) clockDiscrepancy = true;
    latestNow = Math.max(latestNow, wall, receivedWall + elapsed);
    return latestNow;
  }
  function updateFreshness() {
    if (expiryTimer !== null) clearTimer(expiryTimer);
    expiryTimer = null;
    if (!value) return;
    const current = effectiveNow(), states = [];
    for (const {row, element} of stateLabels) {
      const state = candidateObservationState(value, row, current, clockDiscrepancy);
      states.push(state); element.textContent = STATE_LABEL[state];
    }
    const counted = state => states.filter(item => item === state).length;
    $('summary').textContent = `${value.returned} recorded candidate observations · `
      + `${counted('OBSERVED')} within reported time window · ${counted('STALE')} expired · `
      + `${counted('CLOCK_SKEW')} with clock discrepancy · ${counted('UNAVAILABLE')} unavailable. `
      + 'Training completion and promotion are not verified or authorized by this view.';
    if (states.includes('OBSERVED')) {
      const deadlines = stateLabels.filter(({row}) =>
        candidateObservationState(value, row, current, clockDiscrepancy) === 'OBSERVED')
        .map(({row}) => Date.parse(row.expiresAt));
      expiryTimer = setTimer(updateFreshness, Math.max(1, Math.min(1000, Math.min(...deadlines) - current)));
    }
  }
  function addField(list, label, content) {
    list.append(text('dt', label), text('dd', content === null ? 'Unavailable' : String(content)));
  }
  function render() {
    $('evaluated').textContent = value.evaluatedAt;
    $('source-observed').textContent = value.sourceObservedAt;
    $('report-hash').textContent = value.reportSha256;
    for (const row of value.candidates) {
      const article = text('article', '', 'training-observation-card');
      const state = text('p', '', 'training-observation-state');
      article.append(text('h3', row.id), state);
      article.append(text('p', (row.checkpointStep === null ? 'Checkpoint unavailable'
        : `Checkpoint step reported: ${row.checkpointStep}`) + ` · Target declared: ${row.targetSteps}.`,
      'training-observation-progress'));
      article.append(text('p', `Producer-reported status: ${row.producerState.replaceAll('_', ' ').toLowerCase()}.`));
      article.append(text('p', 'Training completion: unverified. Evaluation: unverified. Artifact integrity: '
        + 'unverified. Proof: unverified. Process liveness: unverified. Promotion: not authorized.',
      'training-observation-checks'));
      const details = text('details', ''), list = text('dl', '');
      details.append(text('summary', 'Recorded metadata'));
      addField(list, 'Candidate observed at', row.observedAt);
      addField(list, 'Observation expires at', row.expiresAt);
      addField(list, 'Hub revision reported', row.hubRevision);
      addField(list, 'Checkpoint step reported', row.checkpointStep);
      addField(list, 'Target steps declared', row.targetSteps);
      addField(list, 'Trainer global step reported', row.trainerGlobalStep);
      addField(list, 'Trainer max steps reported', row.trainerMaxSteps);
      addField(list, 'Trainer-state SHA-256 reported', row.trainerStateSha256);
      addField(list, 'Trainer-state integrity reported', row.trainerStateIntegrityReported === 'UNAVAILABLE'
        ? 'Unavailable' : 'Producer reports pinned object bytes checked; not independently verified here');
      for (const name of ['adapter', 'config', 'tokenizer']) addField(list, `Final ${name} file reported`,
        row.finalFiles[name] === null ? null : row.finalFiles[name] ? 'Reported present' : 'Reported absent');
      addField(list, 'Provider-ready instances reported', row.providerReadyCount);
      details.append(list); article.append(details); $('cards').append(article);
      stateLabels.push({row, element: state});
    }
    $('results').hidden = false; updateFreshness();
  }
  async function load() {
    if (disposed) return;
    const ticket = ++generation; active?.abort(); active = null; clearResults();
    $('load').disabled = false;
    const tenant = $('tenant').value.trim(); let token = $('token').value.trim();
    $('token').value = '';
    if (!/^[\x21-\x7e]{1,256}$/.test(tenant) || !/^[\x21-\x7e]{1,8192}$/.test(token)) {
      $('status').textContent = 'Enter a tenant and operator token. No private observations are displayed.';
      return;
    }
    const own = new AbortController(); active = own; let timedOut = false;
    $('load').disabled = true; $('status').textContent = 'Reading operator observations…';
    const requestTimer = setTimer(() => { timedOut = true; own.abort(); }, 15000);
    try {
      const pending = fetcher(OBSERVATION_ENDPOINT, {
        method: 'GET', credentials: 'omit', redirect: 'error', cache: 'no-store', signal: own.signal,
        headers: {Accept: 'application/json', Authorization: `Bearer ${token}`, 'X-A11oy-Tenant': tenant},
      });
      token = '';
      const response = await pending;
      if (ticket !== generation) return;
      if (!response.ok) {
        if (response.status === 401 || response.status === 403)
          throw new Error(`Operator access was not accepted (HTTP ${response.status}).`);
        throw new Error(`Operator observations unavailable (HTTP ${response.status}).`);
      }
      const incoming = validateTrainingObservation(await readBoundedObservationJson(response, own.signal));
      if (ticket !== generation) return;
      if (own.signal.aborted) throw new DOMException('Request aborted.', 'AbortError');
      value = incoming; receivedWall = now(); receivedMonotonic = monotonic(); latestNow = receivedWall;
      clockDiscrepancy = Date.parse(value.evaluatedAt) > receivedWall;
      render();
      $('status').textContent = (value.state === 'PARTIAL' ? 'Report contains unavailable observations. '
        : value.state === 'STALE' ? 'Report contains expired observations. '
        : value.state === 'CLOCK_SKEW' || clockDiscrepancy ? 'Clock discrepancy: observation freshness is unknown. '
        : 'Observation report loaded. ')
        + 'Freshness expires locally; load again manually to request a new report.';
    } catch (error) {
      if (ticket !== generation) return;
      clearResults();
      $('status').textContent = own.signal.aborted
        ? `Observation request ${timedOut ? 'timed out' : 'cancelled'}. No private observations are displayed.`
        : `${error instanceof Error ? error.message : 'Observation request failed.'} No private observations are displayed.`;
    } finally {
      clearTimer(requestTimer);
      if (ticket === generation) { active = null; $('load').disabled = false; }
    }
  }
  function disconnect() {
    generation++; active?.abort(); active = null; clearResults();
    $('token').value = ''; $('tenant').value = ''; $('load').disabled = false;
    $('status').textContent = 'Disconnected. Access fields and private observations cleared.';
  }
  function credentialsChanged() {
    generation++; active?.abort(); active = null; clearResults(); $('load').disabled = false;
    $('status').textContent = 'Access fields changed. Load observations to inspect the selected tenant.';
  }
  const visibility = () => { if (doc.visibilityState === 'visible') updateFreshness(); };
  $('load').addEventListener('click', load);
  $('disconnect').addEventListener('click', disconnect);
  for (const name of ['tenant', 'token']) {
    $(name).addEventListener('input', credentialsChanged);
    $(name).addEventListener('change', credentialsChanged);
  }
  doc.addEventListener('visibilitychange', visibility);
  doc.defaultView?.addEventListener('pagehide', disconnect);
  return {load, disconnect, dispose() {
    disconnect(); disposed = true;
    $('load').removeEventListener('click', load);
    $('disconnect').removeEventListener('click', disconnect);
    for (const name of ['tenant', 'token']) {
      $(name).removeEventListener('input', credentialsChanged);
      $(name).removeEventListener('change', credentialsChanged);
    }
    doc.removeEventListener('visibilitychange', visibility);
    doc.defaultView?.removeEventListener('pagehide', disconnect);
  }};
}

if (typeof document !== 'undefined') bootTrainingObservations();
