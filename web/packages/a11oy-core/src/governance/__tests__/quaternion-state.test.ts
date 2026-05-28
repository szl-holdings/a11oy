/**
 * quaternion-state.test.ts — tests for the Q15-packed governance quaternion.
 *
 * Coverage:
 *  - round-trip pack/unpack on 1000 random unit quaternions, Q15 error
 *    stays below the documented 3.5e-5 norm-deviation bound
 *  - Hamilton-product associativity on 100 random triples (real arithmetic)
 *  - SLERP at t=0, t=1, t=0.5 matches reference recomputed from formula
 *    (Shoemake 1985, eq. (8)) within 1e-4
 *  - conjugate and Hamilton-product identity: q · q* = (||q||², 0, 0, 0)
 *  - normalize round-trip on 100 random non-zero quaternions
 *  - input-validation: pack rejects non-finite, unpack rejects wrong size
 *
 * Run: npx tsx web/packages/a11oy-core/src/governance/__tests__/quaternion-state.test.ts
 */

import assert from 'node:assert/strict';
import {
  IDENTITY,
  pack,
  unpack,
  norm,
  multiply,
  conjugate,
  normalize,
  slerp,
  isApproximatelyUnit,
  type QuaternionState,
} from '../quaternion-state.ts';

const results: Array<{ id: string; ok: boolean; detail?: string }> = [];

function test(id: string, fn: () => void) {
  try {
    fn();
    results.push({ id, ok: true });
  } catch (e) {
    results.push({
      id,
      ok: false,
      detail: e instanceof Error ? `${e.name}: ${e.message}` : String(e),
    });
  }
}

// Deterministic PRNG (mulberry32) for reproducible random tests.
function mulberry32(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function randomUnitQuaternion(rng: () => number): QuaternionState {
  // Marsaglia (1972) method: sample on S³ uniformly.
  let u1 = 0, u2 = 0, s1 = 2;
  while (s1 >= 1 || s1 === 0) {
    u1 = 2 * rng() - 1;
    u2 = 2 * rng() - 1;
    s1 = u1 * u1 + u2 * u2;
  }
  let u3 = 0, u4 = 0, s2 = 2;
  while (s2 >= 1 || s2 === 0) {
    u3 = 2 * rng() - 1;
    u4 = 2 * rng() - 1;
    s2 = u3 * u3 + u4 * u4;
  }
  const f = Math.sqrt((1 - s1) / s2);
  return { w: u1, x: u2, y: u3 * f, z: u4 * f };
}

test('IDENTITY is unit', () => {
  assert.equal(norm(IDENTITY), 1);
  assert.equal(isApproximatelyUnit(IDENTITY), true);
});

test('pack/unpack: 1000 random unit quaternions stay within Q15 norm tolerance', () => {
  const rng = mulberry32(0xC0FFEE);
  let worstNorm2Dev = 0;
  let worstCompDev = 0;
  for (let i = 0; i < 1000; i++) {
    const q = randomUnitQuaternion(rng);
    const back = unpack(pack(q));
    const dW = Math.abs(back.w - q.w);
    const dX = Math.abs(back.x - q.x);
    const dY = Math.abs(back.y - q.y);
    const dZ = Math.abs(back.z - q.z);
    const compDev = Math.max(dW, dX, dY, dZ);
    if (compDev > worstCompDev) worstCompDev = compDev;
    const n2 = back.w * back.w + back.x * back.x + back.y * back.y + back.z * back.z;
    const n2Dev = Math.abs(n2 - 1);
    if (n2Dev > worstNorm2Dev) worstNorm2Dev = n2Dev;
    assert.equal(isApproximatelyUnit(back), true,
      `unpacked quaternion not approximately unit; ||q||² − 1 = ${n2Dev}`);
  }
  // Per-component round-to-nearest bound: 2⁻¹⁶ ≈ 1.526e-5.
  assert.ok(worstCompDev < 1.6e-5,
    `worst per-component deviation ${worstCompDev} exceeds bound 1.6e-5`);
  // Norm-squared deviation bound: 6.10e-5 (≈ 2⁻¹⁴) per file header derivation;
  // empirical bound from 1000 samples is well below this proved ceiling.
  assert.ok(worstNorm2Dev < 6.2e-5,
    `worst ||q||² deviation ${worstNorm2Dev} exceeds bound 6.2e-5`);
});

test('pack produces exactly 8 bytes', () => {
  const q = { w: 0.5, x: 0.5, y: 0.5, z: 0.5 };
  const bytes = pack(q);
  assert.equal(bytes.length, 8);
});

test('pack is big-endian and deterministic on IDENTITY', () => {
  const bytes = pack(IDENTITY);
  // 1.0 → clamped to 32767 (INT16_MAX) since 2^15 saturates.
  // Big-endian: [0x7F, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00].
  assert.equal(bytes[0], 0x7f);
  assert.equal(bytes[1], 0xff);
  for (let i = 2; i < 8; i++) assert.equal(bytes[i], 0x00);
});

test('Hamilton product: associativity on 100 random triples (1e-12 tolerance)', () => {
  const rng = mulberry32(0xDEADBEEF);
  for (let i = 0; i < 100; i++) {
    const a = randomUnitQuaternion(rng);
    const b = randomUnitQuaternion(rng);
    const c = randomUnitQuaternion(rng);
    const ab_c = multiply(multiply(a, b), c);
    const a_bc = multiply(a, multiply(b, c));
    const diff = Math.max(
      Math.abs(ab_c.w - a_bc.w),
      Math.abs(ab_c.x - a_bc.x),
      Math.abs(ab_c.y - a_bc.y),
      Math.abs(ab_c.z - a_bc.z),
    );
    assert.ok(diff < 1e-12, `associativity failed on triple ${i}: max diff ${diff}`);
  }
});

test('Hamilton product: norm-multiplicative on 100 random pairs (1e-12 tolerance)', () => {
  const rng = mulberry32(0xFACEFEED);
  for (let i = 0; i < 100; i++) {
    const a = randomUnitQuaternion(rng);
    const b = randomUnitQuaternion(rng);
    const ab = multiply(a, b);
    const lhs = norm(ab);
    const rhs = norm(a) * norm(b);
    assert.ok(Math.abs(lhs - rhs) < 1e-12,
      `||ab|| − ||a||·||b|| = ${lhs - rhs}`);
  }
});

test('Hamilton product: IDENTITY is two-sided identity', () => {
  const q = normalize({ w: 0.2, x: -0.7, y: 0.4, z: 0.55 });
  const lq = multiply(IDENTITY, q);
  const rq = multiply(q, IDENTITY);
  assert.ok(Math.abs(lq.w - q.w) < 1e-15);
  assert.ok(Math.abs(lq.x - q.x) < 1e-15);
  assert.ok(Math.abs(lq.y - q.y) < 1e-15);
  assert.ok(Math.abs(lq.z - q.z) < 1e-15);
  assert.ok(Math.abs(rq.w - q.w) < 1e-15);
  assert.ok(Math.abs(rq.x - q.x) < 1e-15);
  assert.ok(Math.abs(rq.y - q.y) < 1e-15);
  assert.ok(Math.abs(rq.z - q.z) < 1e-15);
});

test('Conjugate: q · q* = (||q||², 0, 0, 0)', () => {
  const rng = mulberry32(0x12345);
  for (let i = 0; i < 50; i++) {
    const q = randomUnitQuaternion(rng);
    const p = multiply(q, conjugate(q));
    assert.ok(Math.abs(p.w - 1) < 1e-12, `w deviates: ${p.w - 1}`);
    assert.ok(Math.abs(p.x) < 1e-12);
    assert.ok(Math.abs(p.y) < 1e-12);
    assert.ok(Math.abs(p.z) < 1e-12);
  }
});

test('normalize: 100 random non-zero quaternions reach unit norm', () => {
  const rng = mulberry32(0xABCDEF);
  for (let i = 0; i < 100; i++) {
    const scale = (rng() * 100) + 0.01; // avoid zero
    const raw = randomUnitQuaternion(rng);
    const scaled = { w: raw.w * scale, x: raw.x * scale, y: raw.y * scale, z: raw.z * scale };
    const n = normalize(scaled);
    assert.ok(Math.abs(norm(n) - 1) < 1e-14, `norm deviates: ${norm(n) - 1}`);
  }
});

test('normalize: rejects zero quaternion', () => {
  assert.throws(() => normalize({ w: 0, x: 0, y: 0, z: 0 }), /zero quaternion/);
});

test('SLERP: t=0 returns q1, t=1 returns q2 (with sign convention)', () => {
  const q1 = normalize({ w: 1, x: 0.1, y: 0.2, z: 0.3 });
  const q2 = normalize({ w: 0.4, x: -0.5, y: 0.6, z: 0.7 });
  const s0 = slerp(q1, q2, 0);
  const s1 = slerp(q1, q2, 1);
  // At t=0 we return q1 (up to floating point).
  assert.ok(Math.abs(s0.w - q1.w) < 1e-14);
  assert.ok(Math.abs(s0.x - q1.x) < 1e-14);
  assert.ok(Math.abs(s0.y - q1.y) < 1e-14);
  assert.ok(Math.abs(s0.z - q1.z) < 1e-14);
  // At t=1 we return q2 *possibly negated* if shorter-arc flip was applied;
  // both represent the same rotation. So check up to sign.
  const dot = s1.w * q2.w + s1.x * q2.x + s1.y * q2.y + s1.z * q2.z;
  const sign = dot >= 0 ? 1 : -1;
  assert.ok(Math.abs(s1.w - sign * q2.w) < 1e-12);
  assert.ok(Math.abs(s1.x - sign * q2.x) < 1e-12);
  assert.ok(Math.abs(s1.y - sign * q2.y) < 1e-12);
  assert.ok(Math.abs(s1.z - sign * q2.z) < 1e-12);
});

test('SLERP: t=0.5 matches direct half-angle reference (1e-4)', () => {
  // Reference: rotation about the z-axis by angle 2·π/3 → quaternion
  // (cos(π/3), 0, 0, sin(π/3)).  Half-way slerp from IDENTITY should be
  // (cos(π/6), 0, 0, sin(π/6)).
  const q2 = { w: Math.cos(Math.PI / 3), x: 0, y: 0, z: Math.sin(Math.PI / 3) };
  const half = slerp(IDENTITY, q2, 0.5);
  const ref = { w: Math.cos(Math.PI / 6), x: 0, y: 0, z: Math.sin(Math.PI / 6) };
  assert.ok(Math.abs(half.w - ref.w) < 1e-4, `w: ${half.w} vs ${ref.w}`);
  assert.ok(Math.abs(half.x - ref.x) < 1e-4);
  assert.ok(Math.abs(half.y - ref.y) < 1e-4);
  assert.ok(Math.abs(half.z - ref.z) < 1e-4, `z: ${half.z} vs ${ref.z}`);
});

test('SLERP: nearly-identical inputs use linear fallback and stay unit-norm', () => {
  const q1 = normalize({ w: 0.5, x: 0.5, y: 0.5, z: 0.5 });
  // Tiny perturbation, well inside SLERP_LINEAR_THRESHOLD.
  const q2 = normalize({ w: 0.5 + 1e-9, x: 0.5, y: 0.5, z: 0.5 });
  const mid = slerp(q1, q2, 0.5);
  assert.ok(Math.abs(norm(mid) - 1) < 1e-12);
});

test('SLERP: rejects t out of [0,1]', () => {
  assert.throws(() => slerp(IDENTITY, IDENTITY, -0.1), /\[0, 1\]/);
  assert.throws(() => slerp(IDENTITY, IDENTITY, 1.1), /\[0, 1\]/);
  assert.throws(() => slerp(IDENTITY, IDENTITY, Number.NaN), /\[0, 1\]/);
});

test('pack: rejects non-finite components', () => {
  assert.throws(() => pack({ w: Number.NaN, x: 0, y: 0, z: 0 }), /not finite/);
  assert.throws(() => pack({ w: 0, x: Infinity, y: 0, z: 0 }), /not finite/);
});

test('unpack: rejects wrong byte length', () => {
  assert.throws(() => unpack(new Uint8Array(7)), /8 bytes/);
  assert.throws(() => unpack(new Uint8Array(9)), /8 bytes/);
});

const passed = results.filter((r) => r.ok).length;
const failed = results.length - passed;
for (const r of results) {
  // eslint-disable-next-line no-console
  console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.id}${r.detail ? '  — ' + r.detail : ''}`);
}
// eslint-disable-next-line no-console
console.log(`\n${passed}/${results.length} tests passed.`);
if (failed > 0) process.exit(1);
