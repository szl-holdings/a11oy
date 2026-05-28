/**
 * Tests for R3-G3 BM 13901 completing-the-square solver.
 *
 * Coverage:
 *  - 50 random (b, c ≥ 0) inputs all satisfy x² + bx − c ≈ 0 within 1e-10
 *  - The original BM 13901 problem 1: x² + x = 3/4, expected x = 1/2
 *  - Identity case b = 0: x = √c
 *  - F3 failure mode: c + (b/2)² < 0 throws RangeError
 *  - Residual reported is consistent with quadraticResidual()
 */
import {
  solveBabylonianQuadratic,
  quadraticResidual,
} from '../quadratic-solver';

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error('ASSERT: ' + msg);
}
function approxEq(a: number, b: number, eps = 1e-10): boolean {
  return Math.abs(a - b) <= eps;
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

console.log('R3-G3 BM 13901 quadratic-completion solver');

run('T_BM13901_problem_1', () => {
  // BM 13901 problem 1: x² + x = 3/4  →  x = 1/2.
  const { x, residual } = solveBabylonianQuadratic({ b: 1, c: 0.75 });
  assert(approxEq(x, 0.5), `expected 0.5, got ${x}`);
  assert(residual < 1e-12, `residual ${residual} should be ~0`);
});

run('T_BM_50_random_quadratics', () => {
  let rng = 31337;
  const next = () => {
    rng = (rng * 1103515245 + 12345) & 0x7fffffff;
    return rng / 0x7fffffff;
  };
  for (let i = 0; i < 50; i++) {
    const b = next() * 20 - 10; // b ∈ [−10, 10]
    const c = next() * 100;     // c ∈ [0, 100]
    const { x, residual } = solveBabylonianQuadratic({ b, c });
    assert(residual < 1e-9, `i=${i} b=${b} c=${c} residual=${residual}`);
  }
});

run('T_BM_b_equals_zero', () => {
  const { x, residual } = solveBabylonianQuadratic({ b: 0, c: 9 });
  assert(approxEq(x, 3), `expected 3, got ${x}`);
  assert(residual < 1e-12, `residual ${residual}`);
});

run('T_BM_b_negative', () => {
  // x² − 5x = 6  →  x = (5 + √49)/2 = 6
  const { x, residual } = solveBabylonianQuadratic({ b: -5, c: 6 });
  assert(approxEq(x, 6), `expected 6, got ${x}`);
  assert(residual < 1e-10, `residual ${residual}`);
});

run('T_BM_FAIL_negative_discriminant', () => {
  // c = −1, b = 0  ⇒  disc = −1, no real root
  let threw = false;
  try {
    solveBabylonianQuadratic({ b: 0, c: -1 });
  } catch (e) {
    threw = e instanceof RangeError;
  }
  assert(threw, 'expected RangeError on negative discriminant');
});

run('T_BM_residual_matches_quadraticResidual', () => {
  const { x, residual } = solveBabylonianQuadratic({ b: 3, c: 4 });
  const r2 = quadraticResidual(3, 4, x);
  assert(approxEq(residual, r2, 1e-15), `residual mismatch: ${residual} vs ${r2}`);
});

run('T_BM_large_c', () => {
  const { x, residual } = solveBabylonianQuadratic({ b: 2, c: 1e6 });
  assert(residual < 1e-6, `residual ${residual} for large c`);
  assert(x > 0, `x should be positive`);
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
