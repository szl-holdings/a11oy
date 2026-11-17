/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
 * Doctrine v11 LOCKED.
 * Bounded, proposal-only edge client. No persistence, retries, or action authority.
 */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.SZLGovernedProposal = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  var PREFIX = 'szl.cloudflare-governed-inference-';
  var ENDPOINTS = {contract: '/api/v2/governed-contract', health: '/api/v2/governed-health', infer: '/api/v2/governed-infer'};
  var LOCKED = ['F1', 'F4', 'F7', 'F11', 'F12', 'F18', 'F19', 'F22'];
  var EFFORTS = {fast: 'Fast', frontier: 'Frontier', lora: 'SZL LoRA adapter · experimental'};
  var ids = 0;
  function object(v) { return !!v && typeof v === 'object' && !Array.isArray(v); }
  function text(v, fallback) { return typeof v === 'string' && v.trim() ? v : (fallback || 'UNAVAILABLE'); }
  function onlyKeys(v, keys) { return object(v) && Object.keys(v).every(function (key) { return keys.indexOf(key) !== -1; }); }
  function boolean(v) { return v === true ? 'Yes' : v === false ? 'No' : 'UNAVAILABLE'; }
  function count(v) { return Number.isSafeInteger(v) && v >= 0 ? String(v) : 'UNAVAILABLE'; }
  function digest(v) { return typeof v === 'string' && /^[a-f0-9]{64}$/.test(v); }
  function attempt(v) { return typeof v === 'string' && /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i.test(v); }
  function exactIds(v) { return Array.isArray(v) && JSON.stringify(v) === JSON.stringify(LOCKED); }
  function requireThat(ok, message) { if (!ok) throw new Error(message); }
  function limit(v, low, high, name) {
    requireThat(Number.isInteger(v) && v >= low && v <= high, 'Unavailable or unsupported input limit: ' + name);
    return v;
  }
  function prepareCapability(contract, health) {
    requireThat(object(contract) && contract.schema === PREFIX + 'contract/v1', 'The edge contract is unavailable or incompatible.');
    requireThat(object(health) && health.schema === PREFIX + 'health/v1', 'The edge health response is unavailable or incompatible.');
    requireThat(/^[a-f0-9]{40}$/.test(contract.source_revision || '') && health.source_revision === contract.source_revision, 'The contract and health revisions do not match. Refresh availability.');
    var runtime = contract.runtime || {}, receipt = contract.receipts || {}, governance = contract.governance || {}, doctrine = health.doctrine || {};
    requireThat(health.status === 'READY' && health.ai_binding === true, 'The edge runtime is unavailable.');
    requireThat(health.tools === false && health.action_authority === 'NONE' && health.receipt_persistence === 'NONE' && health.owned_model_served === false &&
      runtime.tools === false && runtime.autonomous_execution === false && runtime.action_authority === 'NONE' &&
      runtime.output_state === 'PROPOSAL_ONLY' && runtime.persistence === 'NONE' &&
      object(contract.owned_model) && contract.owned_model.served_by_this_runtime === false && typeof contract.owned_model.repository === 'string' &&
      receipt.signature_status === 'UNSIGNED_EDGE' && receipt.durable_storage === false && receipt.must_be_signed_before_consequential_action === true && receipt.prompt_or_evidence_text_persisted === false,
      'The advertised authority or receipt contract is unsupported.');
    requireThat(doctrine.state === 'LOCKED' && doctrine.locked_formula_count === 8 && exactIds(doctrine.locked_formula_ids) &&
      doctrine.lambda_status === 'CONJECTURE_1_ADVISORY' && doctrine.lambda_can_authorize === false &&
      governance.locked_formula_count === 8 && exactIds(governance.locked_formula_ids) &&
      governance.lambda && governance.lambda.status === 'CONJECTURE_1_ADVISORY' && governance.lambda.can_authorize === false,
      'The doctrine contract is unavailable or inconsistent.');
    requireThat(object(contract.endpoint) && Object.keys(ENDPOINTS).every(function (key) {
      return contract.endpoint[key] === ENDPOINTS[key];
    }), 'The advertised endpoint is unsupported. No request was sent.');
    var advertised = runtime.candidates || {};
    var efforts = Object.keys(EFFORTS).filter(function (key) {
      return Array.isArray(health.efforts) && health.efforts.indexOf(key) !== -1 &&
        Array.isArray(advertised[key]) && advertised[key].length > 0 &&
        advertised[key].every(function (candidate) { return typeof candidate === 'string' && candidate.length > 0 && candidate.length < 256; });
    });
    requireThat(efforts.length > 0, 'No mutually advertised inference effort is available.');
    if (efforts.indexOf('lora') !== -1) {
      requireThat(object(runtime.finetune) && text(runtime.finetune.id) !== 'UNAVAILABLE' &&
        text(runtime.finetune.adapter_repository) !== 'UNAVAILABLE' &&
        runtime.finetune.model_kind === 'SZL_TRAINED_LORA_ADAPTER_ON_CLOUDFLARE',
        'The advertised LoRA adapter identity is incomplete.');
    }
    var raw = contract.input_limits || {}, tokens = raw.max_new_tokens || {};
    var limits = {
      prompt: limit(raw.prompt_chars, 1, 12000, 'prompt'),
      items: limit(raw.evidence_items, 1, 8, 'evidence items'),
      item: limit(raw.evidence_item_chars, 1, 4000, 'evidence item'),
      total: limit(raw.evidence_total_chars, 1, 12000, 'total evidence'),
      minimum: limit(tokens.minimum, 16, 768, 'minimum tokens'),
      maximum: limit(tokens.maximum, 16, 768, 'maximum tokens'),
      defaultTokens: limit(tokens.default, 16, 768, 'default tokens')
    };
    requireThat(limits.minimum <= limits.defaultTokens && limits.defaultTokens <= limits.maximum, 'The token limits are inconsistent.');
    return {contract: contract, health: health, efforts: efforts, limits: limits, revision: contract.source_revision};
  }
  function validateInput(capability, prompt, effort, tokens, evidence) {
    var bounds = capability.limits, trimmed = String(prompt || '').trim();
    requireThat(trimmed.length > 0 && trimmed.length <= bounds.prompt, 'Enter a prompt of 1–' + bounds.prompt + ' characters.');
    requireThat(capability.efforts.indexOf(effort) !== -1, 'Choose an available effort.');
    requireThat(Number.isInteger(tokens) && tokens >= bounds.minimum && tokens <= bounds.maximum, 'Output tokens must be an integer from ' + bounds.minimum + ' to ' + bounds.maximum + '.');
    requireThat(Array.isArray(evidence) && evidence.length <= bounds.items, 'Too many evidence items.');
    var total = 0, supplied = [];
    evidence.forEach(function (item) {
      var excerpt = String(item.text || '').trim(), source = String(item.source || '').trim();
      if (!excerpt && !source) return;
      requireThat(excerpt.length > 0 && excerpt.length <= bounds.item, 'Each supplied evidence item needs 1–' + bounds.item + ' characters.');
      requireThat(source.length <= 512 && !/[\u0000-\u001f\u007f]/.test(source), 'Evidence sources must be at most 512 characters without control characters.');
      total += excerpt.length;
      supplied.push({text: excerpt, source: source || 'operator_supplied'});
    });
    requireThat(total <= bounds.total, 'Combined evidence exceeds ' + bounds.total + ' characters.');
    return {prompt: trimmed, effort: effort, max_new_tokens: tokens, evidence: supplied};
  }
  function validateProposal(body, capability, effort) {
    requireThat(object(body) && body.schema === PREFIX + 'response/v1', 'The edge returned an incompatible response.');
    var receipt = body.receipt || {}, payload = receipt.payload || {}, signature = receipt.signature || {};
    var model = body.model || {}, honesty = body.honesty || {}, formula = body.formula_authority || {};
    requireThat(onlyKeys(receipt, ['schema', 'payload', 'receipt_sha256', 'signature', 'prompt_or_evidence_text_persisted']) &&
      onlyKeys(signature, ['status', 'durable', 'must_be_signed_before_consequential_action']) &&
      onlyKeys(payload, ['schema', 'request_id', 'source_repository', 'source_revision', 'prompt_sha256', 'evidence_set_sha256',
        'output_sha256', 'model', 'model_kind', 'finetune_id', 'finetune_adapter_repository', 'owned_model_artifact',
        'owned_model_served', 'decision', 'authority_state', 'executed', 'formula_authority']) &&
      onlyKeys(payload.formula_authority, ['locked_proven_count', 'locked_proven_ids', 'lambda']) &&
      onlyKeys(payload.formula_authority.lambda, ['status', 'can_authorize']),
      'The receipt contains unsupported fields; no payload was displayed.');
    requireThat(body.state === 'PROPOSAL' && body.decision === 'review' &&
      body.executed === false && body.tool_execution === false && body.authority_state === 'NO_ACTION_AUTHORITY' &&
      honesty.output_is_model_proposal === true && honesty.output_is_signed === false &&
      honesty.output_is_owned_khipu_inference === false && honesty.durable_receipt_persistence === false &&
      honesty.action_authority === false && honesty.lambda_is_theorem === false,
      'The returned authority or honesty metadata is inconsistent.');
    requireThat(typeof body.output === 'string' && body.output.trim() && body.output.length <= 100000,
      'The edge returned no usable proposal.');
    requireThat(body.source_revision === capability.revision, 'The edge revision changed. Refresh availability before another request.');
    requireThat(attempt(body.attempt_id) && /^[a-f0-9]{32}$/.test(body.request_id || '') &&
      digest(body.output_sha256) && digest(receipt.receipt_sha256),
      'The response is missing valid attempt or receipt identifiers.');
    requireThat(receipt.schema === PREFIX + 'receipt/v1' && signature.status === 'UNSIGNED_EDGE' &&
      signature.durable === false && signature.must_be_signed_before_consequential_action === true &&
      receipt.prompt_or_evidence_text_persisted === false && payload.schema === receipt.schema &&
      payload.source_repository === 'szl-holdings/a11oy' && digest(payload.prompt_sha256) && digest(payload.evidence_set_sha256) &&
      payload.model === model.candidate && payload.model_kind === model.kind && payload.finetune_id === model.finetune_id &&
      payload.finetune_adapter_repository === model.finetune_adapter_repository && payload.owned_model_served === false &&
      payload.owned_model_artifact === capability.contract.owned_model.repository &&
      JSON.stringify(payload.formula_authority) === JSON.stringify(formula) &&
      payload.request_id === body.request_id && payload.output_sha256 === body.output_sha256 &&
      payload.source_revision === body.source_revision && payload.executed === false &&
      payload.authority_state === 'NO_ACTION_AUTHORITY' && payload.decision === 'REVIEW_PROPOSAL_ONLY',
      'The receipt does not match the returned proposal.');
    requireThat(model.owned_model_served === false && capability.contract.runtime.candidates[effort].indexOf(model.candidate) !== -1,
      'The returned model does not match the advertised candidates.');
    if (effort === 'lora') {
      var adapter = capability.contract.runtime.finetune;
      requireThat(model.kind === adapter.model_kind && model.finetune_id === adapter.id &&
        model.finetune_adapter_repository === adapter.adapter_repository, 'The returned LoRA adapter identity is inconsistent.');
    } else requireThat(model.kind === capability.contract.runtime.model_kind, 'The returned model kind is inconsistent.');
    requireThat(formula.locked_proven_count === 8 && exactIds(formula.locked_proven_ids) &&
      formula.lambda && formula.lambda.status === 'CONJECTURE_1_ADVISORY' && formula.lambda.can_authorize === false,
      'The returned formula authority is inconsistent.');
    return body;
  }
  function canonicalize(value) {
    if (Array.isArray(value)) return value.map(canonicalize);
    if (object(value)) {
      var sorted = {};
      Object.keys(value).sort().forEach(function (key) { sorted[key] = canonicalize(value[key]); });
      return sorted;
    }
    return value;
  }
  async function verifyHashes(body, cryptoImpl) {
    requireThat(cryptoImpl && cryptoImpl.subtle && typeof cryptoImpl.subtle.digest === 'function' &&
      typeof TextEncoder !== 'undefined', 'Hash verification is unavailable in this browser; no proposal or receipt was accepted.');
    async function sha256(value) {
      var bytes = new TextEncoder().encode(value);
      var hashed = await cryptoImpl.subtle.digest('SHA-256', bytes);
      return Array.from(new Uint8Array(hashed)).map(function (byte) { return byte.toString(16).padStart(2, '0'); }).join('');
    }
    var hashes = await Promise.all([sha256(body.output), sha256(JSON.stringify(canonicalize(body.receipt.payload)))]);
    requireThat(hashes[0] === body.output_sha256, 'The output hash does not match; no proposal or receipt was accepted.');
    requireThat(hashes[1] === body.receipt.receipt_sha256, 'The receipt payload hash does not match; no proposal or receipt was accepted.');
    return {output: true, receipt: true};
  }
  function mount(container, options) {
    options = options || {};
    if (!container || !container.ownerDocument || container.isConnected === false) return null;
    var doc = container.ownerDocument, win = doc.defaultView || window;
    var previous = container.querySelector('[data-governed-proposal]');
    if (previous) return previous._governedProposal;
    var fetcher = options.fetch || win.fetch.bind(win);
    var setTimer = options.setTimeout || win.setTimeout.bind(win), clearTimer = options.clearTimeout || win.clearTimeout.bind(win);
    var Controller = options.AbortController || win.AbortController;
    var readinessMs = options.readinessTimeout || 10000, inferenceMs = options.inferenceTimeout || 90000;
    var capability = null, active = null, loading = null, destroyed = false, serial = 0, evidenceRows = [];
    var prefix = 'governed-' + (++ids) + '-';
    function node(tag, className, value, parent) {
      var result = doc.createElement(tag);
      if (className) result.className = className;
      if (value !== undefined && value !== null) result.textContent = String(value);
      if (parent) parent.appendChild(result);
      return result;
    }
    function attr(element, name, value) { element.setAttribute(name, String(value)); return element; }
    function field(parent, label, kind, suffix) {
      var wrap = node('div', 'gp-field', null, parent);
      var labelNode = node('label', '', label, wrap), control = node(kind, '', null, wrap);
      control.id = prefix + suffix; labelNode.htmlFor = control.id;
      return control;
    }
    var card = node('section', 'gp-card', null, container);
    attr(card, 'data-governed-proposal', ''); attr(card, 'data-surface', 'dark');
    var heading = node('h2', '', 'Governed model proposal', card);
    heading.id = prefix + 'heading'; attr(card, 'aria-labelledby', heading.id);
    node('p', 'gp-description', 'Choose a model lane, supply evidence, and review the returned proposal and provenance.', card);
    node('p', 'gp-boundary', 'Proposal only · No action authority · Unsigned edge receipt · No durable receipt storage', card);
    var status = node('p', 'gp-status', 'CHECKING — reading the edge contract and availability.', card);
    attr(status, 'role', 'status'); attr(status, 'aria-live', 'polite'); attr(status, 'aria-atomic', 'true');
    var refresh = node('button', 'gp-secondary', 'Refresh availability', card); refresh.type = 'button';
    var availability = node('details', 'gp-details', null, card);
    node('summary', '', 'Availability and memory observation', availability);
    var availableBody = node('div', '', null, availability);
    var form = node('form', 'gp-form', null, card);
    var prompt = field(form, 'Prompt', 'textarea', 'prompt'); prompt.rows = 5; prompt.required = true; prompt.disabled = true;
    var controls = node('div', 'gp-controls', null, form);
    var effort = field(controls, 'Model lane', 'select', 'effort'); effort.disabled = true;
    var tokens = field(controls, 'Maximum output tokens', 'input', 'tokens'); tokens.type = 'number'; tokens.step = '1'; tokens.disabled = true;
    var laneInfo = node('p', 'gp-note', 'Model identity and evaluation status are unavailable until the contract is checked.', form);
    var evidenceDetails = node('details', 'gp-details', null, form);
    node('summary', '', 'Optional evidence', evidenceDetails);
    var evidenceHint = node('p', 'gp-note', 'Only text you explicitly submit is included in this request.', evidenceDetails);
    var evidenceHost = node('div', 'gp-evidence-items', null, evidenceDetails);
    var addEvidence = node('button', 'gp-secondary', 'Add evidence item', evidenceDetails); addEvidence.type = 'button'; addEvidence.disabled = true;
    var privacy = node('p', 'gp-note', 'Submitting sends the prompt and supplied evidence to the advertised Cloudflare Workers AI runtime. Inputs stay in this page until you leave; they are not saved in browser storage.', form);
    privacy.id = prefix + 'privacy'; attr(prompt, 'aria-describedby', privacy.id);
    var actions = node('div', 'gp-actions', null, form);
    var send = node('button', 'gp-primary', 'Generate proposal', actions); send.type = 'submit'; send.disabled = true;
    var cancel = node('button', 'gp-secondary', 'Stop waiting', actions); cancel.type = 'button'; cancel.disabled = true;
    var result = node('section', 'gp-result', null, card); result.hidden = true;
    function connected() {
      if (destroyed) return false;
      if (!card.isConnected) { destroy(); return false; }
      return true;
    }
    function pair(list, label, value) { node('dt', '', label, list); node('dd', '', value, list); }
    function memory(parent, value) {
      var brain = object(value) ? value : {}, observation = object(brain.memory_observation) ? brain.memory_observation : {};
      var binding = object(brain.model_binding) ? brain.model_binding : {};
      var list = node('dl', 'gp-facts', null, parent);
      pair(list, 'Second-brain state (reported)', text(brain.state));
      pair(list, 'Grounded navigation ready (reported)', boolean(brain.ready_for_grounded_navigation));
      pair(list, 'Public chunks (reported)', count(brain.public_chunk_count));
      pair(list, 'Memory observation status', text(observation.status));
      pair(list, 'Documents in corpus (reported)', count(observation.document_count));
      pair(list, 'Corpus chunks (reported)', count(observation.corpus_chunk_count));
      pair(list, 'Brain handles (reported)', count(observation.brain_handle_count));
      pair(list, 'Memory integrity (reported)', text(observation.integrity_state));
      pair(list, 'Expected Khipu model', text(binding.expected_model));
      pair(list, 'Observed served model', text(binding.served_model));
      pair(list, 'Exact model tag observed', boolean(binding.exact_tag_observed));
      pair(list, 'Artifact binding (reported)', text(binding.artifact_binding));
      node('p', 'gp-note', 'Corpus counts do not establish public access or retrieval into this answer. This lane receives public handles and operator-supplied evidence; private graph access is excluded.', parent);
    }
    function disabled(busy) {
      prompt.disabled = effort.disabled = tokens.disabled = !capability || busy;
      send.disabled = !capability || busy; cancel.disabled = !busy; refresh.disabled = busy || !!loading;
      addEvidence.disabled = !capability || busy || evidenceRows.length >= capability.limits.items;
      evidenceRows.forEach(function (row) { row.source.disabled = row.excerpt.disabled = row.remove.disabled = busy || !capability; });
      attr(form, 'aria-busy', busy ? 'true' : 'false');
    }
    function showLane() {
      if (!capability) return;
      if (capability.efforts.indexOf(effort.value) === -1) { laneInfo.textContent = 'Choose an available model lane. LoRA is experimental and requires explicit selection.'; return; }
      var runtime = capability.contract.runtime, isLora = effort.value === 'lora';
      laneInfo.textContent = isLora
        ? 'Experimental SZL-trained LoRA adapter; qualification pending. Cloudflare-hosted base candidate: ' + runtime.candidates[effort.value].join(', ') + '. Adapter: ' + text(runtime.finetune.adapter_repository) + '. Evaluation: ' + text(runtime.finetune.eval_status) + '.'
        : 'Cloudflare-hosted external candidate. Candidate order: ' + runtime.candidates[effort.value].join(', ') + '.';
    }
    function addRow() {
      if (!capability || active || evidenceRows.length >= capability.limits.items) return;
      var rowId = ++serial, wrap = node('fieldset', 'gp-evidence-item', null, evidenceHost);
      node('legend', '', 'Evidence item ' + rowId, wrap);
      var source = field(wrap, 'Source or reference', 'input', 'source-' + rowId); source.type = 'text'; source.maxLength = 512;
      var excerpt = field(wrap, 'Evidence excerpt', 'textarea', 'excerpt-' + rowId); excerpt.rows = 3; excerpt.maxLength = capability.limits.item;
      var remove = node('button', 'gp-secondary', 'Remove this item', wrap); remove.type = 'button'; attr(remove, 'aria-label', 'Remove evidence item ' + rowId);
      var row = {source: source, excerpt: excerpt, remove: remove};
      evidenceRows.push(row);
      remove.addEventListener('click', function () {
        evidenceRows.splice(evidenceRows.indexOf(row), 1); wrap.remove(); disabled(false);
      });
      disabled(false); source.focus();
    }
    async function json(url, init) {
      var response = await fetcher(url, Object.assign({credentials: 'same-origin', cache: 'no-store', redirect: 'error'}, init));
      var contentType = response.headers && response.headers.get('content-type') || '';
      if (!/^application\/json(?:\s*;|$)/i.test(contentType)) throw new Error('The edge route returned no JSON contract.');
      var body;
      try { body = await response.json(); } catch (_) { throw new Error('The edge returned malformed JSON.'); }
      if (!response.ok) {
        var failure = new Error('The edge returned HTTP ' + response.status + '.');
        if (object(body) && body.schema === PREFIX + 'error/v1' && /^[a-z0-9_]{1,100}$/.test(body.error || '') &&
          body.executed === false && body.authority_state === 'NO_ACTION_AUTHORITY') {
          failure.edgeCode = body.error; failure.attemptId = attempt(body.attempt_id) ? body.attempt_id : null;
        }
        throw failure;
      }
      return body;
    }
    async function refreshAvailability() {
      if (!connected() || loading || active) return;
      capability = null; loading = new Controller(); var thisLoad = loading;
      disabled(false); status.textContent = 'CHECKING — reading the edge contract and availability.';
      var timer = setTimer(function () { thisLoad.abort(); }, readinessMs);
      try {
        var responses = await Promise.all([
          json(ENDPOINTS.contract, {method: 'GET', signal: thisLoad.signal}),
          json(ENDPOINTS.health, {method: 'GET', signal: thisLoad.signal})
        ]);
        if (!connected() || thisLoad.signal.aborted) return;
        capability = prepareCapability(responses[0], responses[1]);
        var selected = effort.value; effort.replaceChildren();
        var placeholder = node('option', '', 'Choose a model lane', effort); placeholder.value = '';
        capability.efforts.forEach(function (key) { var option = node('option', '', EFFORTS[key], effort); option.value = key; });
        effort.value = capability.efforts.indexOf(selected) !== -1 ? selected : (capability.efforts.find(function (key) { return key !== 'lora'; }) || '');
        prompt.maxLength = capability.limits.prompt; tokens.min = capability.limits.minimum; tokens.max = capability.limits.maximum;
        if (!tokens.value) tokens.value = capability.limits.defaultTokens;
        evidenceHint.textContent = 'Up to ' + capability.limits.items + ' items; ' + capability.limits.item + ' characters each; ' + capability.limits.total + ' characters combined.';
        evidenceRows.forEach(function (row) { row.excerpt.maxLength = capability.limits.item; });
        availableBody.replaceChildren();
        var facts = node('dl', 'gp-facts', null, availableBody);
        pair(facts, 'Runtime source revision', capability.revision);
        pair(facts, 'Provider', text(capability.contract.runtime.provider));
        pair(facts, 'Receipt signature', 'UNSIGNED_EDGE — verification unavailable');
        pair(facts, 'Receipt persistence', 'NONE');
        memory(availableBody, capability.health.second_brain);
        showLane(); status.textContent = 'AVAILABLE — choose a model lane and explicitly generate a proposal. Model quality is not verified.';
      } catch (error) {
        if (connected()) {
          status.textContent = 'UNAVAILABLE — ' + (thisLoad.signal.aborted ? 'The availability check timed out.' : error.message);
          availableBody.replaceChildren(); node('p', 'gp-note', 'No compatible runtime contract is available. Refresh to check again.', availableBody);
          laneInfo.textContent = 'Model identity and evaluation status are unavailable.';
        }
      } finally {
        clearTimer(timer); thisLoad.abort(); if (loading === thisLoad) loading = null;
        if (connected()) disabled(false);
      }
    }
    function renderProposal(body, selectedEffort) {
      result.replaceChildren(); result.hidden = false;
      node('h3', '', 'Model proposal · unverified', result);
      node('pre', 'gp-output', body.output, result);
      node('p', 'gp-boundary', 'No action was authorized. The receipt is unsigned and has no durable edge storage.', result);
      var details = node('details', 'gp-details', null, result); details.open = true;
      node('summary', '', 'Inspect run evidence', details);
      var facts = node('dl', 'gp-facts', null, details), model = body.model;
      pair(facts, 'Attempt ID — this execution', body.attempt_id);
      pair(facts, 'Request ID — deterministic input identity', body.request_id);
      pair(facts, 'Source revision', body.source_revision);
      pair(facts, 'Served model', model.candidate);
      pair(facts, 'Model kind', model.kind);
      pair(facts, 'Fallback count (reported)', count(model.fallback_count));
      if (selectedEffort === 'lora') {
        pair(facts, 'Adapter repository', model.finetune_adapter_repository);
        pair(facts, 'Adapter ID', model.finetune_id);
        pair(facts, 'Adapter evaluation (contract)', text(capability.contract.runtime.finetune.eval_status));
      }
      pair(facts, 'Owned Khipu artifact served', 'No — artifact lineage only');
      pair(facts, 'Output SHA-256 — matched locally', body.output_sha256);
      pair(facts, 'Receipt SHA-256 — matched locally', body.receipt.receipt_sha256);
      pair(facts, 'Signature status', 'UNSIGNED_EDGE — no signature verification');
      pair(facts, 'Locked formula inventory', body.formula_authority.locked_proven_ids.join(', '));
      pair(facts, 'Lambda status', 'Conjecture 1 — advisory; cannot authorize actions');
      node('p', 'gp-note', 'The output and canonical receipt payload hashes match locally. Hash consistency does not authenticate a signer or prove a model claim. The receipt is unsigned. The locked formula inventory does not prove this generated answer.', details);
      var tiers = node('a', 'gp-link', 'Inspect pinned formula authority and limits', details); tiers.href = 'https://github.com/szl-holdings/a11oy/blob/1e5d070806696ac4d45d9bb411e1972a4bc5f849/formula_registry/formula-registry.v1.json';
      memory(details, body.second_brain);
      var handles = node('details', 'gp-details', null, details);
      node('summary', '', 'Returned evidence handles and citation claims', handles);
      node('p', 'gp-note', 'Returned citation references are unverified model claims. A handle does not establish that corpus contents were retrieved.', handles);
      function handleIds(values) { return Array.isArray(values) ? values.filter(function (value) { return typeof value === 'string' && /^(E[01]|U[1-8])$/.test(value); }).slice(0, 10) : []; }
      var safeHandles = Array.isArray(body.evidence_handles) ? body.evidence_handles.slice(0, 10).filter(object).map(function (handle) {
        return {id: handleIds([handle.id])[0] || 'UNAVAILABLE', source: text(handle.source), sha256: digest(handle.sha256) ? handle.sha256 : 'UNAVAILABLE', characters: count(handle.characters)};
      }) : [];
      var safeClaims = Array.isArray(body.claims) ? body.claims.slice(0, 10).filter(object).map(function (claim) {
        return {claim_sha256: digest(claim.claim_sha256) ? claim.claim_sha256 : 'UNAVAILABLE', status: claim.status === 'MODEL_PROPOSAL_UNVERIFIED' ? claim.status : 'UNAVAILABLE', evidence_handles: handleIds(claim.evidence_handles)};
      }) : [];
      node('pre', 'gp-json', JSON.stringify({evidence_handles: safeHandles, citations: handleIds(body.citations), claims: safeClaims}, null, 2), handles);
      var observation = body.anatomy_observation || {}, event = observation.event || {};
      var observed = node('dl', 'gp-facts', null, details);
      pair(observed, 'Observation delivery', text(observation.delivery));
      pair(observed, 'Observation persistence', text(observation.persistence));
      pair(observed, 'Observation attempt ID', event.attempt_id === body.attempt_id ? event.attempt_id : 'UNAVAILABLE');
      var download = node('button', 'gp-secondary', 'Download unsigned receipt', details); download.type = 'button';
      download.addEventListener('click', function () {
        var blob = new win.Blob([JSON.stringify({attempt_id: body.attempt_id, request_id: body.request_id, receipt: body.receipt}, null, 2) + '\n'], {type: 'application/json'});
        var url = win.URL.createObjectURL(blob), anchor = node('a', '', null, doc.body);
        anchor.href = url; anchor.download = 'a11oy-unsigned-receipt-' + body.attempt_id + '.json';
        anchor.click(); anchor.remove(); setTimer(function () { win.URL.revokeObjectURL(url); }, 1000);
      });
      var raw = node('details', 'gp-details', null, details);
      node('summary', '', 'Receipt payload', raw); node('pre', 'gp-json', JSON.stringify(body.receipt, null, 2), raw);
    }
    function stop(reason) {
      if (!active) return;
      var run = active; active = null; clearTimer(run.timer); run.controller.abort();
      if (connected()) {
        status.textContent = (reason === 'timeout' ? 'TIMED OUT' : 'STOPPED WAITING') + ' — server outcome unknown. Stopping the browser wait does not confirm server cancellation. No automatic retry was made.';
        disabled(false);
      }
    }
    async function submit(event) {
      if (event) event.preventDefault();
      if (!connected() || active || !capability) return;
      var request;
      try {
        request = validateInput(capability, prompt.value, effort.value, Number(tokens.value), evidenceRows.map(function (row) {
          return {source: row.source.value, text: row.excerpt.value};
        }));
      } catch (error) { status.textContent = 'CHECK INPUT — ' + error.message; return; }
      result.hidden = true; result.replaceChildren();
      var run = {controller: new Controller(), timer: null}; active = run; disabled(true);
      status.textContent = 'GENERATING — awaiting one bounded proposal. No action is being authorized.';
      run.timer = setTimer(function () { if (active === run) stop('timeout'); }, inferenceMs);
      try {
        var body = await json(ENDPOINTS.infer, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(request), signal: run.controller.signal});
        if (!connected() || active !== run || run.controller.signal.aborted) return;
        validateProposal(body, capability, request.effort);
        if (!connected() || active !== run || run.controller.signal.aborted) return;
        await verifyHashes(body, win.crypto);
        if (!connected() || active !== run || run.controller.signal.aborted) return;
        renderProposal(body, request.effort);
        status.textContent = 'PROPOSAL RECEIVED — hashes matched locally. Review required; unsigned receipt, no action authority.';
      } catch (error) {
        if (!connected() || active !== run) return;
        status.textContent = error.edgeCode
          ? 'FAILED — ' + error.edgeCode + (error.attemptId ? '. Attempt ID: ' + error.attemptId : '') + '. No automatic retry was made.'
          : 'OUTCOME UNKNOWN — ' + error.message + ' The server may have completed generation. No automatic retry was made.';
      } finally {
        clearTimer(run.timer);
        if (active === run) { active = null; if (connected()) disabled(false); }
      }
    }
    function destroy() {
      if (destroyed) return;
      destroyed = true; stop('leave');
      if (loading) loading.abort();
      if (observer) observer.disconnect();
      win.removeEventListener('pagehide', destroy);
      prompt.value = ''; evidenceRows.forEach(function (row) { row.source.value = ''; row.excerpt.value = ''; });
    }
    effort.addEventListener('change', showLane); addEvidence.addEventListener('click', addRow);
    refresh.addEventListener('click', refreshAvailability); cancel.addEventListener('click', function () { stop('cancel'); });
    form.addEventListener('submit', submit); win.addEventListener('pagehide', destroy);
    var observer = win.MutationObserver ? new win.MutationObserver(function () { if (!card.isConnected) destroy(); }) : null;
    if (observer) observer.observe(doc.documentElement || doc.body, {childList: true, subtree: true});
    var api = {element: card, refresh: refreshAvailability, destroy: destroy};
    card._governedProposal = api; api.ready = refreshAvailability();
    return api;
  }
  return {mount: mount, prepareCapability: prepareCapability, validateInput: validateInput, validateProposal: validateProposal, verifyHashes: verifyHashes};
}));
