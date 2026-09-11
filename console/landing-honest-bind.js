/* SPDX-License-Identifier: Apache-2.0 — SZL Holdings
 * Source-owned replacement for #2100's binder. HTTP success != readiness.
 * Absent counts never become 8. This script grants no formula or action authority.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else api.mount(root.document, root.fetch.bind(root));
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const isObject = (v) => !!v && typeof v === 'object' && !Array.isArray(v);
  const boundedText = (v) => typeof v === 'string' && v.trim().length > 0 && v.length <= 128 ? v.trim() : null;
  const countValue = (v) => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0 && v <= 100000 ? v : null;

  function derive(data) {
    const view = { state: 'UNAVAILABLE', doctrine: null, service: null, count: null, countState: 'UNAVAILABLE' };
    if (!isObject(data)) return view;
    const lock = isObject(data.doctrine_lock) ? data.doctrine_lock : {};
    const first = boundedText(lock.doctrine), second = boundedText(data.doctrine);
    view.doctrine = first && second && first !== second ? null : first || second;
    const a = lock.locked_formula_count, b = data.locked_formula_count;
    const hasA = a !== undefined && a !== null, hasB = b !== undefined && b !== null;
    const ca = countValue(a), cb = countValue(b);
    if ((hasA && ca === null) || (hasB && cb === null)) view.countState = 'INVALID';
    else if (hasA && hasB && ca !== cb) view.countState = 'CONFLICT';
    else if (hasA || hasB) { view.count = hasA ? ca : cb; view.countState = 'REPORTED'; }
    view.service = boundedText(data.organ) || boundedText(data.service);
    if (view.doctrine || view.service || view.countState === 'REPORTED') view.state = 'OBSERVED_METADATA';
    return view;
  }

  async function readBounded(response) {
    if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('unavailable');
    const limit = 65536, length = response.headers.get('content-length');
    if (length !== null && (!/^\d+$/.test(length) || Number(length) > limit)) throw new Error('oversized');
    if (!response.body || typeof response.body.getReader !== 'function') throw new Error('bounded_transport_unavailable');
    const reader = response.body.getReader(), chunks = []; let size = 0;
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > limit) { await reader.cancel(); throw new Error('oversized'); }
        chunks.push(value);
      }
    } finally { reader.releaseLock(); }
    const raw = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { raw.set(chunk, offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(raw));
  }

  function mount(document, fetcher) {
    if (!document || typeof fetcher !== 'function') return;
    const $ = (id) => document.getElementById(id);
    const write = (id, value) => { const el = $(id); if (el) el.textContent = value; };
    let sequence = 0, active;
    function reset() {
      for (const id of ['nv-doctrine', 'nv-kernel', 'nv-service', 'nv-state']) write(id, 'UNAVAILABLE');
      const panel = $('nv-panel'); if (panel) { panel.classList.remove('is-live'); panel.dataset.observation = 'UNAVAILABLE'; }
    }
    async function refresh() {
      const run = ++sequence; active?.abort(); active = new AbortController(); const request = active;
      reset();
      const timer = setTimeout(() => request.abort(), 10000);
      try {
        const response = await fetcher('/api/a11oy/v1/honest', { signal: request.signal, cache: 'no-store', credentials: 'omit' });
        const view = derive(await readBounded(response));
        if (run !== sequence) return;
        write('nv-doctrine', view.doctrine || 'UNAVAILABLE');
        write('nv-service', view.service || 'UNAVAILABLE');
        write('nv-kernel', view.countState === 'REPORTED' ? `${view.count} locked · reported` : view.countState);
        write('nv-state', view.state === 'OBSERVED_METADATA' ? 'metadata observed · not readiness' : 'UNAVAILABLE');
        const panel = $('nv-panel'); if (panel) panel.dataset.observation = view.state;
      } catch (_) { if (run === sequence) reset(); }
      finally { clearTimeout(timer); }
    }
    const legacy = $('fw-main-sha');
    if (legacy) { legacy.id = 'fw-main-sha-retired'; legacy.textContent = ''; legacy.hidden = true; }
    document.addEventListener('szl:refresh-observation', refresh);
    void refresh();
  }
  return { derive, readBounded, mount };
});
