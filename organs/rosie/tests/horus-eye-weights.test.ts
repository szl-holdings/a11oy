/**
 * horus-eye-weights.test.ts — round-trip + invariants for the 6-bit dyadic
 * receipt-weight encoding (R1-G2).
 *
 * Run: node --experimental-strip-types tests/horus-eye-weights.test.ts
 */

import assert from 'node:assert/strict';
import {
  HORUS_EYE_UNITS,
  HORUS_EYE_DENOMINATOR,
  HORUS_EYE_MAX_NUMERATOR,
  HORUS_EYE_MAX,
  encodeHorusEye,
  decodeHorusEye,
  horusEyeBits,
  horusEyeSum,
  horusEyeRoundtripError,
} from '../src/horus-eye-weights.ts';

const results: Array<{ id: string; ok: boolean; detail?: string }> = [];

function test(id: string, fn: () => void) {
  try {
    fn();
    results.push({ id, ok: true });
  } catch (e) {
    results.push({ id, ok: false, detail: e instanceof Error ? e.message : String(e) });
  }
}

test('T_horus_units_six', () => {
  assert.equal(HORUS_EYE_UNITS.length, 6);
});

test('T_horus_units_dyadic', () => {
  const expected = [1 / 2, 1 / 4, 1 / 8, 1 / 16, 1 / 32, 1 / 64];
  for (let i = 0; i < 6; i++) assert.equal(HORUS_EYE_UNITS[i], expected[i]);
});

test('T_horus_sum_eq_63_over_64', () => {
  assert.equal(horusEyeSum(), 63 / 64);
  assert.equal(HORUS_EYE_MAX, 63 / 64);
});

test('T_horus_denom_64', () => {
  assert.equal(HORUS_EYE_DENOMINATOR, 64);
  assert.equal(HORUS_EYE_MAX_NUMERATOR, 63);
});

test('T_horus_roundtrip_all_64_codes', () => {
  // For every code c ∈ [0, 63], decode then encode returns c.
  for (let c = 0; c <= 63; c++) {
    const w = decodeHorusEye(c);
    assert.equal(encodeHorusEye(w), c, `code ${c} round-trip`);
  }
});

test('T_horus_roundtrip_1000_random', () => {
  // 1000 random weights in [0, 63/64] — quantisation error ≤ 1/128.
  // Seeded LCG so the test is deterministic.
  let seed = 0xDEADBEEF >>> 0;
  const rng = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 0x100000000;
  };
  let maxErr = 0;
  for (let i = 0; i < 1000; i++) {
    const w = rng() * HORUS_EYE_MAX;
    const err = Math.abs(horusEyeRoundtripError(w));
    if (err > maxErr) maxErr = err;
    assert.ok(err <= 1 / 128 + 1e-12, `weight ${w}: err ${err} > 1/128`);
  }
  // Sanity: max observed error should be at most half a quantum (1/128).
  assert.ok(maxErr <= 1 / 128 + 1e-12, `maxErr ${maxErr} > 1/128`);
});

test('T_horus_determinism', () => {
  // Same input always produces same code — required for hash stability.
  for (let i = 0; i < 100; i++) {
    const w = i / 100 * HORUS_EYE_MAX;
    const c1 = encodeHorusEye(w);
    const c2 = encodeHorusEye(w);
    assert.equal(c1, c2);
  }
});

test('T_horus_bits_msb_first', () => {
  // Code 63 = 0b111111 → all six bits true.
  assert.deepEqual([...horusEyeBits(63)], [true, true, true, true, true, true]);
  // Code 32 = 0b100000 → only first bit (1/2) true.
  assert.deepEqual([...horusEyeBits(32)], [true, false, false, false, false, false]);
  // Code 1 = 0b000001 → only last bit (1/64) true.
  assert.deepEqual([...horusEyeBits(1)], [false, false, false, false, false, true]);
  // Code 0 → all false.
  assert.deepEqual([...horusEyeBits(0)], [false, false, false, false, false, false]);
});

test('T_horus_bits_reconstruct_code', () => {
  // bits[i] = 1 ↔ unit 2^-(i+1) contributes; sum of contributing units * 64 = code.
  for (let c = 0; c <= 63; c++) {
    const bits = horusEyeBits(c);
    let acc = 0;
    for (let i = 0; i < 6; i++) {
      if (bits[i]!) acc += HORUS_EYE_UNITS[i]!;
    }
    assert.equal(Math.round(acc * 64), c, `code ${c} reconstruction`);
  }
});

test('T_horus_reject_out_of_range_weight', () => {
  assert.throws(() => encodeHorusEye(-0.01), /out of range/);
  assert.throws(() => encodeHorusEye(HORUS_EYE_MAX + 0.01), /out of range/);
  assert.throws(() => encodeHorusEye(Number.NaN), /non-finite/);
  assert.throws(() => encodeHorusEye(Number.POSITIVE_INFINITY), /non-finite/);
});

test('T_horus_reject_out_of_range_code', () => {
  assert.throws(() => decodeHorusEye(-1), /out of range/);
  assert.throws(() => decodeHorusEye(64), /out of range/);
  assert.throws(() => decodeHorusEye(0.5), /non-integer/);
});

const failed = results.filter((r) => !r.ok);
for (const r of results) {
  console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.id}${r.detail ? '  — ' + r.detail : ''}`);
}
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length === 0 ? 0 : 1);
