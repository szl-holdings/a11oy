/* SPDX-License-Identifier: Apache-2.0 */
const test = require('node:test');
const assert = require('node:assert/strict');
const { derive, readBounded } = require('../static/landing-honest-bind.js');
for (const [name, input] of Object.entries({empty: {}, null: null, array: [], string: 'ok'})) {
  test(`missing count ${name} never becomes eight`, () => {
    const value = derive(input); assert.equal(value.count, null); assert.equal(value.state, 'UNAVAILABLE');
  });
}
for (const bad of [true, false, '8', -1, Infinity, NaN, 1.5, 100001]) {
  test(`invalid count ${String(bad)}`, () => {
    assert.equal(derive({locked_formula_count: bad}).countState, 'INVALID');
    assert.equal(derive({locked_formula_count: bad}).count, null);
  });
}
test('reported zero remains zero', () => assert.equal(derive({locked_formula_count: 0}).count, 0));
test('eight only follows explicit reported count', () => assert.equal(derive({doctrine_lock:{locked_formula_count:8}}).count, 8));
test('conflicting aliases', () => assert.equal(derive({locked_formula_count:8,doctrine_lock:{locked_formula_count:9}}).countState, 'CONFLICT'));
test('equal aliases including zero', () => assert.equal(derive({locked_formula_count:0,doctrine_lock:{locked_formula_count:0}}).count, 0));
test('doctrine metadata is not readiness', () => assert.equal(derive({doctrine:'v11',state:'LIVE'}).state, 'OBSERVED_METADATA'));
test('unknown nested truth does not produce evidence', () => assert.equal(derive({ok:true}).state, 'UNAVAILABLE'));
test('conflicting doctrine does not select convenient alias', () => assert.equal(derive({doctrine:'v11',doctrine_lock:{doctrine:'v12'}}).doctrine, null));
test('bounded valid JSON', async () => assert.deepEqual(await readBounded(new Response('{"x":0}',{headers:{'Content-Type':'application/json'}})), {x:0}));
test('rejects HTML success', async () => await assert.rejects(readBounded(new Response('<html/>',{headers:{'Content-Type':'text/html'}}))));
test('rejects failed response', async () => await assert.rejects(readBounded(new Response('{}',{status:503,headers:{'Content-Type':'application/json'}}))));
test('rejects oversized untrusted length', async () => await assert.rejects(readBounded(new Response('{}',{headers:{'Content-Type':'application/json','Content-Length':'999999'}}))));
test('rejects oversized chunk stream', async () => await assert.rejects(readBounded(new Response(' '.repeat(65537),{headers:{'Content-Type':'application/json'}}))));
test('rejects invalid UTF8', async () => await assert.rejects(readBounded(new Response(new Uint8Array([255]),{headers:{'Content-Type':'application/json'}}))));
