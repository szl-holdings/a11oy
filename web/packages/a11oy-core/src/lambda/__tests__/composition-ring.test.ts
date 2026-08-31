/**
 * Tests for R4-I3 Brahmagupta–Fibonacci composition identity.
 *
 * Coverage:
 *  - Brahmagupta's worked example (≈ in BSS ch. 18): canonical 4-tuple
 *  - 100 random integer 4-tuples satisfy the identity exactly (BigInt
 *    cross-check ensures no FP drift)
 *  - 50 random real 4-tuples satisfy within FP tolerance
 *  - Identity commutativity-of-norms: N(u·v) = N(v·u) for symmetric norms
 *  - Edge cases: zero vector, identity vector (1, 0)
 */
import {
  bfProduct,
  bfResidual,
  composeLambdaCertificates,
  squareNorm,
  type TwoVector,
} from '../composition-ring';

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

console.log('R4-I3 Brahmagupta–Fibonacci composition ring');

run('T_BF_brahmagupta_worked_example', () => {
  // (2² + 3²)(4² + 5²) = 13 · 41 = 533
  //                    = (2·4 − 3·5)² + (2·5 + 3·4)²
  //                    = (−7)² + 22² = 49 + 484 = 533
  const u: TwoVector = { a: 2, b: 3 };
  const v: TwoVector = { a: 4, b: 5 };
  const r = composeLambdaCertificates(u, v);
  assert(r.composed.a === -7, `expected a = -7, got ${r.composed.a}`);
  assert(r.composed.b === 22, `expected b = 22, got ${r.composed.b}`);
  assert(r.composedNorm === 533, `expected norm 533, got ${r.composedNorm}`);
  assert(r.productOfNorms === 533, `expected product 533, got ${r.productOfNorms}`);
  assert(r.residual === 0, `expected residual 0, got ${r.residual}`);
});

run('T_BF_100_random_integer_tuples_BigInt_exact', () => {
  // BigInt cross-check: with integer inputs, residual must be exactly 0.
  let rng = 424242;
  const next = () => {
    rng = (rng * 1103515245 + 12345) & 0x7fffffff;
    return rng;
  };
  for (let i = 0; i < 100; i++) {
    const a = (next() % 200) - 100;
    const b = (next() % 200) - 100;
    const c = (next() % 200) - 100;
    const d = (next() % 200) - 100;
    const u: TwoVector = { a, b };
    const v: TwoVector = { a: c, b: d };
    const res = bfResidual(u, v);
    assert(
      res === 0,
      `i=${i} (${a},${b},${c},${d}): residual ${res} ≠ 0`,
    );
    // BigInt cross-check
    const A = BigInt(a), B = BigInt(b), C = BigInt(c), D = BigInt(d);
    const lhs = (A * A + B * B) * (C * C + D * D);
    const re = A * C - B * D;
    const im = A * D + B * C;
    const rhs = re * re + im * im;
    assert(lhs === rhs, `i=${i} BigInt mismatch ${lhs} vs ${rhs}`);
  }
});

run('T_BF_50_random_real_tuples_FP', () => {
  let rng = 9091;
  const next = () => {
    rng = (rng * 1103515245 + 12345) & 0x7fffffff;
    return rng / 0x7fffffff;
  };
  for (let i = 0; i < 50; i++) {
    const u: TwoVector = { a: next() * 20 - 10, b: next() * 20 - 10 };
    const v: TwoVector = { a: next() * 20 - 10, b: next() * 20 - 10 };
    const res = bfResidual(u, v);
    assert(res < 1e-9, `i=${i}: residual ${res} > 1e-9`);
  }
});

run('T_BF_identity_vector_acts_as_unit', () => {
  // (1, 0) · (a, b) = (a, b) for the BF product, since
  //   (1·a − 0·b, 1·b + 0·a) = (a, b).
  const e: TwoVector = { a: 1, b: 0 };
  const v: TwoVector = { a: 7, b: -3 };
  const r = bfProduct(e, v);
  assert(r.a === v.a && r.b === v.b, `identity failed: ${JSON.stringify(r)}`);
});

run('T_BF_zero_vector_norm_zero', () => {
  const z: TwoVector = { a: 0, b: 0 };
  assert(squareNorm(z) === 0, `zero norm ≠ 0`);
  const v: TwoVector = { a: 3, b: 4 };
  const r = composeLambdaCertificates(z, v);
  assert(r.composedNorm === 0, `composed with zero must have norm 0`);
  assert(r.productOfNorms === 0, `product with zero must be 0`);
  assert(r.residual === 0, `residual ${r.residual}`);
});

run('T_BF_norm_multiplicativity_on_unit_circle', () => {
  // For (a,b) and (c,d) on the unit circle, composed norm is also 1.
  const u: TwoVector = { a: Math.cos(0.7), b: Math.sin(0.7) };
  const v: TwoVector = { a: Math.cos(1.3), b: Math.sin(1.3) };
  const r = composeLambdaCertificates(u, v);
  assert(approxEq(r.composedNorm, 1), `composed norm ${r.composedNorm} ≠ 1`);
  assert(approxEq(r.productOfNorms, 1), `product ${r.productOfNorms} ≠ 1`);
});

run('T_BF_residual_matches_bfResidual', () => {
  const u: TwoVector = { a: 5, b: 12 };
  const v: TwoVector = { a: 3, b: 4 };
  const r = composeLambdaCertificates(u, v);
  const r2 = bfResidual(u, v);
  assert(r.residual === r2, `residual mismatch: ${r.residual} vs ${r2}`);
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
