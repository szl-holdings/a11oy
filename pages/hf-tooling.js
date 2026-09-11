// SPDX-License-Identifier: Apache-2.0 — SZL Holdings
// Public evidence only. No credentials, local storage, innerHTML or effectors.
const endpoint = '/api/a11oy/v1/frontier-tooling';
const $ = (id) => document.getElementById(id);
const names = {
  filesystem_path_boundary: 'Unsafe download paths rejected',
  httpx_exception_contract: 'Shared HTTP exception contract',
  public_readme_cache_roundtrip: 'Pinned concurrent reads · no dry-run payload',
  sandbox_label_validation: 'Job labels validated before provider access',
  accelerate_cpu_checkpoint_roundtrip: 'CPU checkpoint restored exactly',
  chunked_nll_loss_gradient_parity: 'Eight CPU loss / gradient comparisons',
  long_context_config_only: '1M-token configuration · no training',
  synthetic_generation_offline: 'Tiny local-model generation',
  catalog_does_not_grant_authority: 'Discovery cannot expand the allowlist',
  custom_message_label_roundtrip: 'Evidence messages and bookmarks persisted',
  legacy_compaction_replay: 'Legacy session replay',
  malformed_session_rejected: 'Malformed session records rejected',
};
const titles = { VERSION_MATCH_ONLY: 'Version matches · source unverified', VERSION_DIFFERS: 'Different installed version', NOT_INSTALLED: 'Not installed in this process', UNAVAILABLE: 'Metadata unavailable' };
const expectedIds = ['hub-linux', 'hub-windows', 'trl', 'tau'];
let controller;
let requestNumber = 0;
let currentFilter = 'all';
let currentData;

function element(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = String(text);
  if (cls) node.className = cls;
  return node;
}
function link(text, url) {
  const node = element('a', text); node.href = url;
  if (url.startsWith('https://')) { node.target = '_blank'; node.rel = 'noopener noreferrer'; }
  return node;
}
function valid(data) {
  // The server authenticates the archive against reviewed source. This client
  // additionally refuses malformed projections and any implied action authority.
  if (!data || data.schema !== 'szl.hf-tooling-product.v1' || data.available !== true || data.kind !== 'ARCHIVED_MEASUREMENT' || data.productionDisposition !== 'HOLD') return false;
  if (data.sourceRepository !== 'szl-holdings/szl-forge' || !/^[a-f0-9]{40}$/.test(data.sourceRevision) || !/^[a-f0-9]{64}$/.test(data.archiveSha256)) return false;
  if (!data.authority || Object.keys(data.authority).length !== 6 || Object.values(data.authority).some((v) => v !== false)) return false;
  if (!Number.isSafeInteger(data.workflowRun) || data.workflowRun <= 0 || data.signatureState !== 'UNSIGNED') return false;
  if (!Array.isArray(data.lanes) || data.lanes.length !== 4 || new Set(data.lanes.map((r) => r.id)).size !== 4) return false;
  for (const lane of data.lanes) {
    if (!expectedIds.includes(lane.id) || lane.state !== 'SMOKE_PASS' || !Number.isSafeInteger(lane.artifactId) || lane.artifactId <= 0) return false;
    if (!/^[a-f0-9]{64}$/.test(lane.receiptSha256) || !Array.isArray(lane.sources) || !Array.isArray(lane.remaining)) return false;
    if (!lane.checks || Object.keys(lane.checks).length !== 4 || Object.entries(lane.checks).some(([key, row]) => !names[key] || row.status !== 'PASS' || !row.evidence)) return false;
  }
  return Array.isArray(data.runtime?.packages) && data.runtime.packages.length === 5 && data.runtime.packages.every((row) => row.state in titles && row.exactInstalledSourceVerified === false) && Array.isArray(data.bounds);
}
function renderLanes() {
  const fragment = document.createDocumentFragment();
  for (const lane of currentData.lanes.filter((row) => currentFilter === 'all' || row.id.startsWith(currentFilter))) {
    const card = element('article', undefined, 'lane');
    card.dataset.lane = lane.id;
    const top = element('div', undefined, 'lane-top'); top.append(element('h3', lane.label), element('span', 'Smoke passed', 'pill'));
    const versions = lane.sources.map((row) => `${row.package} ${row.version}`).join(' · ');
    card.append(top, element('p', versions, 'lane-meta mono'));
    const list = element('ul', undefined, 'check-list');
    for (const [name, check] of Object.entries(lane.checks)) {
      const row = element('li'); row.append(element('span', names[name]), element('strong', check.status)); list.append(row);
    }
    card.append(list);
    const measured = element('details'); measured.append(element('summary', 'Inspect measured values'));
    measured.append(element('pre', JSON.stringify(lane.checks, null, 2)));
    const remaining = element('details'); remaining.append(element('summary', `${lane.remaining.length} unmeasured requirements`));
    const missing = element('ul'); for (const name of lane.remaining) missing.append(element('li', name.replaceAll('_', ' '))); remaining.append(missing);
    card.append(measured, remaining, link('Read exact receipt →', `${endpoint}/receipts/${lane.id}`)); fragment.append(card);
  }
  $('lanes').replaceChildren(fragment);
  for (const button of $('lane-filters').querySelectorAll('button')) button.setAttribute('aria-pressed', String(button.dataset.filter === currentFilter));
}
function render(data) {
  currentData = data;
  const filters = document.createDocumentFragment();
  for (const [id, label] of [['all', 'All evaluations'], ['hub', 'Hub'], ['trl', 'Training'], ['tau', 'Memory']]) {
    const button = element('button', label); button.type = 'button'; button.dataset.filter = id;
    button.addEventListener('click', () => { currentFilter = id; renderLanes(); }); filters.append(button);
  }
  $('lane-filters').replaceChildren(filters); renderLanes();
  $('archive-date').textContent = `Forge run ${data.workflowRun} · measured ${data.lanes[0].observedAt.slice(0, 10)} · four executed platform lanes. Not a live training run.`;
  const packages = document.createDocumentFragment();
  for (const row of data.runtime.packages) {
    const node = element('div', undefined, 'package');
    const label = element('div'); label.append(element('strong', row.package), element('small', `Evaluated ${row.evaluatedVersion}`));
    node.append(label, element('span', row.installedVersion ?? '—', 'mono'), element('span', titles[row.state], `state ${row.state === 'VERSION_MATCH_ONLY' ? 'match' : ''}`)); packages.append(node);
  }
  $('packages').replaceChildren(packages);
  $('runtime-observed').textContent = `Process observation: ${data.runtime.observedAt}`;
  $('forge-source').textContent = data.sourceRevision; $('archive-hash').textContent = data.archiveSha256;
  $('product-source').textContent = data.runtime.productSourceRevision || 'UNAVAILABLE';
  $('bounds').replaceChildren(...data.bounds.map((text) => element('li', text)));
  const base = 'https://github.com/szl-holdings/szl-forge';
  $('source-links').replaceChildren(link('Merged implementation ↗', `${base}/pull/216`), link('Executed workflow ↗', `${base}/actions/runs/${data.workflowRun}`), link('Product API →', endpoint));
  $('content').hidden = false; $('error').hidden = true;
  $('status').textContent = 'Archive verified · process metadata observed';
}
async function refresh() {
  const sequence = ++requestNumber;
  controller?.abort(); controller = new AbortController();
  const active = controller; const timer = setTimeout(() => active.abort(), 12000);
  $('refresh').disabled = true; $('status').textContent = 'Checking evidence…';
  // Never leave a previous green result displayed after a failed refresh.
  $('content').hidden = true; $('error').hidden = true;
  try {
    const response = await fetch(endpoint, { signal: active.signal, credentials: 'omit', cache: 'no-store', headers: { Accept: 'application/json' } });
    if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Evidence API unavailable');
    const text = await response.text(); if (text.length > 131072) throw new Error('Oversized evidence response');
    const data = JSON.parse(text); if (!valid(data)) throw new Error('Evidence response failed validation');
    if (sequence === requestNumber) render(data);
  } catch (error) {
    if (sequence !== requestNumber) return;
    currentData = undefined; $('lanes').replaceChildren(); $('packages').replaceChildren();
    $('content').hidden = true; $('error').hidden = false;
    $('status').textContent = 'UNAVAILABLE · no cached success';
    $('error-text').textContent = error.name === 'AbortError' ? 'The request timed out. Refresh to retry; no cached success is presented.' : 'The source-bound archive could not be verified. No measurements are presented as current.';
  } finally { clearTimeout(timer); if (sequence === requestNumber) $('refresh').disabled = false; }
}
$('refresh').addEventListener('click', refresh);
void refresh();
