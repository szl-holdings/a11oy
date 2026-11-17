// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { Script, runInNewContext } from 'node:vm';

const files = ['console/index.html', 'pages/console.html', 'pages_console.html'];

// Simulated observations test the rendering contract; they are not live evidence.
function report(ready = false) {
  const readiness = {
    ready, status: ready ? 'READY' : 'NOT_READY', service_blockers: [],
    frontier: {
      ready, state: ready ? 'READY' : 'NOT_READY', ready_tiles: ['energy ledger'],
      blocked_tiles: ready ? [] : [{ name: 'Energy operator', reasons: ['operator_stopped'] }],
    },
  };
  return {
    status: ready ? 'REAL' : 'DEGRADED', health_state: ready ? 'OBSERVED' : 'DEGRADED',
    grounded: true, observed_at: '2026-11-16T23:00:00Z', source_http_status: 200,
    operational_readiness: readiness,
    recommendations: [{ severity: ready ? 'ok' : 'warn', organ: 'a11oy',
      finding: ready ? 'Observed ready' : 'operator_stopped', remedy: 'Refresh evidence' }],
    counts: { critical: 0, warn: ready ? 0 : 1, info: 0, ok: ready ? 1 : 0 },
    citations: [{ endpoint: '/api/a11oy/healthz',
      data: { service: 'a11oy', status: 'ok', operational_readiness: structuredClone(readiness) } }],
  };
}

function harness(source, fetcher) {
  const ui = { html: '', chart: null, clears: 0, requests: [] };
  const escape = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
  const api = runInNewContext(source + '\n({refresh:ask_recs,view:askRecommendationView})', {
    orgGet: (...args) => { ui.requests.push(args); return fetcher(); },
    killChart: () => { ui.chart = null; ui.clears++; },
    doughnut: (_id, labels, data) => { ui.chart = { labels: [...labels], data: [...data] }; },
    setHTML: (_id, html) => { ui.html = html; },
    addHTML: (_id, html) => { ui.html += html; },
    esc: escape, el: () => ({}), document: { documentElement: {} },
    getComputedStyle: () => ({ getPropertyValue: token => token }), TEAL: 'theme-info',
  });
  return { ...api, ui };
}

for (const file of files) {
  const html = readFileSync(new URL('../' + file, import.meta.url), 'utf8');
  const start = html.indexOf('// Recommendations consume the same readiness report');
  const handler = html.indexOf('async function ask_recs(){', start);
  const end = html.indexOf('\n}\n', handler) + 3;
  assert.ok(start >= 0 && handler > start && end > handler, file + ' has the observed reader');
  const source = html.slice(start, end);

  test(file + ': shipped inline script parses', () => {
    const scripts = [...html.matchAll(/<script(?:[\s/][^>]*)?>([\s\S]*?)<\/script(?:[\s/][^>]*)?>/gi)]
      .map(match => match[1]).filter(script => script.includes('async function ask_recs(){'));
    assert.equal(scripts.length, 1);
    assert.doesNotThrow(() => new Script(scripts[0]));
  });

  test(file + ': renders blocked findings and remedies with escaped text', async () => {
    const value = report();
    value.recommendations[0].finding += ' <img src=x onerror=alert(1)>';
    const h = harness(source, async () => value);
    await h.refresh();
    assert.match(h.ui.html, /NOT_READY/);
    assert.match(h.ui.html, /operator_stopped/);
    assert.match(h.ui.html, /Refresh evidence/);
    assert.match(h.ui.html, /&lt;img/);
    assert.doesNotMatch(h.ui.html, /<img/);
    assert.deepEqual(h.ui.chart.data, [0, 1, 0, 0]);
    assert.deepEqual(h.ui.requests, [['core', '/api/a11oy/v1/operator/recommend']]);
  });

  test(file + ': ready requires consistent observed readiness and its citation', async () => {
    const h = harness(source, async () => report(true));
    await h.refresh();
    assert.match(h.ui.html, />READY</);
    assert.deepEqual(h.ui.chart.data, [0, 0, 0, 1]);
    const mutations = [
      value => { value.operational_readiness.ready = false; },
      value => { value.operational_readiness.frontier.state = 'NOT_READY'; },
      value => { value.citations[0].data.operational_readiness.ready = false; },
      value => { value.grounded = false; },
      value => { value.source_http_status = 503; },
    ];
    for (const mutate of mutations) {
      const value = report(true);
      mutate(value);
      const rejected = harness(source, async () => value);
      await rejected.refresh();
      assert.match(rejected.ui.html, /UNAVAILABLE/);
      assert.equal(rejected.ui.chart, null);
    }
  });

  test(file + ': malformed or empty findings never become all clear', async () => {
    for (const value of [null, {}, { ...report(), recommendations: [] },
      { ...report(), counts: { critical: 0, warn: 0, info: 0, ok: 1 } },
      { ...report(), recommendations: [{}] }, { ...report(), citations: [] }]) {
      const h = harness(source, async () => value);
      await h.refresh();
      assert.match(h.ui.html, /UNAVAILABLE/);
      assert.doesNotMatch(h.ui.html, /all clear/);
      assert.equal(h.ui.chart, null);
    }
  });

  test(file + ': refresh and failure clear the previous ready chart', async () => {
    let fail = false;
    const h = harness(source, async () => {
      if (fail) throw new Error('connection failed');
      return report(true);
    });
    await h.refresh();
    assert.ok(h.ui.chart);
    fail = true;
    const pending = h.refresh();
    assert.equal(h.ui.chart, null);
    assert.match(h.ui.html, /Observing readiness/);
    await pending;
    assert.equal(h.ui.chart, null);
    assert.match(h.ui.html, /UNAVAILABLE/);
    assert.doesNotMatch(h.ui.html, />READY</);
  });

  test(file + ': late old success cannot replace a newer failed observation', async () => {
    let resolveOld, request = 0;
    const h = harness(source, () => ++request === 1
      ? new Promise(resolve => { resolveOld = resolve; })
      : Promise.reject(new Error('latest observation failed')));
    const old = h.refresh();
    await h.refresh();
    resolveOld(report(true));
    await old;
    assert.match(h.ui.html, /UNAVAILABLE/);
    assert.match(h.ui.html, /latest observation failed/);
    assert.equal(h.ui.chart, null);
  });
}
