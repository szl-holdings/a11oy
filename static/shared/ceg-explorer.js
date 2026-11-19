/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
 */
(() => {
  'use strict';

  const root = document.getElementById('evidence-inspector');
  if (!root) return;
  const endpoint = root.dataset.endpoint;
  const MAX_EDGES = 1024;
  const MAX_RESPONSE_BYTES = 2 * 1024 * 1024;
  const RECEIPT_ID = /^edge-[a-f0-9]{64}$/;
  const SHA256 = /^[a-f0-9]{64}$/;
  const SCOPES = new Set([
    'RUNTIME_OBSERVATION', 'RUNTIME_SOURCE_WITNESS',
    'HISTORICAL_ARTIFACT', 'OBSERVER_SUPPLIED',
  ]);
  const PUBLIC_ARTIFACT_HOSTS = new Set([
    'huggingface.co', 'github.com', 'raw.githubusercontent.com', 'doi.org', 'arxiv.org',
  ]);
  const $ = id => root.querySelector('#' + id);
  const ui = {
    status: $('ceg-status'), count: $('ceg-count'), list: $('ceg-list'),
    details: $('ceg-details'), summary: $('ceg-summary'), witness: $('ceg-witness'),
    blockers: $('ceg-blockers'), filter: $('ceg-filter'), scope: $('ceg-scope'),
    refresh: $('ceg-refresh'),
  };
  let snapshot = null;
  let selectedId = null;

  function object(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function text(value, fallback = 'NOT SUPPLIED') {
    if (typeof value === 'string' && value.length) return value;
    if (typeof value === 'boolean' || typeof value === 'number') return String(value);
    return fallback;
  }

  function node(tag, value, className) {
    const element = document.createElement(tag);
    if (value !== undefined) element.textContent = text(value, '');
    if (className) element.className = className;
    return element;
  }

  function publicArtifactUrl(value) {
    if (typeof value !== 'string' || value.length > 2048) return null;
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || url.username || url.password || url.port ||
          !PUBLIC_ARTIFACT_HOSTS.has(url.hostname)) return null;
      return url.href;
    } catch {
      return null;
    }
  }

  function validateSnapshot(payload) {
    if (!object(payload) || payload.schema !== 'szl.evidence-graph/v1' ||
        !object(payload.graph) || payload.graph.schema !== 'szl.evidence-graph/v1') {
      throw new Error('Unexpected evidence response schema');
    }
    const graph = payload.graph;
    if (!Array.isArray(graph.edges) || graph.edges.length > MAX_EDGES ||
        graph.edge_count !== graph.edges.length || typeof graph.digest_sha256 !== 'string' ||
        !SHA256.test(graph.digest_sha256)) {
      throw new Error('Invalid or oversized evidence snapshot');
    }
    const ids = new Set();
    for (const edge of graph.edges) {
      if (!object(edge) || edge.schema !== 'szl.evidence-edge/v1' ||
          typeof edge.receipt_id !== 'string' || !RECEIPT_ID.test(edge.receipt_id) ||
          ids.has(edge.receipt_id) ||
          !object(edge.subject) || typeof edge.subject.kind !== 'string' ||
          typeof edge.subject.id !== 'string' || !object(edge.runtime) ||
          !object(edge.evidence) || !object(edge.authority) ||
          !Array.isArray(edge.parents) || edge.parents.length > MAX_EDGES ||
          !edge.parents.every(id => typeof id === 'string' && RECEIPT_ID.test(id))) {
        throw new Error('Invalid evidence edge');
      }
      ids.add(edge.receipt_id);
    }
    return payload;
  }

  function assessment(edge) {
    const supplied = snapshot && object(snapshot.edge_assessments)
      ? snapshot.edge_assessments[edge.receipt_id] : null;
    if (object(supplied) && SCOPES.has(supplied.scope)) return supplied;
    let scope = 'OBSERVER_SUPPLIED';
    if (edge.evidence.kind === 'receipt-artifact') scope = 'HISTORICAL_ARTIFACT';
    else if (edge.subject.kind === 'runtime') scope = 'RUNTIME_OBSERVATION';
    return {
      scope, freshness: 'UNKNOWN', source_relation: 'NOT ASSESSED',
      observed_at: edge.evidence.observed_at, valid_until: edge.evidence.valid_until,
      assessment_unavailable: true,
    };
  }

  function scopeLabel(edge) {
    const scope = assessment(edge).scope;
    return {
      RUNTIME_OBSERVATION: 'Runtime observation',
      RUNTIME_SOURCE_WITNESS: 'Runtime source witness',
      HISTORICAL_ARTIFACT: 'Historical artifact',
      OBSERVER_SUPPLIED: 'Observer-supplied record',
    }[scope];
  }

  function appendField(list, label, value, mono = false) {
    list.append(node('dt', label));
    const detail = node('dd', text(value));
    if (mono) detail.className = 'ceg-mono';
    list.append(detail);
  }

  function appendJson(container, label, value) {
    const disclosure = node('details', undefined, 'ceg-disclosure');
    disclosure.append(node('summary', label));
    disclosure.append(node('pre', JSON.stringify(value, null, 2), 'ceg-json'));
    container.append(disclosure);
  }

  function renderSnapshotSummary() {
    const graph = snapshot.graph;
    const fields = node('dl', undefined, 'ceg-facts');
    appendField(fields, 'Returned edges', graph.edge_count);
    appendField(fields, 'Snapshot captured', snapshot.captured_at);
    appendField(fields, 'Graph SHA-256 (backend supplied)', graph.digest_sha256, true);
    appendField(fields, 'Digest scope', graph.digest_scope || 'NOT REPORTED BY THIS API VERSION');
    appendField(fields, 'Bounded snapshot', graph.bounded);
    if (Array.isArray(graph.causal_heads)) {
      appendField(fields, 'Causal heads in returned edges', graph.causal_heads.length);
    }
    appendField(fields, 'Ledger head', graph.ledger_head, true);
    for (const [label, key] of [
      ['Missing parent IDs in source', 'missing_parent_count'],
      ['Parents omitted from returned edges', 'omitted_parent_count'],
      ['Unresolved parent IDs', 'unresolved_parent_count'],
    ]) {
      if (Number.isInteger(graph[key])) appendField(fields, label, graph[key]);
    }
    ui.summary.replaceChildren(fields);
  }

  function renderWitness() {
    ui.witness.replaceChildren();
    const witness = snapshot.provenance_witness;
    if (!object(witness)) {
      ui.witness.append(node('p', 'Runtime source witness: NOT SUPPLIED by this API version.'));
    } else {
      const fields = node('dl', undefined, 'ceg-facts');
      for (const [label, key] of [
        ['Witness state', 'state'], ['Observer status', 'status'], ['Reason', 'reason'],
        ['Source revision', 'source_revision'], ['HF revision', 'hf_revision'],
        ['Runtime boot ID', 'runtime_boot_id'], ['Local bytes evidence', 'local_bytes_evidence'],
        ['Witness scope', 'scope'], ['Execution authority', 'execution_authority'],
      ]) appendField(fields, label, witness[key], key.endsWith('revision') || key.endsWith('_id'));
      ui.witness.append(fields);
    }
    ui.blockers.replaceChildren();
    if (!Array.isArray(snapshot.blockers)) {
      ui.blockers.append(node('li', 'Blocker assessment was not supplied by this API version.'));
    } else if (!snapshot.blockers.length) {
      ui.blockers.append(node('li', 'No blockers reported by this observation endpoint. Execution authority remains a separate field.'));
    } else {
      for (const blocker of snapshot.blockers.slice(0, 128)) {
        ui.blockers.append(node('li', typeof blocker === 'string' ? blocker : JSON.stringify(blocker)));
      }
      if (snapshot.blockers.length > 128) ui.blockers.append(node('li', 'Additional blockers are in the raw JSON.'));
    }
  }

  function selectEdge(id, focusDetails = false) {
    selectedId = id;
    renderList();
    if (focusDetails) ui.details.focus({preventScroll: true});
    else ui.list.querySelector('button[aria-pressed="true"]')?.focus({preventScroll: true});
  }

  function renderDetails(edge) {
    ui.details.replaceChildren();
    if (!edge) {
      ui.details.append(node('p', 'Select a returned edge to inspect its content and declared parents.', 'ceg-empty'));
      return;
    }
    const observed = assessment(edge);
    ui.details.append(node('h3', text(edge.subject.kind) + ' / ' + text(edge.subject.id)));
    ui.details.append(node('p', scopeLabel(edge) + ' · observer verdict: ' + text(edge.verdict), 'ceg-caption'));
    if (observed.scope === 'HISTORICAL_ARTIFACT') {
      ui.details.append(node('p', 'Historical receipt bytes do not establish the current runtime, freshness, or execution authority.', 'ceg-notice'));
    }
    if (observed.assessment_unavailable) {
      ui.details.append(node('p', 'Assessment unavailable. Scope follows the record type; freshness and source agreement have not been assessed.', 'ceg-notice'));
    }
    const fields = node('dl', undefined, 'ceg-facts');
    appendField(fields, 'Receipt ID', edge.receipt_id, true);
    appendField(fields, 'Source revision', edge.source_revision, true);
    appendField(fields, 'Artifact SHA-256', edge.artifact_sha256, true);
    appendField(fields, 'Observed at', observed.observed_at);
    appendField(fields, 'Declared valid until', observed.valid_until);
    appendField(fields, 'Freshness assessment', observed.freshness);
    appendField(fields, 'Source relation', observed.source_relation);
    if (edge.evidence.relationship) appendField(fields, 'Declared relationship', edge.evidence.relationship);
    appendField(fields, 'Signature status', edge.evidence.signature_status || 'UNSPECIFIED', true);
    appendField(fields, 'Claims verified (reported)', edge.evidence.claims_verified);
    appendField(fields, 'Reason', edge.reason);
    ui.details.append(fields);
    if (typeof edge.evidence.artifact_uri === 'string') {
      const row = node('p', undefined, 'ceg-artifact');
      const href = publicArtifactUrl(edge.evidence.artifact_uri);
      if (href) {
        const link = node('a', 'Open public source artifact');
        link.href = href;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        row.append(link);
      } else {
        row.textContent = 'Source artifact URL is outside the public HTTPS allowlist; inspect the supplied field below.';
      }
      ui.details.append(row);
    }
    const parents = node('section', undefined, 'ceg-parents');
    parents.append(node('h4', 'Declared parent receipts'));
    if (!edge.parents.length) {
      parents.append(node('p', 'No parent links supplied. No lineage relationship is inferred.'));
    } else {
      parents.append(node('p', 'Links below come from the edge’s parents field. Their meaning and authority remain those of the supplying observer.'));
      if (observed.scope === 'RUNTIME_SOURCE_WITNESS') {
        parents.append(node('p', 'Source witness parent links record a source comparison only; CEG does not reverify the cached witness or grant execution authority.'));
      }
      const list = node('ul');
      for (const parentId of edge.parents) {
        const item = node('li');
        const present = snapshot.graph.edges.some(candidate => candidate.receipt_id === parentId);
        if (present) {
          const button = node('button', parentId, 'ceg-parent-link');
          button.type = 'button';
          button.addEventListener('click', () => {
            ui.filter.value = '';
            ui.scope.value = 'all';
            selectEdge(parentId, true);
          });
          item.append(button);
        } else {
          const missing = Array.isArray(snapshot.graph.missing_parent_ids) &&
            snapshot.graph.missing_parent_ids.includes(parentId);
          const omitted = Array.isArray(snapshot.graph.omitted_parent_ids) &&
            snapshot.graph.omitted_parent_ids.includes(parentId);
          const relation = missing ? 'reported missing from the source snapshot' :
            omitted ? 'omitted from the returned snapshot' : 'outside the returned snapshot';
          item.append(node('span', parentId + ' — ' + relation, 'ceg-mono'));
        }
        list.append(item);
      }
      parents.append(list);
    }
    ui.details.append(parents);
    appendJson(ui.details, 'Runtime fields', edge.runtime);
    appendJson(ui.details, 'Evidence fields (observer supplied)', edge.evidence);
    appendJson(ui.details, 'Authority fields (observer supplied)', edge.authority);
    appendJson(ui.details, 'Complete edge JSON', edge);
  }

  function renderList() {
    const query = ui.filter.value.trim().toLocaleLowerCase();
    const scope = ui.scope.value;
    const edges = snapshot ? snapshot.graph.edges : [];
    const filtered = edges.filter(edge => {
      const category = assessment(edge).scope;
      const inScope = scope === 'all' ||
        (scope === 'runtime' && (category === 'RUNTIME_OBSERVATION' || category === 'RUNTIME_SOURCE_WITNESS')) ||
        (scope === 'historical' && category === 'HISTORICAL_ARTIFACT') ||
        (scope === 'other' && category === 'OBSERVER_SUPPLIED');
      const searchable = [
        edge.receipt_id, edge.subject.kind, edge.subject.id, edge.source_revision,
        edge.artifact_sha256, edge.verdict, scopeLabel(edge),
      ].join(' ').toLocaleLowerCase();
      return inScope && (!query || searchable.includes(query));
    });
    if (!filtered.some(edge => edge.receipt_id === selectedId)) {
      selectedId = filtered.length ? filtered[0].receipt_id : null;
    }
    ui.count.textContent = filtered.length + ' of ' + edges.length + ' returned edges';
    ui.list.replaceChildren();
    for (const edge of filtered) {
      const item = node('li');
      const button = node('button', undefined, 'ceg-edge');
      button.type = 'button';
      button.setAttribute('aria-pressed', String(edge.receipt_id === selectedId));
      button.setAttribute('aria-controls', 'ceg-details');
      button.append(
        node('strong', edge.subject.kind + ' / ' + edge.subject.id),
        node('span', scopeLabel(edge) + ' · ' + text(edge.verdict), 'ceg-caption'),
        node('span', edge.receipt_id, 'ceg-mono'),
      );
      button.addEventListener('click', () => selectEdge(edge.receipt_id));
      item.append(button);
      ui.list.append(item);
    }
    if (!filtered.length) {
      ui.list.append(node('li', snapshot
        ? 'No returned edges match these filters.' : 'No evidence snapshot is available.', 'ceg-empty'));
    }
    renderDetails(filtered.find(edge => edge.receipt_id === selectedId));
  }

  function clearSnapshot(message) {
    snapshot = null;
    selectedId = null;
    ui.status.textContent = message;
    ui.summary.replaceChildren();
    ui.witness.replaceChildren(node('p', 'Runtime source witness unavailable.'));
    ui.blockers.replaceChildren(node('li', 'No current assessment is available.'));
    renderList();
  }

  async function readJson(response) {
    const declaredSize = Number(response.headers.get('content-length'));
    if (declaredSize > MAX_RESPONSE_BYTES) throw new Error('Evidence response exceeds the display limit');
    if (!response.body) throw new Error('Evidence response has no body');
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8', {fatal: true});
    let bytes = 0;
    let body = '';
    try {
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        bytes += part.value.byteLength;
        if (bytes > MAX_RESPONSE_BYTES) throw new Error('Evidence response exceeds the display limit');
        body += decoder.decode(part.value, {stream: true});
      }
      body += decoder.decode();
      return JSON.parse(body);
    } finally {
      await reader.cancel().catch(() => {});
      reader.releaseLock();
    }
  }

  async function refresh() {
    clearSnapshot('Loading observation snapshot…');
    root.setAttribute('aria-busy', 'true');
    ui.refresh.disabled = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      if (!/^\/api\/[a-z0-9_-]+\/v1\/evidence\/graph$/.test(endpoint || '')) {
        throw new Error('Evidence endpoint is not an allowed same-origin path');
      }
      const response = await fetch(endpoint, {
        method: 'GET', headers: {Accept: 'application/json'}, cache: 'no-store',
        credentials: 'same-origin', redirect: 'error', signal: controller.signal,
      });
      if (!response.ok) throw new Error('HTTP ' + response.status);
      if (!(response.headers.get('content-type') || '').toLowerCase().includes('application/json')) {
        throw new Error('Evidence endpoint did not return JSON');
      }
      snapshot = validateSnapshot(await readJson(response));
      ui.status.textContent = 'Evidence availability: ' + text(snapshot.state, 'STATE NOT SUPPLIED') + ' — ' +
        text(snapshot.reason, 'Observation endpoint supplied no reason') +
        '. Received by this browser at ' + new Date().toISOString() + '.';
      renderSnapshotSummary();
      renderWitness();
      renderList();
    } catch (error) {
      clearSnapshot('UNAVAILABLE — ' + (error.name === 'AbortError'
        ? 'request timed out' : error.message) + '. No evidence data is displayed.');
    } finally {
      clearTimeout(timeout);
      root.setAttribute('aria-busy', 'false');
      ui.refresh.disabled = false;
    }
  }

  ui.filter.addEventListener('input', renderList);
  ui.scope.addEventListener('change', renderList);
  ui.refresh.addEventListener('click', refresh);
  refresh();
})();
