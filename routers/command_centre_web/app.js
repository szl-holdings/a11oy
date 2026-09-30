/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 */
'use strict';
(() => {
  const el = (id) => document.getElementById(id);
  let ready = false, sending = false, uncertain = false;

  async function json(url, options = {}, timeout = 15000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, { ...options, cache: 'no-store', credentials: 'same-origin', signal: controller.signal });
      if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('NON_JSON_RESPONSE');
      const value = await response.json();
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

  async function refresh() {
    el('refresh').disabled = true; ready = false; el('send').disabled = true;
    const results = await Promise.allSettled([
      json('/api/a11oy/v1/command-centre/manifest'), json('/api/build-info'),
      json('/api/a11oy/v1/atelier/health'), json('/api/a11oy/v1/command-centre/inventory'),
      json('/api/a11oy/v1/command-centre/study'),
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
      el('source-state').textContent = validRevision ? 'Runtime source observed' : 'Runtime identity incomplete';
      el('source-sha').textContent = validRevision ? revision : 'No valid 40-character source revision';
    } else { el('source-state').textContent = 'Build information unavailable'; el('source-sha').textContent = 'Not observed'; }
    const health = results[2];
    if (health.status === 'fulfilled') {
      const value = health.value.value; ready = health.value.ok && value.ready === true;
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
    el('send').disabled = !ready || sending; el('refresh').disabled = false;
  }

  el('refresh').addEventListener('click', refresh);
  el('forget-key').addEventListener('click', () => { el('operator-key').value = ''; });
  window.addEventListener('pagehide', () => { el('operator-key').value = ''; });
  el('turn-form').addEventListener('submit', async (event) => {
    event.preventDefault(); if (sending || !ready) return;
    const credential = el('operator-key').value.trim();
    if (!credential || /\s/.test(credential) || credential.length > 4096) { el('turn-status').textContent = 'Enter a valid Atelier operator credential, not the xAI API key.'; return; }
    if (uncertain && !window.confirm('The previous request may have executed at the provider. Sending again can incur another charge. Send a new request?')) return;
    uncertain = false; sending = true; el('send').disabled = true;
    el('answer').hidden = true; el('answer').textContent = ''; el('receipt-panel').hidden = true; el('receipt').textContent = '';
    el('turn-status').textContent = 'Checking authorization and policy, then making at most one provider request…';
    try {
      const response = await json('/api/a11oy/v1/atelier/turn', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${credential}` },
        body: JSON.stringify({ prompt: el('prompt').value, model: el('model').value, reasoning_effort: el('effort').value, declared: el('classification').value }),
      }, 130000);
      const { answer, ...evidence } = response.value;
      el('receipt').textContent = JSON.stringify(evidence, null, 2); el('receipt-panel').hidden = false;
      if (response.ok && response.value.state === 'COMPLETED' && typeof answer === 'string' && answer.trim()) {
        el('answer').textContent = answer; el('answer').hidden = false;
        el('turn-status').textContent = 'Final text received. Inspect the server’s signed outcome receipt below.';
      } else {
        uncertain = response.status >= 500 || response.value.code === 'PROVIDER_TIMEOUT';
        el('turn-status').textContent = `No completed answer · ${response.value.code || response.value.state || `HTTP ${response.status}`}. No automatic retry was made.`;
      }
    } catch (_error) {
      uncertain = true; el('turn-status').textContent = 'Request outcome uncertain. The provider may have executed it. No automatic retry was made; confirm before sending another request.';
    } finally { sending = false; el('send').disabled = !ready; }
  });
  refresh();
})();
