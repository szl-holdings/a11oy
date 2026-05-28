/**
 * Tests for R4-I1 Madhava alternating-series bound.
 *
 * Coverage:
 *  - arctan(1) = π/4 reconstruction to within 1e-3 at N=1000
 *  - madhavaRemainder strictly bounds the actual truncation error
 *  - PAC-Bayes refinement adds the remainder term to the TH13 slack
 *  - Input validation: |x| > 1 throws, non-integer N throws
 *  - Identity: madhavaArctan(0, N) = 0
 *
 * Run: npx tsx web/packages/a11oy-core/src/governance/__tests__/madhava-bound.test.ts
 */
import {
  madhavaArctan,
  madhavaRemainder,
  madhavaPACBayesRefinement,
} from '../madhava-bound';

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

console.log('R4-I1 Madhava alternating-series bound');

run('T_madhava_arctan_one_eq_pi_over_4', () => {
  // arctan(1) = π/4 ≈ 0.7853981633974483
  // Madhava-Leibniz remainder at x=1, N=1000:  1/(2·1000+1) ≈ 4.998e-4
  // Spec: within 1e-3 at N=1000.
  const N = 1000;
  const S = madhavaArctan(1, N);
  const err = Math.abs(S - Math.PI / 4);
  assert(err < 1e-3, `|S_N − π/4| = ${err}, need < 1e-3`);
  // And the Madhava remainder bound must dominate the true error:
  const R = madhavaRemainder(1, N);
  assert(err <= R + 1e-15, `actual err ${err} should be ≤ remainder ${R}`);
});

run('T_madhava_remainder_dominates_truncation_50_random_x', () => {
  let rng = 9001;
  const next = () => {
    rng = (rng * 1103515245 + 12345) & 0x7fffffff;
    return rng / 0x7fffffff;
  };
  for (let i = 0; i < 50; i++) {
    const x = next() * 0.95; // |x| ≤ 0.95 (strictly inside radius)
    const N = 5 + Math.floor(next() * 20);
    const S = madhavaArctan(x, N);
    const trueArctan = Math.atan(x);
    const err = Math.abs(S - trueArctan);
    const R = madhavaRemainder(x, N);
    assert(
      err <= R + 1e-15,
      `i=${i} x=${x} N=${N}: err ${err} > remainder ${R}`,
    );
  }
});

run('T_madhava_remainder_arctan_one_half_N10', () => {
  // |x|=0.5, N=10: remainder = 0.5^21 / 21 ≈ 2.27e-8
  const R = madhavaRemainder(0.5, 10);
  const S = madhavaArctan(0.5, 10);
  const err = Math.abs(S - Math.atan(0.5));
  assert(R < 1e-7, `remainder ${R} should be small`);
  assert(err <= R + 1e-15, `err ${err} ≤ R ${R}`);
});

run('T_madhava_arctan_zero_is_zero', () => {
  for (const N of [1, 5, 100, 1000]) {
    assert(madhavaArctan(0, N) === 0, `arctan(0) partial sum N=${N} ≠ 0`);
  }
});

run('T_madhava_FAIL_remainder_x_gt_1', () => {
  let threw = false;
  try {
    madhavaRemainder(1.5, 10);
  } catch (e) {
    threw = e instanceof RangeError;
  }
  assert(threw, 'expected RangeError on |x| > 1');
});

run('T_madhava_FAIL_invalid_N', () => {
  let threw = false;
  try {
    madhavaArctan(0.5, 0);
  } catch (e) {
    threw = e instanceof RangeError;
  }
  assert(threw, 'expected RangeError on N=0');
  threw = false;
  try {
    madhavaArctan(0.5, 1.5);
  } catch (e) {
    threw = e instanceof RangeError;
  }
  assert(threw, 'expected RangeError on N=1.5');
});

run('T_madhava_PACBayes_refinement_adds_remainder', () => {
  const result = madhavaPACBayesRefinement({
    slackTH13: 0.1,
    N: 20,
    x: 0.5,
    empiricalRiskN: 0.3,
  });
  const expectedR = madhavaRemainder(0.5, 20);
  assert(
    Math.abs(result.madhavaRemainder - expectedR) < 1e-15,
    `remainder mismatch: ${result.madhavaRemainder} vs ${expectedR}`,
  );
  const expectedBound = 0.3 + 0.1 + expectedR;
  assert(
    Math.abs(result.upperBound - expectedBound) < 1e-15,
    `upper bound mismatch: ${result.upperBound} vs ${expectedBound}`,
  );
});

run('T_madhava_PACBayes_refinement_monotone_in_N', () => {
  // Larger N → smaller remainder → tighter bound.
  const input = (N: number) => ({
    slackTH13: 0.1,
    N,
    x: 0.5,
    empiricalRiskN: 0.3,
  });
  const r10 = madhavaPACBayesRefinement(input(10));
  const r50 = madhavaPACBayesRefinement(input(50));
  assert(
    r50.upperBound < r10.upperBound,
    `expected r50 ${r50.upperBound} < r10 ${r10.upperBound}`,
  );
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
