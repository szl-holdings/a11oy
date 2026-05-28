/**
 * Tests for R1-G1 false-position calibration.
 *
 * Coverage:
 *  - exact recovery on 50 random affine gates
 *  - identity case (target = y₁ → x* = x₁)
 *  - F3 failure modes: dx=0 and dy=0 both throw RangeError
 *  - residual is zero up to floating-point error
 */
import {
  falsePosition,
  falsePositionResidual,
  type AffineSample,
} from '../false-position';

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error('ASSERT: ' + msg);
}

function approxEq(a: number, b: number, eps = 1e-9): boolean {
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

console.log('R1-G1 false-position calibration');

run('T_aha_recovery_50_random_gates', () => {
  let rng = 1729;
  const next = () => {
    rng = (rng * 1103515245 + 12345) & 0x7fffffff;
    return (rng / 0x7fffffff) * 10 - 5;
  };
  for (let i = 0; i < 50; i++) {
    const m = next() + 1e-3 * Math.sign(next());
    const c = next();
    const x1 = next();
    const x2 = next() + 1;
    if (x1 === x2) continue;
    const s1: AffineSample = { x: x1, y: m * x1 + c };
    const s2: AffineSample = { x: x2, y: m * x2 + c };
    const target = next();
    const { xStar } = falsePosition(s1, s2, target);
    const recovered = m * xStar + c;
    assert(approxEq(recovered, target, 1e-9), `i=${i} recovered ${recovered} vs target ${target}`);
  }
});

run('T_aha_identity_target_y1', () => {
  const s1: AffineSample = { x: 3, y: 7 };
  const s2: AffineSample = { x: 5, y: 11 };
  const { xStar } = falsePosition(s1, s2, 7);
  assert(approxEq(xStar, 3), `xStar=${xStar} expected 3`);
});

run('T_aha_identity_target_y2', () => {
  const s1: AffineSample = { x: 3, y: 7 };
  const s2: AffineSample = { x: 5, y: 11 };
  const { xStar } = falsePosition(s1, s2, 11);
  assert(approxEq(xStar, 5), `xStar=${xStar} expected 5`);
});

run('T_aha_FAIL_degenerate_dx', () => {
  let threw = false;
  try {
    falsePosition({ x: 2, y: 5 }, { x: 2, y: 9 }, 7);
  } catch (e) {
    threw = e instanceof RangeError;
  }
  assert(threw, 'expected RangeError on dx=0');
});

run('T_aha_FAIL_degenerate_dy', () => {
  let threw = false;
  try {
    falsePosition({ x: 2, y: 5 }, { x: 7, y: 5 }, 9);
  } catch (e) {
    threw = e instanceof RangeError;
  }
  assert(threw, 'expected RangeError on dy=0');
});

run('T_aha_residual_zero', () => {
  const s1: AffineSample = { x: 1, y: 4 };
  const s2: AffineSample = { x: 2, y: 7 };
  const { xStar } = falsePosition(s1, s2, 10);
  const resid = falsePositionResidual(s1, s2, 10, xStar);
  assert(resid < 1e-12, `residual ${resid} should be ~0`);
});

run('T_aha_RMP_problem_24_analog', () => {
  // RMP Problem 24: "A heap and its 1/7 part become 19. What is the heap?"
  // Modern: x + x/7 = 19  →  x = 19 · 7/8 = 16.625
  // Affine form: f(x) = (8/7) · x, two samples at x=7 (→ 8) and x=14 (→ 16).
  const s1: AffineSample = { x: 7, y: 8 };
  const s2: AffineSample = { x: 14, y: 16 };
  const { xStar } = falsePosition(s1, s2, 19);
  assert(approxEq(xStar, 16.625), `xStar=${xStar} expected 16.625`);
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
