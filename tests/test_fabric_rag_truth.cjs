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
