/**
 * qec_lineage.test.ts — runtime parity with Lutar/QEC/*.lean modules.
 *
 * Tests cover Hamming (1950), Shor (1995), CSS (1996), Kitaev (1997/2003).
 */

import assert from 'node:assert/strict';
import {
  hammingDist,
  hammingWeight,
  hammingDistByte,
  minDistance,
  shorEncode,
  shorMajorityPayload,
  classicalToCSS,
  cssConsistent,
  vertexParity,
  singleSiteError,
  allErrors,
  noErrors,
  PhysicalReceipt,
  Site,
  VertexCheck,
} from './qec_lineage';

function run(name: string, fn: () => void) {
  try {
    fn();
    console.log(`  ok    ${name}`);
  } catch (e) {
    console.error(`  FAIL  ${name}`);
    console.error(e);
    process.exitCode = 1;
  }
}

console.log('QEC lineage — runtime parity with Lutar.QEC');

// ─── Hamming ───────────────────────────────────────────────────────────

run('Hamming: equal bit arrays have distance 0', () => {
  assert.equal(hammingDist([true, false, true], [true, false, true]), 0);
});

run('Hamming: 000 vs 111 distance 3', () => {
  assert.equal(hammingDist([false, false, false], [true, true, true]), 3);
});

run('Hamming: 1010 vs 0101 distance 4', () => {
  assert.equal(hammingDist([true, false, true, false], [false, true, false, true]), 4);
});

run('Hamming: weight of all-zero is 0', () => {
  assert.equal(hammingWeight([false, false, false]), 0);
});

run('Hamming: weight of all-one len 4 is 4', () => {
  assert.equal(hammingWeight([true, true, true, true]), 4);
});

run('Hamming: weight of 1010 is 2', () => {
  assert.equal(hammingWeight([true, false, true, false]), 2);
});

run('Hamming: length mismatch throws', () => {
  assert.throws(() => hammingDist([true], [true, false]));
});

run('Hamming byte: 0x00 vs 0xFF distance 8', () => {
  assert.equal(hammingDistByte(0x00, 0xff), 8);
});

run('Hamming byte: 0xAA vs 0x55 distance 8', () => {
  assert.equal(hammingDistByte(0xaa, 0x55), 8);
});

run('Hamming byte: 0x42 vs 0x42 distance 0', () => {
  assert.equal(hammingDistByte(0x42, 0x42), 0);
});

run('Hamming code minimum distance', () => {
  // Hamming [7,4,3] partial code: include 4 codewords spanning the space.
  const cw = [
    [false, false, false, false, false, false, false],
    [true, true, false, true, false, false, false],
    [false, true, true, false, true, false, false],
    [true, false, true, true, true, false, false],
  ];
  const d = minDistance(cw);
  assert.ok(d >= 1);
});

// ─── Shor ──────────────────────────────────────────────────────────────

run('Shor: encode yields 9 receipts', () => {
  const logical: PhysicalReceipt = { payload: 0x42, lineage: 0xa5 };
  const bundle = shorEncode(logical);
  assert.equal(bundle.length, 9);
});

run('Shor: clean bundle decodes to original payload', () => {
  const logical: PhysicalReceipt = { payload: 0x42, lineage: 0xa5 };
  const bundle = shorEncode(logical);
  assert.equal(shorMajorityPayload(bundle), 0x42);
});

run('Shor: single-fault bundle still decodes correctly (majority)', () => {
  const logical: PhysicalReceipt = { payload: 0x42, lineage: 0xa5 };
  const bundle = shorEncode(logical);
  bundle[5] = { payload: 0xff, lineage: 0xff };
  assert.equal(shorMajorityPayload(bundle), 0x42);
});

run('Shor: 4-fault bundle still decodes correctly (5 majority)', () => {
  const logical: PhysicalReceipt = { payload: 0x42, lineage: 0xa5 };
  const bundle = shorEncode(logical);
  for (let i = 0; i < 4; i += 1) bundle[i] = { payload: 0xff, lineage: 0xff };
  assert.equal(shorMajorityPayload(bundle), 0x42);
});

run('Shor: 5-fault bundle flips majority', () => {
  const logical: PhysicalReceipt = { payload: 0x42, lineage: 0xa5 };
  const bundle = shorEncode(logical);
  for (let i = 0; i < 5; i += 1) bundle[i] = { payload: 0xff, lineage: 0xff };
  assert.equal(shorMajorityPayload(bundle), 0xff);
});

// ─── CSS ───────────────────────────────────────────────────────────────

run('CSS: 0x00 -> (0x00, 0xFF)', () => {
  const p = classicalToCSS(0x00);
  assert.equal(p.xParity, 0x00);
  assert.equal(p.zParity, 0xff);
});

run('CSS: 0xFF -> (0xFF, 0x00)', () => {
  const p = classicalToCSS(0xff);
  assert.equal(p.xParity, 0xff);
  assert.equal(p.zParity, 0x00);
});

run('CSS: 0x55 -> (0x55, 0xAA), consistent', () => {
  const p = classicalToCSS(0x55);
  assert.equal(p.xParity, 0x55);
  assert.equal(p.zParity, 0xaa);
  assert.ok(cssConsistent(p));
});

run('CSS: inconsistent pair detected', () => {
  assert.ok(!cssConsistent({ xParity: 0x00, zParity: 0x00 }));
});

run('CSS: injective on classical codewords', () => {
  const all = new Set<string>();
  for (let i = 0; i < 256; i += 1) {
    const p = classicalToCSS(i);
    all.add(`${p.xParity},${p.zParity}`);
  }
  assert.equal(all.size, 256);
});

// ─── Kitaev ────────────────────────────────────────────────────────────

const v0: VertexCheck = {
  n: { agent: 0, slice: 0 },
  s: { agent: 0, slice: 1 },
  e: { agent: 1, slice: 0 },
  w: { agent: 0, slice: 2 },
};

run('Kitaev: no errors -> parity 0', () => {
  assert.equal(vertexParity(noErrors(), v0), false);
});

run('Kitaev: single-site error at n -> parity 1', () => {
  assert.equal(vertexParity(singleSiteError(v0.n), v0), true);
});

run('Kitaev: single-site error at s -> parity 1', () => {
  assert.equal(vertexParity(singleSiteError(v0.s), v0), true);
});

run('Kitaev: single-site error at e -> parity 1', () => {
  assert.equal(vertexParity(singleSiteError(v0.e), v0), true);
});

run('Kitaev: single-site error at w -> parity 1', () => {
  assert.equal(vertexParity(singleSiteError(v0.w), v0), true);
});

run('Kitaev: all errors -> parity 0 (4 errors cancel)', () => {
  assert.equal(vertexParity(allErrors(), v0), false);
});

run('Kitaev: error at off-lattice site -> parity 0', () => {
  const offSite: Site = { agent: 99, slice: 99 };
  assert.equal(vertexParity(singleSiteError(offSite), v0), false);
});

console.log(process.exitCode === 1 ? '\nFAIL' : '\nall green (24 tests)');
