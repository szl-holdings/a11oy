/**
 * Tests for R1-G4 Akhmim/RMP self-verifying threshold tables.
 *
 * Coverage:
 *  - all 50 RMP 2/n entries verify in exact rational arithmetic
 *  - selfVerifyingLookup returns found+verified for valid n
 *  - selfVerifyingLookup returns not-found for n out of range
 *  - F3 failure modes: empty parts FAIL, zero denominator FAIL, negative
 *    part FAIL, intentionally-corrupted decomposition FAIL
 *  - 50 random table lookups (drawn from the 50 valid odd n) all verify
 */
import {
  RMP_TWO_OVER_N,
  verifyUnitFractionDecomposition,
  selfVerifyingLookup,
  lookupTwoOverN,
} from '../akhmim-table';

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error('ASSERT: ' + msg);
}

let passed = 0;
let failed = 0;
function run(name: string, fn: () => void): void {
  try {
    fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (e) {
    failed++;
    console.log(`  ✗ ${name}: ${(e as Error).message}`);
  }
}

console.log('R1-G4 Akhmim/RMP self-verifying table');

run('T_akhmim_all_50_entries_verify', () => {
  for (const [n, parts] of RMP_TWO_OVER_N) {
    const r = verifyUnitFractionDecomposition({ parts, num: 2, den: n });
    assert(r.ok, `n=${n} parts=${parts.join(',')} failed: ${r.ok ? '' : r.reason}`);
  }
  assert(RMP_TWO_OVER_N.size === 50, `expected 50 entries, got ${RMP_TWO_OVER_N.size}`);
});

run('T_akhmim_lookup_in_range', () => {
  const r = selfVerifyingLookup(13);
  assert(r.found, 'n=13 should be found');
  if (r.found) {
    assert(r.verified, 'n=13 should verify');
    assert(
      r.decomposition.parts.length === 3,
      `n=13 parts length=${r.decomposition.parts.length}, expected 3`,
    );
  }
});

run('T_akhmim_lookup_out_of_range', () => {
  const r = selfVerifyingLookup(4); // even
  assert(!r.found, 'n=4 (even) should not be found');
  const r2 = selfVerifyingLookup(103); // odd but > 101
  assert(!r2.found, 'n=103 (out of RMP range) should not be found');
});

run('T_akhmim_FAIL_empty_parts', () => {
  const r = verifyUnitFractionDecomposition({ parts: [], num: 2, den: 3 });
  assert(!r.ok, 'empty parts should FAIL');
});

run('T_akhmim_FAIL_zero_denominator', () => {
  const r = verifyUnitFractionDecomposition({ parts: [2, 6], num: 2, den: 0 });
  assert(!r.ok, 'zero den should FAIL');
});

run('T_akhmim_FAIL_negative_part', () => {
  const r = verifyUnitFractionDecomposition({ parts: [2, -6], num: 2, den: 3 });
  assert(!r.ok, 'negative part should FAIL');
});

run('T_akhmim_FAIL_corrupted_decomposition', () => {
  // 2/3 ≠ 1/2 + 1/7 (would be 9/14, not 2/3)
  const r = verifyUnitFractionDecomposition({ parts: [2, 7], num: 2, den: 3 });
  assert(!r.ok, 'corrupted decomposition should FAIL');
});

run('T_akhmim_50_random_lookups_verify', () => {
  const keys = Array.from(RMP_TWO_OVER_N.keys());
  let rng = 1729;
  const next = () => {
    rng = (rng * 1103515245 + 12345) & 0x7fffffff;
    return rng / 0x7fffffff;
  };
  for (let i = 0; i < 50; i++) {
    const k = keys[Math.floor(next() * keys.length)]!;
    const r = selfVerifyingLookup(k);
    assert(r.found && r.verified, `n=${k} lookup i=${i} failed`);
  }
});

run('T_akhmim_lookup_returns_undefined_even_n', () => {
  assert(lookupTwoOverN(8) === undefined, 'even n should return undefined');
  assert(lookupTwoOverN(100) === undefined, 'even n=100 should return undefined');
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
