/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 */
'use strict';
(() => {
  const el = (id) => document.getElementById(id);
  let ready = false, sending = false, uncertain = false;
  let localReady = false, localSending = false, localUncertain = false;
  let cpuReady = false, cpuSending = false, cpuUncertain = false;
  let cpuAcknowledgedPrompt = null;
  const laneEvidence = { grok: null, local: null, cpu: null };
  const SHA40 = /^(?!0{40}$)[a-f0-9]{40}$/;
  const SHA256 = /^(?!0{64}$)[a-f0-9]{64}$/;
  const RECEIPT_SCHEMA = 'a11oy.atelier.single-turn.receipt/v1';

  function observedContext(value) {
    return typeof value.source_revision === 'string' && SHA40.test(value.source_revision)
      && typeof value.model === 'string' && value.model.length > 0 && value.model.length <= 512
      ? Object.freeze({ source: value.source_revision, model: value.model }) : null;
  }

  function resetPublicConsent() {
    cpuAcknowledgedPrompt = null;
    el('cpu-public-ack').checked = false;
  }

  async function textHash(value) {
    const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
    return Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join('');
  }

  function canonicalValue(value, depth = 0) {
    if (depth > 32) throw new Error('RECEIPT_DEPTH_BOUND');
    if (value === null || typeof value === 'boolean' || typeof value === 'string') return JSON.stringify(value);
    if (typeof value === 'number' && Number.isFinite(value)) return JSON.stringify(value);
    if (Array.isArray(value) && value.length <= 256) return '[' + value.map(x => canonicalValue(x, depth + 1)).join(',') + ']';
    if (value && typeof value === 'object' && Object.keys(value).length <= 256) {
      return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonicalValue(value[k], depth + 1)).join(',') + '}';
    }
    throw new Error('INVALID_RECEIPT_VALUE');
  }

  function parseUniqueJSON(raw) {
    const fail=()=>{throw new Error('RESPONSE_JSON_AMBIGUOUS');};
    // JSON.parse establishes syntax. The bounded second pass rejects duplicate
    // decoded member names, including escaped aliases, before interpretation.
    const value=JSON.parse(raw); let at=0,nodes=0;
    const space=()=>{while(at<raw.length && /[\t\n\r ]/.test(raw[at])) at++;};
    function stringToken() {
      const start=at++;
      for (;;) {
        if (at>=raw.length) fail();
        if (raw[at]==='\\') {at+=2;continue;}
        if (raw[at++]==='"') return raw.slice(start,at);
      }
    }
    function scan(depth) {
      if (depth>32 || ++nodes>16384) fail();
      space(); const kind=raw[at];
      if (kind==='"') {stringToken();return;}
      if (kind==='{' || kind==='[') {
        const end=kind==='{'?'}':']',keys=new Set(); at++;space();
        if (raw[at]===end) {at++;return;}
        for (;;) {
          space();
          if (kind==='{') {
            if (raw[at]!=='"') fail();
            const key=JSON.parse(stringToken());
            if (keys.has(key)) fail();keys.add(key);space();
            if (raw[at++]!==':') fail();
          }
          scan(depth+1);space();
          if (raw[at]===end) {at++;return;}
          if (raw[at++]!==',') fail();
        }
      }
      const start=at;
      while(at<raw.length && !/[\t\n\r ,}\]]/.test(raw[at])) at++;
      if (at===start) fail();
    }
    scan(0);space();if(at!==raw.length) fail();
    return value;
  }
  async function requireBoundOutcome(value, request, context, provider, mode = null) {
    // These are response/request consistency checks, NOT independent signature
    // verification, signer admission, exactly-once execution, or model quality.
    const receipt = value.receipt, payload = receipt?.payload, envelope = value.dsse;
    const require = condition => { if (!condition) throw new Error('OUTCOME_BINDING_UNAVAILABLE'); };
    require(context && value.state === 'COMPLETED' && typeof value.answer === 'string'
      && value.answer.trim() && value.answer.length <= 32768 && value.retry_safe === false);
    require(receipt?.persisted === true && receipt.signature_verified === true
      && typeof receipt.digest === 'string' && SHA256.test(receipt.digest)
      && receipt.chain_scope === 'SINGLE_PROCESS_RETAINED_METADATA_CHAIN');
    require(payload?.schema === RECEIPT_SCHEMA && payload.phase === 'OUTCOME'
      && payload.state === 'COMPLETED' && typeof value.request_id === 'string'
      && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value.request_id)
      && payload.request_id === value.request_id && payload.client_request_id === request.client_request_id
      && payload.provider === provider
      && payload.model === value.model && payload.model === (request.model || context.model)
      && payload.source_revision === context.source
      && typeof payload.decision_receipt_hash === 'string' && SHA256.test(payload.decision_receipt_hash));
    if (mode) require(payload.mode === mode && value.mode === mode && value.provider === provider);
    if (provider === 'szl_cpu_lab') {
      // The provider returns a grounded PROPOSAL, not an executed action.
      // Only the Atelier statement is signed; provider output is UNSIGNED_LOCAL.
      require(payload.classification === 'PUBLIC'
        && payload.public_share_acknowledged === true
        && payload.provider_decision === 'PROPOSAL'
        && value.provider_decision === 'PROPOSAL'
        && payload.provider_output_signature_status === 'UNSIGNED_LOCAL'
        && value.provider_output_signature_status === 'UNSIGNED_LOCAL'
        && payload.grounding_required === true && value.grounding_required === true
        && payload.authority === 'NO_ACTION_AUTHORITY' && value.authority === 'NO_ACTION_AUTHORITY'
        && payload.executed === false && value.executed === false
        && payload.provider_outcome_uncertain === false
        && payload.provider_output_authenticity_verified === false
        && value.provider_output_authenticity_verified === false
        && cpuPublicSources(value) !== null);
      require(payload.evidence_handles_sha256 === await textHash(canonicalValue(value.evidence_handles))
        && payload.citations_sha256 === await textHash(canonicalValue(value.citations)));
    }
    require(payload.prompt_sha256 === await textHash(request.prompt));
    require(payload.answer_sha256 === await textHash(value.answer));
    require(envelope?.signed === true && envelope.payloadType === 'application/vnd.szl.atelier-turn+json'
      && typeof envelope.payload === 'string' && envelope.payload.length <= 262144
      && Array.isArray(envelope.signatures) && envelope.signatures.length > 0 && envelope.signatures.length <= 16
      && envelope.signatures.every(x => typeof x.sig === 'string' && x.sig.length > 0 && x.sig.length <= 16384));
    const embedded = parseUniqueJSON(new TextDecoder('utf-8', { fatal: true }).decode(
      Uint8Array.from(atob(envelope.payload), c => c.charCodeAt(0))));
    require(canonicalValue(embedded) === canonicalValue(payload));
  }

  async function json(url, options = {}, timeout = 15000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, { ...options, cache: 'no-store', credentials: 'same-origin', redirect: 'error', signal: controller.signal });
      if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('NON_JSON_RESPONSE');
      const reader = response.body?.getReader();
      if (!reader) throw new Error('RESPONSE_BODY_UNAVAILABLE');
      const chunks = []; let bytes = 0;
      try {
        while (true) {
          const next = await reader.read();
          if (next.done) break;
          bytes += next.value.byteLength;
          if (bytes > 1048576) { controller.abort(); throw new Error('RESPONSE_BYTE_BOUND'); }
          chunks.push(next.value);
        }
      } finally { reader.releaseLock(); }
      const body = new Uint8Array(bytes); let offset = 0;
      for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
      const value = parseUniqueJSON(new TextDecoder('utf-8', { fatal: true }).decode(body));
      if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('INVALID_RESPONSE');
      return { value, status: response.status, ok: response.ok };
    } finally { clearTimeout(timer); }
  }

  function links(surfaces) {
    for (const [lane, id] of [['operate', 'operate-links'], ['verify', 'verify-links'], ['artifacts', 'artifact-links']]) {
      const target = el(id); target.replaceChildren();
      for (const item of surfaces.filter((item) => item.lane === lane)) {
        if (typeof item.href !== 'string' || !((item.href.startsWith('/') && !item.href.startsWith('//')) || item.href.startsWith('https://'))) continue;
        const link = document.createElement('a'); link.className = 'link-card'; link.href = item.href;
        const title = document.createElement('strong'); title.textContent = item.title;
        const boundary = document.createElement('span'); boundary.textContent = item.boundary;
        link.append(title, boundary); target.append(link);
      }
    }
  }

  function study(value) {
    const models = value.collection?.models;
    if (value.schema !== 'szl.atelier.model-intake.v1' || !Array.isArray(models)) throw new Error('INVALID_STUDY');
    el('study-summary').textContent = `${models.length} pinned repositories · ${value.collected_at_utc || 'Timestamp unavailable'} · bounded public metadata and source review; no model inference or benchmark results.`;
    const target = el('study-models'); target.replaceChildren();
    for (const item of models.slice(0, 50)) {
      if (typeof item.id !== 'string' || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(item.id) || typeof item.revision !== 'string' || !/^[a-f0-9]{40}$/.test(item.revision)) continue;
      const link = document.createElement('a'); link.className = 'link-card';
      link.href = `https://huggingface.co/${item.id.split('/').map(encodeURIComponent).join('/')}/tree/${item.revision}`;
      const title = document.createElement('strong'); title.textContent = item.id;
      const detail = document.createElement('span'); detail.textContent = `${item.revision.slice(0, 12)} · card license: ${item.card_license_declared || 'UNAVAILABLE'} · ${item.license_decision || 'REVIEW_REQUIRED'} · inference not witnessed`;
      link.append(title, detail); target.append(link);
    }
  }

  function cpuPublicSources(value) {
    const handles = value.evidence_handles, citations = value.citations;
    const fields = ['nodeId', 'nodeKind', 'label', 'note'];
    if (!Array.isArray(handles) || !handles.length || handles.length > 3
        || !Array.isArray(citations) || citations.length > 3) return null;
    if (handles.some((handle) => !handle || typeof handle !== 'object' || Array.isArray(handle)
        || fields.some((field) => typeof handle[field] !== 'string' || handle[field].length > 16384)
        || !handle.nodeId || handle.nodeId.length > 256)) return null;
    const ids = new Set(handles.map((handle) => handle.nodeId));
    if (ids.size !== handles.length || new Set(citations).size !== citations.length
        || citations.some((id) => typeof id !== 'string' || !ids.has(id))) return null;
    return {
      handles: handles.map(({ nodeId, nodeKind, label, note }) => ({ nodeId, nodeKind, label, note })),
      citations: [...citations],
    };
  }

  async function refresh() {
    el('refresh').disabled = true; ready = false; localReady = false; cpuReady = false;
    laneEvidence.grok = laneEvidence.local = laneEvidence.cpu = null;
    el('send').disabled = true; el('local-send').disabled = true; el('cpu-send').disabled = true;
    const results = await Promise.allSettled([
      json('/api/a11oy/v1/command-centre/manifest'), json('/api/build-info'),
      json('/api/a11oy/v1/atelier/health'), json('/api/a11oy/v1/command-centre/inventory'),
      json('/api/a11oy/v1/command-centre/study'),
      json('/api/a11oy/v1/atelier/local/health'),
      json('/api/a11oy/v1/atelier/cpu-lab/health'),
    ]);
    if (results[0].status === 'fulfilled' && results[0].value.ok && Array.isArray(results[0].value.value.surfaces)) {
      links(results[0].value.value.surfaces);
      if (results[0].value.value.runtime_scope === 'LOCAL_PREVIEW_STARTUP_DISABLED') el('turn-status').textContent = 'Local source preview · background startup disabled · no production deployment or inference success claimed.';
    }
    const build = results[1];
    if (build.status === 'fulfilled' && build.value.ok) {
      const value = build.value.value;
      const revision = value.build?.revision || value.git_sha || value.source_revision || value.sourceRevision || value.source_commit || value.sha;
      const validRevision = typeof revision === 'string' && /^[a-f0-9]{40}$/.test(revision);
      el('source-state').textContent = validRevision ? 'Declared by this process · not independently verified' : 'Runtime identity incomplete';
      el('source-sha').textContent = validRevision ? revision : 'No valid 40-character source revision';
    } else { el('source-state').textContent = 'Build information unavailable'; el('source-sha').textContent = 'Not observed'; }
    const health = results[2];
    if (health.status === 'fulfilled') {
      const value = health.value.value;
      laneEvidence.grok = observedContext(value);
      ready = health.value.ok && value.ready === true && value.provider === 'xai' && laneEvidence.grok !== null;
      el('grok-state').textContent = ready ? 'Configured · inference not yet witnessed' : 'Unavailable · configuration gates remain';
      const blockers = Array.isArray(value.blockers) ? value.blockers.join(' · ') : 'No successful inference established';
      el('grok-detail').textContent = `${value.model || 'Grok 4.7'} · ${blockers || 'A successful turn still needs its own receipt.'}`;
    } else { el('grok-state').textContent = 'Health unavailable'; el('grok-detail').textContent = 'No readiness or inference success assumed.'; }
    const inventory = results[3];
    if (inventory.status === 'fulfilled' && inventory.value.ok && inventory.value.value.counts) {
      const value = inventory.value.value, counts = value.counts;
      el('inventory-state').textContent = `${counts.models} models · ${counts.kernels} kernels`;
      el('inventory-detail').textContent = `${counts.datasets_public} public datasets · ${counts.spaces_public} public Spaces/profile · ${value.state} · ${value.observed_at}`;
    } else { el('inventory-state').textContent = 'Inventory unavailable'; el('inventory-detail').textContent = 'No counts guessed. Open the proof room for retained evidence.'; }
    try {
      if (results[4].status !== 'fulfilled' || !results[4].value.ok) throw new Error('STUDY_UNAVAILABLE');
      study(results[4].value.value);
    } catch (_error) { el('study-summary').textContent = 'Research snapshot unavailable. No model admission or benchmark result assumed.'; el('study-models').replaceChildren(); }
    const localHealth = results[5];
    if (localHealth.status === 'fulfilled' && localHealth.value.ok) {
      const value = localHealth.value.value;
      laneEvidence.local = observedContext(value);
      localReady = value.ready === true && value.mode === 'NO_KEY_LOCAL' && value.provider === 'local_ollama' && laneEvidence.local !== null;
      el('local-state').textContent = localReady ? 'Configured · inference not yet witnessed' : 'Unavailable · local gates remain';
      const blockers = Array.isArray(value.blockers) ? value.blockers.join(' · ') : 'No completed local turn established';
      el('local-detail').textContent = `${value.model || 'No model selected'} · ${blockers || 'A signed completed turn is still required.'}`;
      el('local-model').value = typeof value.model === 'string' && value.model ? value.model : 'Not configured';
    } else {
      el('local-state').textContent = 'Local health unavailable';
      el('local-detail').textContent = 'No local model readiness or inference assumed.';
      el('local-model').value = 'Not configured';
    }
    const cpuHealth = results[6];
    if (cpuHealth.status === 'fulfilled' && cpuHealth.value.ok) {
      const value = cpuHealth.value.value;
      laneEvidence.cpu = observedContext(value);
      cpuReady = value.ready === true && value.mode === 'NO_PROVIDER_KEY_PUBLIC_CPU_LAB' && value.provider === 'szl_cpu_lab' && laneEvidence.cpu !== null;
      el('cpu-state').textContent = cpuReady ? 'Local gates configured · remote identity not yet checked' : 'Unavailable · CPU lab gates remain';
      const blockers = Array.isArray(value.blockers) ? value.blockers.join(' · ') : 'No completed CPU lab turn established';
      el('cpu-detail').textContent = `${value.model || 'No model selected'} · ${blockers || 'Remote identity is checked only during a signed turn; inference remains unverified.'}`;
      el('cpu-model').value = typeof value.model === 'string' && value.model ? value.model : 'Not configured';
    } else {
      el('cpu-state').textContent = 'CPU lab health unavailable';
      el('cpu-detail').textContent = 'No CPU inference readiness or success assumed.';
      el('cpu-model').value = 'Not configured';
    }
    el('send').disabled = !ready || sending;
    el('local-send').disabled = !localReady || localSending;
    el('cpu-send').disabled = !cpuReady || cpuSending;
    el('refresh').disabled = false;
  }

  el('refresh').addEventListener('click', refresh);
  el('cpu-public-ack').addEventListener('change', () => {
    cpuAcknowledgedPrompt = el('cpu-public-ack').checked ? el('cpu-prompt').value : null;
  });
  for (const event of ['input', 'change']) el('cpu-prompt').addEventListener(event, resetPublicConsent);
  el('forget-key').addEventListener('click', () => { el('operator-key').value = ''; });
  el('local-forget-key').addEventListener('click', () => { el('local-operator-key').value = ''; });
  el('cpu-forget-key').addEventListener('click', () => { el('cpu-operator-key').value = ''; });
  window.addEventListener('pagehide', () => { el('operator-key').value = ''; el('local-operator-key').value = ''; el('cpu-operator-key').value = ''; resetPublicConsent(); });
  el('turn-form').addEventListener('submit', async (event) => {
    event.preventDefault(); if (sending || !ready) return;
    const credential = el('operator-key').value.trim();
    if (!credential || /\s/.test(credential) || credential.length > 4096) { el('turn-status').textContent = 'Enter a valid Atelier operator credential, not the xAI API key.'; return; }
    if (uncertain && !window.confirm('The previous request may have executed at the provider. Sending again can incur another charge. Send a new request?')) return;
    const request = Object.freeze({ client_request_id: crypto.randomUUID(), prompt: el('prompt').value, model: el('model').value, reasoning_effort: el('effort').value, declared: el('classification').value });
    const context = laneEvidence.grok;
    uncertain = false; sending = true; el('send').disabled = true;
    el('answer').hidden = true; el('answer').textContent = ''; el('receipt-panel').hidden = true; el('receipt').textContent = '';
    el('turn-status').textContent = 'Checking authorization and policy, then making at most one provider request…';
    try {
      const response = await json('/api/a11oy/v1/atelier/turn', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${credential}` },
        body: JSON.stringify(request),
      }, 130000);
      const { answer, ...evidence } = response.value;
      el('receipt').textContent = JSON.stringify(evidence, null, 2); el('receipt-panel').hidden = false;
      if (response.ok && response.value.state === 'COMPLETED' && typeof answer === 'string' && answer.trim()) {
        await requireBoundOutcome(response.value, request, context, 'xai');
        el('answer').textContent = answer; el('answer').hidden = false;
        el('turn-status').textContent = 'Response matched the submitted request (not any later draft). The server reports a persisted, signature-verified outcome; it is not independently verified in this browser.';
      } else {
        uncertain = response.status >= 500 || response.value.code === 'PROVIDER_TIMEOUT';
        el('turn-status').textContent = `No completed answer · ${response.value.code || response.value.state || `HTTP ${response.status}`}. No automatic retry was made.`;
      }
    } catch (_error) {
      uncertain = true; el('turn-status').textContent = 'Request outcome uncertain. The provider may have executed it. No automatic retry was made; confirm before sending another request.';
    } finally { sending = false; el('send').disabled = !ready; }
  });
  el('local-turn-form').addEventListener('submit', async (event) => {
    event.preventDefault(); if (localSending || !localReady) return;
    const credential = el('local-operator-key').value.trim();
    if (!credential || /\s/.test(credential) || credential.length > 4096) { el('local-turn-status').textContent = 'Enter the local Atelier operator credential.'; return; }
    if (localUncertain && !window.confirm('The previous local request may have executed. Send a new request?')) return;
    const request = Object.freeze({ client_request_id: crypto.randomUUID(), prompt: el('local-prompt').value, declared: el('local-classification').value, max_output_tokens: 768 });
    const context = laneEvidence.local;
    localUncertain = false; localSending = true; el('local-send').disabled = true;
    el('local-answer').hidden = true; el('local-answer').textContent = '';
    el('local-receipt-panel').hidden = true; el('local-receipt').textContent = '';
    el('local-turn-status').textContent = 'Checking authorization and policy, then making at most one local model request…';
    try {
      const response = await json('/api/a11oy/v1/atelier/local/turn', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${credential}` },
        body: JSON.stringify(request),
      }, 130000);
      const { answer, ...evidence } = response.value;
      el('local-receipt').textContent = JSON.stringify(evidence, null, 2);
      el('local-receipt-panel').hidden = false;
      if (response.ok && response.value.state === 'COMPLETED' && typeof answer === 'string' && answer.trim()) {
        await requireBoundOutcome(response.value, request, context, 'local_ollama', 'NO_KEY_LOCAL');
        el('local-answer').textContent = answer; el('local-answer').hidden = false;
        el('local-turn-status').textContent = 'Local response matched the submitted request (not any later draft). The server reports a persisted, signature-verified outcome; it is not independently verified in this browser.';
      } else {
        localUncertain = response.status >= 500;
        el('local-turn-status').textContent = `No completed local answer · ${response.value.code || response.value.state || `HTTP ${response.status}`}. No automatic retry was made.`;
      }
    } catch (_error) {
      localUncertain = true;
      el('local-turn-status').textContent = 'Local request outcome uncertain. No automatic retry was made; confirm before sending another request.';
    } finally { localSending = false; el('local-send').disabled = !localReady; }
  });
  el('cpu-turn-form').addEventListener('submit', async (event) => {
    event.preventDefault(); if (cpuSending || !cpuReady) return;
    const credential = el('cpu-operator-key').value.trim();
    if (!credential || /\s/.test(credential) || credential.length > 4096) { el('cpu-turn-status').textContent = 'Enter an Atelier operator credential, not a provider key.'; return; }
    const prompt = el('cpu-prompt').value;
    if (!prompt || prompt !== prompt.trim() || prompt.length > 1200 || prompt.includes('\0')) { el('cpu-turn-status').textContent = 'Enter one public prompt of at most 1,200 characters with no surrounding whitespace.'; return; }
    if (!el('cpu-public-ack').checked || cpuAcknowledgedPrompt !== prompt) { resetPublicConsent(); el('cpu-turn-status').textContent = 'Confirm this exact prompt is safe to disclose to the public CPU lab.'; return; }
    if (cpuUncertain && !window.confirm('The previous CPU lab request may have executed. Send a new request?')) return;
    const request = Object.freeze({ client_request_id: crypto.randomUUID(), prompt, declared: 'PUBLIC', public_share_acknowledged: true, max_output_tokens: 24 });
    const context = laneEvidence.cpu;
    cpuUncertain = false; cpuSending = true; el('cpu-send').disabled = true;
    resetPublicConsent();
    el('cpu-answer').hidden = true; el('cpu-answer').textContent = '';
    el('cpu-sources-panel').hidden = true; el('cpu-sources').replaceChildren(); el('cpu-citations').textContent = '';
    el('cpu-receipt-panel').hidden = true; el('cpu-receipt').textContent = '';
    el('cpu-turn-status').textContent = 'Checking operator permission and policy, then sending at most one public CPU lab request…';
    try {
      const response = await json('/api/a11oy/v1/atelier/cpu-lab/turn', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${credential}` },
        body: JSON.stringify(request),
      }, 90000);
      const { answer, evidence_handles, citations, ...evidence } = response.value;
      const sources = cpuPublicSources({ evidence_handles, citations });
      const proposal = response.ok && response.value.state === 'COMPLETED'
        && response.value.provider_decision === 'PROPOSAL'
        && response.value.provider_output_signature_status === 'UNSIGNED_LOCAL'
        && response.value.grounding_required === true
        && response.value.authority === 'NO_ACTION_AUTHORITY' && response.value.executed === false
        && sources !== null && typeof answer === 'string' && answer.trim();
      el('cpu-receipt').textContent = JSON.stringify(proposal
        ? { ...evidence, evidence_handles: sources.handles, citations: sources.citations } : evidence, null, 2);
      el('cpu-receipt-panel').hidden = false;
      if (proposal) {
        await requireBoundOutcome(response.value, request, context, 'szl_cpu_lab', 'NO_PROVIDER_KEY_PUBLIC_CPU_LAB');
        el('cpu-answer').textContent = answer; el('cpu-answer').hidden = false;
        for (const handle of sources.handles) {
          const row = document.createElement('li');
          row.textContent = `${handle.label}\n${handle.nodeKind} · ${handle.nodeId}\n${handle.note}`;
          el('cpu-sources').append(row);
        }
        el('cpu-citations').textContent = `Citations returned: ${sources.citations.length ? sources.citations.join(' · ') : 'None'}`;
        el('cpu-sources-panel').hidden = false;
        el('cpu-turn-status').textContent = 'Source-grounded proposal matched the submitted request (not any later draft). Lab record UNSIGNED_LOCAL; no action authority. Inspect public source handles and the Atelier outcome receipt below.';
      } else {
        const terminal = ['ABSTAIN', 'REVIEW', 'BLOCKED', 'DENIED', 'UNAVAILABLE'].includes(response.value.state);
        const invalidOutcome = !terminal;
        cpuUncertain = response.status >= 500 || response.value.code === 'LAB_TIMEOUT' || invalidOutcome;
        const state = invalidOutcome ? 'UNAVAILABLE' : response.value.state;
        const code = invalidOutcome ? 'CPU_LAB_INVALID_OUTCOME' : (response.value.code || `HTTP ${response.status}`);
        const reason = typeof response.value.reason_code === 'string'
          && /^[A-Z][A-Z0-9_]{0,63}$/.test(response.value.reason_code) ? ` · ${response.value.reason_code}` : '';
        el('cpu-turn-status').textContent = `No CPU lab proposal · ${state} · ${code}${reason}. No automatic retry was made.`;
      }
    } catch (_error) {
      cpuUncertain = true;
      el('cpu-turn-status').textContent = 'CPU lab outcome uncertain. No automatic retry was made; confirm before sending another request.';
    } finally { cpuSending = false; el('cpu-send').disabled = !cpuReady; }
  });
  refresh();
})();
