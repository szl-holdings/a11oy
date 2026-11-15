// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import assert from 'node:assert/strict';

const bits = (value, length) => Array.from({ length }, (_, i) => Boolean(value & (1 << i)));
const distance = (a, b) => a.filter((bit, i) => bit !== b[i]).length;

// Bounded generated-input tests of classical byte/receipt helpers. These are not
// quantum error-correction experiments or a proof of the cited Lean modules.
export const properties = [
  ['byte distance equals differing bit positions', (q, check) => {
    for (let a = 0; a < 256; a++) for (let b = 0; b < 256; b++) check(() => {
      assert.equal(q.hammingDistByte(a, b), distance(bits(a, 8), bits(b, 8)));
    });
  }],
  ['boolean distance, weight and mismatched lengths', (q, check) => {
    for (let n = 0; n <= 6; n++) for (let a = 0; a < 2 ** n; a++) {
      const x = bits(a, n);
      check(() => {
        assert.equal(q.hammingWeight(x), x.filter(Boolean).length);
        assert.equal(q.hammingDist(x, x), 0);
        assert.throws(() => q.hammingDist(x, [...x, false]), /length mismatch/);
      });
      for (let b = 0; b < 2 ** n; b++) check(() => {
        const y = bits(b, n);
        assert.equal(q.hammingDist(x, y), distance(x, y));
        assert.equal(q.hammingDist(x, y), q.hammingDist(y, x));
      });
    }
  }],
  ['minimum distance covers every unordered pair', (q, check) => {
    check(() => { assert.equal(q.minDistance([]), 0); assert.equal(q.minDistance([[true]]), 0); });
    for (let seed = 0; seed < 256; seed++) check(() => {
      const words = [seed, seed ^ 255, (seed + 1) & 255, (seed * 17) & 255].map(x => bits(x, 8));
      const expected = Math.min(...words.flatMap((x, i) => words.slice(i + 1).map(y => distance(x, y))));
      assert.equal(q.minDistance(words), expected);
      assert.equal(q.minDistance([...words].reverse()), expected);
    });
  }],
  ['nine independent receipt copies retain payload and lineage', (q, check) => {
    for (let payload = 0; payload < 256; payload++) check(() => {
      const logical = { payload, lineage: payload ^ 255 };
      const bundle = q.shorEncode(logical);
      assert.equal(bundle.length, 9);
      for (const receipt of bundle) { assert.deepEqual(receipt, logical); assert.notEqual(receipt, logical); }
      assert.equal(new Set(bundle).size, 9);
      bundle[0].lineage ^= 255;
      assert.equal(logical.lineage, payload ^ 255);
      assert.equal(bundle[1].lineage, payload ^ 255);
    });
  }],
  ['receipt majority survives every location set of up to four corruptions', (q, check) => {
    const masks = Array.from({ length: 512 }, (_, i) => bits(i, 9));
    for (let payload = 0; payload < 256; payload++) for (const mask of masks) check(() => {
      const other = (payload + 1) & 255;
      const bundle = q.shorEncode({ payload, lineage: payload ^ 255 });
      mask.forEach((corrupt, i) => { if (corrupt) bundle[i] = { payload: other, lineage: 0 }; });
      const expected = mask.filter(Boolean).length <= 4 ? payload : other;
      assert.equal(q.shorMajorityPayload(bundle), expected);
    });
  }],
  ['CSS byte mapping round-trip and single-bit corruption', (q, check) => {
    const seen = new Set();
    for (let byte = 0; byte < 256; byte++) {
      const pair = q.classicalToCSS(byte);
      check(() => {
        assert.equal(pair.xParity, byte);
        assert.equal(pair.zParity, 255 - byte);
        assert.equal(q.cssConsistent(pair), true);
        const key = JSON.stringify(pair);
        assert.equal(seen.has(key), false); seen.add(key);
      });
      for (let bit = 0; bit < 8; bit++) check(() => {
        assert.equal(q.cssConsistent({ ...pair, xParity: pair.xParity ^ (1 << bit) }), false);
        assert.equal(q.cssConsistent({ ...pair, zParity: pair.zParity ^ (1 << bit) }), false);
      });
    }
  }],
  ['vertex parity and site identity preserve both coordinates', (q, check) => {
    for (let seed = 0; seed < 64; seed++) {
      const sites = [0, 1, 2, 3].map(i => ({ agent: seed + (i % 2), slice: seed + Math.floor(i / 2) }));
      const vertex = Object.fromEntries(['n', 's', 'e', 'w'].map((k, i) => [k, sites[i]]));
      for (let pattern = 0; pattern < 16; pattern++) check(() => {
        const errors = bits(pattern, 4);
        const errs = site => errors[sites.findIndex(s => s.agent === site.agent && s.slice === site.slice)];
        assert.equal(q.vertexParity(errs, vertex), errors.filter(Boolean).length % 2 === 1);
      });
      for (const target of sites) check(() => {
        const err = q.singleSiteError(target);
        assert.equal(err({ ...target }), true);
        assert.equal(err({ ...target, agent: target.agent + 1000 }), false);
        assert.equal(err({ ...target, slice: target.slice + 1000 }), false);
        assert.equal(q.vertexParity(err, vertex), true);
      });
      check(() => {
        assert.equal(q.vertexParity(q.allErrors(), vertex), false);
        assert.equal(q.vertexParity(q.noErrors(), vertex), false);
      });
    }
  }],
];

export function executeProperties(q, suite = properties) {
  assert.ok(suite.length > 0, 'property suite must not be empty');
  const results = [];
  for (const [name, run] of suite) {
    let cases = 0;
    run(q, fn => { fn(); cases++; });
    assert.ok(cases > 0, `${name}: no completed input cases`);
    results.push({ name, cases });
  }
  return { properties: results.length, cases: results.reduce((n, r) => n + r.cases, 0), results };
}
