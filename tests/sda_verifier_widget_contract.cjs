'use strict';

// Executes the real pinned widget. Only DOM elements and transport are stubbed;
// no provider calls, browser downloads, npm dependencies, or network access.
const assert = require('node:assert/strict');
const test = require('node:test');
const widget = require('../spaces/sda/assets/szl_verify_widget.js');
const VERIFY_URL = 'https://a-11-oy.com/api/a11oy/v1/verify/receipt';
const envelope = {
  payloadType: 'application/vnd.in-toto+json',
  payload: 'eyJ0ZXN0Ijp0cnVlfQ==',
  signatures: [{keyid: 'fixture-only', sig: 'not-a-real-signature'}],
};

global.fetch = async () => { throw new Error('unexpected transport'); };

function browser(responses) {
  const calls = [];
  const elements = Object.fromEntries(
    ['ta', 'url', 'out', 'go', 'sample'].map(name => [`.szlv-${name}`, {
      value: '', innerHTML: '', disabled: false,
      addEventListener(event, listener) {
        assert.equal(event, 'click');
        this.click = listener;
      },
    }]),
  );
  const host = {
    innerHTML: '',
    classList: {add(value) { assert.equal(value, 'szlv'); }},
    querySelector(selector) {
      assert.ok(this.innerHTML.includes(`class="${selector.slice(1)}`));
      assert.ok(elements[selector], `unknown mounted selector ${selector}`);
      return elements[selector];
    },
  };
  global.document = {
    getElementById() { return null; },
    createElement(tag) { assert.equal(tag, 'style'); return {}; },
    head: {appendChild(style) { assert.equal(style.id, 'szlv-css'); }},
  };
  global.fetch = async (url, options) => {
    const index = calls.length;
    calls.push({url, options});
    assert.ok(index < responses.length, 'unexpected extra fetch');
    const response = responses[index];
    if (response.error) throw response.error;
    return {
      ok: response.status >= 200 && response.status < 300,
      status: response.status,
      async json() {
        if (response.invalidJson) throw new SyntaxError('invalid response JSON');
        return response.data;
      },
    };
  };
  assert.equal(widget.mount(host).base, 'https://a-11-oy.com');
  return {
    calls,
    async verify({value, url = ''} = {}) {
      elements['.szlv-ta'].value = value === undefined ? '' : value;
      elements['.szlv-url'].value = url;
      elements['.szlv-go'].click();
      // Drain the widget's real asynchronous fetch/normalize/render chain.
      await new Promise(setImmediate);
      assert.equal(elements['.szlv-go'].disabled, false);
      return elements['.szlv-out'].innerHTML;
    },
  };
}

function assertPost(call, expectedBody) {
  assert.equal(call.url, VERIFY_URL);
  assert.equal(call.options.method, 'POST');
  assert.equal(call.options.headers['Content-Type'], 'application/json');
  assert.equal(call.options.cache, 'no-store');
  assert.equal(call.options.mode, 'cors');
  assert.ok(call.options.signal instanceof AbortSignal);
  const body = JSON.parse(call.options.body);
  assert.deepEqual(body, expectedBody);
  assert.equal(Object.hasOwn(body, 'url'), false);
}

test('canonical endpoint and DSSE signatures are preserved', () => {
  assert.equal(widget.verifyPath, '/api/a11oy/v1/verify/receipt');
  assert.deepEqual(widget._verifyBody(envelope), {envelope});
  assert.deepEqual(widget._verifyBody({envelope, receipt_id: ' fixture '}), {
    envelope, receipt_id: 'fixture',
  });
  assert.deepEqual(widget._verifyBody({receipt: envelope}), {envelope});
  assert.deepEqual(widget._verifyBody({receipt_id: ' fixture '}), {receipt_id: 'fixture'});
  assert.deepEqual(widget._verifyBody({receipt: ' fixture '}), {receipt_id: 'fixture'});
});

test('plain Unicode JSON is explicitly unsigned, never given a fabricated signature', () => {
  const input = {claim: 'prueba · λ · 🌐'};
  const body = widget._verifyBody(input);
  assert.equal(body.envelope.payloadType, 'application/vnd.in-toto+json');
  assert.deepEqual(body.envelope.signatures, []);
  assert.deepEqual(JSON.parse(Buffer.from(body.envelope.payload, 'base64').toString('utf8')), input);
});

for (const [name, value] of [['null', null], ['array', []], ['string', 'PASS'], ['boolean', true], ['number', 1]]) {
  test(`non-object ${name} is not a verifier body`, () => {
    assert.equal(widget._verifyBody(value), null);
  });
}

test('public receipt URL is fetched in the browser, then only its envelope is POSTed', async () => {
  const receiptUrl = 'https://public-fixture.invalid/receipt.json?fixture=1';
  const b = browser([
    {status: 200, data: envelope},
    {status: 200, data: {verdict: 'PARTIAL'}},
  ]);
  const html = await b.verify({url: receiptUrl});
  assert.equal(b.calls.length, 2);
  assert.equal(b.calls[0].url, receiptUrl);
  assert.equal(b.calls[0].options.method, 'GET');
  assert.equal(b.calls[0].options.cache, 'no-store');
  assert.equal(b.calls[0].options.mode, 'cors');
  assert.equal(b.calls[0].options.body, undefined);
  assertPost(b.calls[1], {envelope});
  assert.ok(html.includes('szlv-verdict warn'));
  assert.ok(html.includes('not a complete cryptographic green'));
});

test('plain public JSON follows the same canonical route with empty signatures', async () => {
  const input = {claim: 'fixture-only'};
  const b = browser([{status: 200, data: input}, {status: 200, data: {verdict: 'STRUCTURAL-ONLY'}}]);
  const html = await b.verify({url: 'https://public-fixture.invalid/plain.json'});
  assert.equal(b.calls.length, 2);
  assertPost(b.calls[1], widget._verifyBody(input));
  assert.deepEqual(JSON.parse(b.calls[1].options.body).envelope.signatures, []);
  assert.ok(html.includes('szlv-verdict warn'));
  assert.equal(html.includes('szlv-verdict ok'), false);
});

const failures = [
  ['401', {status: 401, data: {verdict: 'PASS'}}, 'HTTP 401'],
  ['403', {status: 403, data: {verdict: 'PASS'}}, 'HTTP 403'],
  ['429', {status: 429, data: {verdict: 'PASS'}}, 'rate-limited'],
  ['500', {status: 500, data: {verdict: 'PASS'}}, 'HTTP 500'],
  ['network', {error: new Error('transport fixture')}, 'unreachable'],
  ['abort', {error: Object.assign(new Error('aborted fixture'), {name: 'AbortError'})}, 'timed out'],
  ['invalid JSON', {status: 200, invalidJson: true}, 'HTTP 200'],
];
for (const [name, response, message] of failures) {
  test(`failed public receipt ${name} is never forwarded or rendered green`, async () => {
    const b = browser([response]);
    const html = await b.verify({url: 'https://public-fixture.invalid/receipt.json'});
    assert.equal(b.calls.length, 1);
    assert.equal(b.calls[0].options.method, 'GET');
    assert.ok(html.includes(message));
    assert.equal(html.includes('szlv-verdict'), false);
  });
  test(`verifier ${name} is not a PASS despite misleading response data`, async () => {
    const b = browser([response]);
    const html = await b.verify({value: JSON.stringify(envelope)});
    assert.equal(b.calls.length, 1);
    assertPost(b.calls[0], {envelope});
    assert.ok(html.includes(message));
    assert.equal(html.includes('szlv-verdict'), false);
  });
}

for (const verdict of ['PARTIAL', 'INCONCLUSIVE', 'STRUCTURAL-ONLY']) {
  test(`${verdict} remains explicitly advisory, never a complete green`, async () => {
    const b = browser([{status: 200, data: {verdict}}]);
    const html = await b.verify({value: JSON.stringify(envelope)});
    assertPost(b.calls[0], {envelope});
    assert.ok(html.includes(`>${verdict}</b>`));
    assert.ok(html.includes('szlv-verdict warn'));
    assert.ok(html.includes('not a complete cryptographic green'));
    assert.equal(html.includes('szlv-verdict ok'), false);
  });
}

for (const verdict of ['FAIL', 'UNKNOWN', undefined]) {
  test(`server verdict ${String(verdict)} is not upgraded to green`, async () => {
    const b = browser([{status: 200, data: {verdict}}]);
    const html = await b.verify({value: JSON.stringify(envelope)});
    assert.equal(b.calls.length, 1);
    assert.equal(html.includes('szlv-verdict ok'), false);
  });
}

test('PASS is displayed only after a successful canonical verifier response', async () => {
  const b = browser([{status: 200, data: {verdict: 'PASS'}}]);
  const html = await b.verify({value: JSON.stringify(envelope)});
  assert.equal(b.calls.length, 1);
  assertPost(b.calls[0], {envelope});
  assert.ok(html.includes('szlv-verdict ok'));
  assert.ok(html.includes('>PASS</b>'));
});

for (const value of ['', '{bad JSON', '[]', 'null', '"PASS"']) {
  test(`invalid input ${JSON.stringify(value)} makes no fetch and invents no verdict`, async () => {
    const b = browser([]);
    const html = await b.verify({value});
    assert.equal(b.calls.length, 0);
    assert.equal(html.includes('szlv-verdict'), false);
    assert.ok(html.includes('szlv-state muted'));
  });
}

test('untrusted server fields are escaped, including unknown verdicts and checks', async () => {
  const attack = '<img src=x onerror="fixture()">';
  const b = browser([{status: 200, data: {
    verdict: attack, detail: attack, kinds: [attack], service: attack,
    checks: [{status: attack, check: attack, detail: attack}],
    doctrine: {version: attack, lambda: attack}, verified_at: attack,
  }}]);
  const html = await b.verify({value: JSON.stringify(envelope)});
  assert.equal(html.includes('<img'), false);
  assert.ok(html.includes('&lt;img'));
  assert.ok(html.includes('&quot;fixture()&quot;'));
  assert.equal(html.includes('szlv-verdict ok'), false);
});
