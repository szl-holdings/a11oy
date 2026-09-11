/* SPDX-License-Identifier: Apache-2.0 */
const test = require('node:test');
const assert = require('node:assert/strict');
const { derive, paint } = require('../static/landing-honest-bind.js');

function doc() {
  const store = {};
  const panel = {
    classList: {
      _s: new Set(),
      contains(c) { return this._s.has(c); },
      add(c) { this._s.add(c); },
      remove(c) { this._s.delete(c); },
    },
    dataset: {},
  };
  return {
    getElementById(id) {
      if (id === 'nv-panel') return panel;
      if (!store[id]) store[id] = { textContent: 'UNAVAILABLE' };
      return store[id];
    },
    _panel: panel,
    _store: store,
  };
}

test('paint never grants is-live on reported eight', () => {
  const d = doc();
  d._panel.classList.add('is-live');
  paint(d, derive({ doctrine_lock: { locked_formula_count: 8 }, doctrine: 'v11', organ: 'a11oy' }));
  assert.equal(d._store['nv-kernel'].textContent, '8 locked · reported');
  assert.equal(d._store['nv-state'].textContent, 'metadata observed · not readiness');
  assert.equal(d._panel.classList.contains('is-live'), false);
});

test('paint keeps zero as zero', () => {
  const d = doc();
  paint(d, derive({ locked_formula_count: 0 }));
  assert.equal(d._store['nv-kernel'].textContent, '0 locked · reported');
});
