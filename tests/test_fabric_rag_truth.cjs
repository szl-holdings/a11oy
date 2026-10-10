'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync(path.resolve(__dirname, '../pages/fabric.html'), 'utf8');
const start = html.indexOf('function ragNotReadyHTML(');
const end = html.indexOf('function renderWatt(', start);
assert.ok(start > 0 && end > start, 'Fabric RAG status and ask functions must be testable');
const ragCode = html.slice(start, end);
const queryEndpoint = '/api/a11oy/v1/rag/query';

function fixture(fetchStub = async () => { throw new Error('unexpected fetch'); }) {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, { innerHTML: '', style: { display: '' }, disabled: false, value: '' });
    return elements.get(id);
  }
  const context = {
    $: element,
    L: (_kind, label) => `<label>${label || _kind}</label>`,
    fmt: value => String(value),
    escapeHTML: value => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]),
    pendingHTML: reason => `<span>PENDING ${reason}</span>`,
    URLSearchParams,
    fetch: fetchStub,
  };
  vm.runInNewContext('var RAG_ASK_URL=null;\n' + ragCode + '\n;globalThis.rag={renderRag,askRag,askURL:()=>RAG_ASK_URL};', context);
  return { element, rag: context.rag };
}

function status(index, extra = {}) {
  return { url: '/api/a11oy/v1/rag/status', data: { index, query_endpoint: queryEndpoint, query_method: 'GET', ...extra } };
}

test('unbuilt index reports SEEDING or UNAVAILABLE and never enables ask', async () => {
  let fetches = 0;
  const { element, rag } = fixture(async () => { fetches++; throw new Error('should not query'); });
  element('rag-q').value = 'How many formulas?';
  assert.equal(rag.renderRag(status({ built: false, chunks: 12, build_state: { phase: 'seeding' } })), false);
  assert.match(element('rag-state').innerHTML, /SEEDING/);
  assert.doesNotMatch(element('rag-state').innerHTML, /LIVE|ready/);
  assert.equal(element('rag-qa').style.display, 'none');
  assert.equal(element('rag-ask').disabled, true);
  assert.equal(element('rag-q').disabled, true);
  assert.equal(rag.askURL(), null);
  await rag.askRag();
  assert.equal(fetches, 0);

  assert.equal(rag.renderRag(status({ built: false, build_state: { phase: 'error', error: '<index failed>' } })), false);
  assert.match(element('rag-state').innerHTML, /UNAVAILABLE/);
  assert.match(element('rag-state').innerHTML, /&lt;index failed&gt;/);
  assert.doesNotMatch(element('rag-state').innerHTML, /LIVE|ready/);
  assert.equal(rag.renderRag(null), false);
  assert.match(element('rag-state').innerHTML, /UNAVAILABLE/);
});

test('built flag and advertised public GET contract are both required', () => {
  const { element, rag } = fixture();
  assert.equal(rag.renderRag(status({ built: 'true' })), false);
  assert.equal(rag.renderRag(status({ built: true }, { query_method: 'POST' })), false);
  assert.equal(rag.renderRag(status({ built: true }, { query_endpoint: '/api/a11oy/v1/rag/estate/query' })), false);
  assert.equal(element('rag-qa').style.display, 'none');
  assert.equal(rag.askURL(), null);
  assert.match(element('rag-state').innerHTML, /UNAVAILABLE/);
});

test('ready ask uses only read-only GET with URLSearchParams, never POST', async () => {
  const calls = [];
  const { element, rag } = fixture(async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ grounded: true, answer: 'Eight locked formulas.', citations: ['proof'] }) };
  });
  assert.equal(rag.renderRag(status({ built: true, chunks: 12, files: 4 })), true);
  assert.equal(element('rag-qa').style.display, 'flex');
  assert.equal(element('rag-ask').disabled, false);
  assert.match(element('rag-state').innerHTML, /INDEX BUILT/);
  element('rag-q').value = '  Λ & receipts?  ';
  await rag.askRag();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.method, 'GET');
  assert.equal(Object.hasOwn(calls[0].options, 'body'), false);
  assert.equal(new URL(calls[0].url, 'https://a-11-oy.com').pathname, queryEndpoint);
  assert.equal(new URL(calls[0].url, 'https://a-11-oy.com').searchParams.get('q'), 'Λ & receipts?');
  assert.match(element('rag-state').innerHTML, /Eight locked formulas/);

  assert.equal(rag.renderRag(status({ built: false, build_state: { phase: 'seeding' } })), false);
  assert.equal(rag.askURL(), null);
  assert.equal(element('rag-ask').disabled, true);
  assert.doesNotMatch(element('rag-state').innerHTML, /INDEX BUILT|LIVE/);
});


function wattFixture() {
  const start = html.indexOf('function renderWatt(');
  const end = html.indexOf('function escapeHTML(', start);
  assert.ok(start > 0 && end > start, 'Fabric decision renderer must be testable');
  const element = { innerHTML: '' };
  const labels = [];
  const context = {
    $: () => element,
    L: (kind, label) => { labels.push({ kind, label }); return `<label>${label || kind}</label>`; },
    fmt: value => String(value),
    fmt1: value => Number(value).toFixed(1),
    shortHash: value => String(value).slice(0, 12),
    escapeHTML: value => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]),
    pendingHTML: reason => `<span>PENDING ${reason}</span>`,
  };
  vm.runInNewContext(html.slice(start, end) + '\n;globalThis.render=renderWatt;', context);
  return { element, render: context.render, labels };
}

const samplePlacement = {
  decision: 'placed', chosen_node: '<sample-node>', grid_price_eur_mwh: 42.5,
  grid_price_label: 'SAMPLE', savings_pct: 0.125, saving_label: 'MODELED',
  reason: 'synthetic fixture',
};

for (const [name, data] of [
  ['raw latest decision', { latest_decision: samplePlacement }],
  ['legacy receipt wrapper', { latest_decision: { decision: samplePlacement } }],
  ['recent decision fallback', { recent_decisions: [samplePlacement] }],
  ['flat decision fallback', samplePlacement],
  ['non-object latest fallback', { latest_decision: 'placed', recent_decisions: [samplePlacement] }],
  ['array latest fallback', { latest_decision: [], recent_decisions: [samplePlacement] }],
  ['null latest fallback', { latest_decision: null, recent_decisions: [samplePlacement] }],
  ['malformed wrapped decision', { latest_decision: { ...samplePlacement, decision: [] } }],
]) {
  test(`placement renderer preserves fields for ${name}`, () => {
    const { element, render } = wattFixture();
    assert.equal(render({ data }), true);
    assert.match(element.innerHTML, /42\.5/);
    assert.match(element.innerHTML, /&lt;sample-node&gt;/);
    assert.match(element.innerHTML, /12\.5%/);
    assert.doesNotMatch(element.innerHTML, /<sample-node>|no chosen node in the retained record/);
  });
}

test('raw no-choice decision preserves and escapes its reason', () => {
  const { element, render } = wattFixture();
  assert.equal(render({ data: { latest_decision: {
    decision: 'no-choice', chosen_node: null, reason: '<no eligible sample node>',
  } } }), true);
  assert.match(element.innerHTML, /no chosen node in the retained record/);
  assert.match(element.innerHTML, /&lt;no eligible sample node&gt;/);
  assert.doesNotMatch(element.innerHTML, /<no eligible sample node>/);
});


test('missing placement response preserves the pending state', () => {
  const { element, render } = wattFixture();
  assert.equal(render(null), false);
  assert.match(element.innerHTML, /PENDING/);
  assert.doesNotMatch(element.innerHTML, /chosen node:/);
});


const sourceEvidenceLabels = [
  'MEASURED', 'REPORTED', 'DECLARED', 'SIMULATED', 'SAMPLE',
  'MODELED', 'ROADMAP', 'UNKNOWN', 'UNAVAILABLE', 'BLOCKED',
];

for (const label of sourceEvidenceLabels) {
  test(`retained price and savings preserve source-declared ${label}`, () => {
    const { element, render, labels } = wattFixture();
    const data = { latest_decision: {
      ...samplePlacement, grid_price_label: label, saving_label: label,
    } };
    const before = JSON.stringify(data);
    assert.equal(render({ data }), true);
    assert.equal(JSON.stringify(data), before, 'rendering must not change the retained payload');
    assert.deepEqual(labels.map(item => item.kind), [label, label]);
    assert.match(element.innerHTML, /recorded grid price \u00b7 source-declared label/);
    assert.match(element.innerHTML, /recorded chosen node:/);
    assert.match(element.innerHTML, /recorded savings:/);
    assert.match(element.innerHTML, /labels are not independently verified/);
    assert.match(element.innerHTML, /Current reachability and execution: UNKNOWN/);
    assert.doesNotMatch(element.innerHTML, /LIVE|live grid|LOWEST|REACHABLE|ROUTING LAW|most-expensive/);
    if (label !== 'MEASURED') assert.doesNotMatch(element.innerHTML, /MEASURED/);
  });
}

for (const [name, value] of [
  ['missing', undefined], ['null', null], ['empty', ''], ['unrecognized', 'ESTIMATE'],
  ['live', 'LIVE'], ['lowercase', 'measured'], ['boolean', true],
  ['array', ['MEASURED']], ['object', { label: 'MEASURED' }],
  ['markup', '<img src=x onerror=alert(1)>'],
]) {
  test(`retained evidence labels stay UNKNOWN when ${name}`, () => {
    const { element, render, labels } = wattFixture();
    assert.equal(render({ data: { latest_decision: {
      ...samplePlacement, grid_price_label: value, saving_label: value,
    } } }), true);
    assert.deepEqual(labels.map(item => item.kind), ['UNKNOWN', 'UNKNOWN']);
    assert.doesNotMatch(element.innerHTML, /MEASURED|LIVE|MODELED|ESTIMATE|onerror|<img/);
  });
}

test('retained references and all free text are escaped without signature claims', () => {
  const { element, render, labels } = wattFixture();
  const data = {
    latest_decision: {
      ...samplePlacement, chosen_node: '<b>node</b>', saving: '<img src=x>',
      reason: '<script>reason</script>', signed: true, dsse: { signatures: [{}] },
    },
    chain: { head: '<img src=x>', length: '<b>length</b>' },
  };
  assert.equal(render({ data }), true);
  assert.match(element.innerHTML, /&lt;b&gt;node&lt;\/b&gt;/);
  assert.match(element.innerHTML, /recorded savings: <b>&lt;img src=x&gt;<\/b>/);
  assert.match(element.innerHTML, /recorded reason: &lt;script&gt;reason&lt;\/script&gt;/);
  assert.match(element.innerHTML, /unverified receipt reference &lt;img src=x&gt;/);
  assert.match(element.innerHTML, /recorded chain length &lt;b&gt;length&lt;\/b&gt;/);
  assert.doesNotMatch(element.innerHTML, /<img|<script|LIVE|VERIFIED|SIGNED|signature verified/);
  assert.ok(labels.every(item => sourceEvidenceLabels.includes(item.kind)));
});
