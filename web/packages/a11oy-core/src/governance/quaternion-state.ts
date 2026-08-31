/**
 * quaternion-state.ts — 64-bit packed unit-quaternion governance state token.
 *
 * Quaternion algebra: Hamilton (1843), "On a New Species of Imaginary
 *   Quantities Connected with a Theory of Quaternions," Proc. Royal Irish
 *   Academy 2:424–434.  JSTOR 20520177.
 * Unit-quaternion interpolation (SLERP): Shoemake (1985), "Animating
 *   rotation with quaternion curves," SIGGRAPH '85, ACM SIGGRAPH Computer
 *   Graphics 19(3):245–254.  DOI 10.1145/325334.325242.
 * Quaternion deep learning lineage:
 *   Zhu, Xu, Xu, Chen (2018), "Quaternion Convolutional Neural Networks,"
 *     ECCV 2018, LNCS 11212:631–647.  DOI 10.1007/978-3-030-01237-3_39.
 *   Parcollet et al. (2018), "Quaternion Convolutional Neural Networks for
 *     End-to-End Automatic Speech Recognition," Interspeech 2018, pp. 22–26.
 *     arXiv:1806.07789.  (Note: brief named ICASSP 2019; canonical venue is
 *     Interspeech 2018.)
 *   Comminiello, Lella, Scardapane, Uncini (2019), "Quaternion Convolutional
 *     Neural Networks for Detection and Localization of 3D Sound Events,"
 *     ICASSP 2019, pp. 8533–8537.  arXiv:1812.06811.
 *
 * SZL application: each governance receipt carries a unit quaternion
 * representing the rotation in 4D state-axis space from the doctrinal
 * identity (1, 0, 0, 0).  Composition of receipts corresponds to the
 * Hamilton product of their quaternions.  Token is byte-aligned (8 B)
 * for cache and register width on x86-64 / ARM64 / RV64 targets.
 *
 * Encoding: Q15 fixed-point (int16 / 32768) on each of (w, x, y, z).
 *   Round-to-nearest quantization error per component: |δᵢ| ≤ 2⁻¹⁶.
 *   Vector error magnitude: ||δ|| = √(Σ δᵢ²) ≤ √4·2⁻¹⁶ = 2⁻¹⁵.
 *   Worst-case deviation of ||q||² from 1 on a unit input:
 *     | ||q+δ||² − 1 | = | 2⟨q,δ⟩ + ||δ||² |
 *                     ≤ 2·||q||·||δ|| + ||δ||²
 *                     ≤ 2·1·2⁻¹⁵ + 2⁻³⁰ ≈ 6.10·10⁻⁵.
 *   Per-component bound: |δᵢ| ≤ 2⁻¹⁶ ≈ 1.53·10⁻⁵.
 *
 * Hamilton product (closed form on (w,x,y,z) ∈ ℝ⁴):
 *   (q₁ q₂).w = w₁w₂ − x₁x₂ − y₁y₂ − z₁z₂
 *   (q₁ q₂).x = w₁x₂ + x₁w₂ + y₁z₂ − z₁y₂
 *   (q₁ q₂).y = w₁y₂ − x₁z₂ + y₁w₂ + z₁x₂
 *   (q₁ q₂).z = w₁z₂ + x₁y₂ − y₁x₂ + z₁w₂
 * Norm-multiplicative: ||q₁q₂|| = ||q₁||·||q₂||  (real arithmetic; closed
 * under the Hamilton product on ℝ⁴ \ {0} — see Lutar.Quaternion.HamiltonAlgebra
 * theorem `hamilton_product_norm_multiplicative`).  Under Q15 the bound
 * above propagates per composition.
 */

export type QuaternionState = {
  readonly w: number;
  readonly x: number;
  readonly y: number;
  readonly z: number;
};

/** The doctrinal identity: zero rotation in 4D state-axis space. */
export const IDENTITY: QuaternionState = { w: 1, x: 0, y: 0, z: 0 };

/** Q15 scale: 1.0 maps to 2^15 = 32768 (clamped to 32767 = max int16). */
const Q15_SCALE = 32768;
const INT16_MAX = 32767;
const INT16_MIN = -32768;

function clampInt16(n: number): number {
  if (n >= INT16_MAX) return INT16_MAX;
  if (n <= INT16_MIN) return INT16_MIN;
  return n;
}

function toQ15(v: number): number {
  if (!Number.isFinite(v)) {
    throw new TypeError(`quaternion component not finite: ${v}`);
  }
  return clampInt16(Math.round(v * Q15_SCALE));
}

function fromQ15(i: number): number {
  return i / Q15_SCALE;
}

/**
 * Pack a quaternion into 8 bytes (big-endian, w-x-y-z).  Caller is
 * responsible for normalizing inputs to the unit sphere first; this
 * function will faithfully encode any quaternion whose components are
 * in [-1, 1 − 2⁻¹⁵], silently clamping the rare +1.0 case to the
 * maximum Q15 value.
 */
export function pack(q: QuaternionState): Uint8Array {
  const bytes = new Uint8Array(8);
  const view = new DataView(bytes.buffer);
  view.setInt16(0, toQ15(q.w), false);
  view.setInt16(2, toQ15(q.x), false);
  view.setInt16(4, toQ15(q.y), false);
  view.setInt16(6, toQ15(q.z), false);
  return bytes;
}

/** Unpack 8 bytes back to a quaternion in floating point. */
export function unpack(bytes: Uint8Array): QuaternionState {
  if (bytes.length !== 8) {
    throw new RangeError(`packed quaternion must be 8 bytes, got ${bytes.length}`);
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, 8);
  return {
    w: fromQ15(view.getInt16(0, false)),
    x: fromQ15(view.getInt16(2, false)),
    y: fromQ15(view.getInt16(4, false)),
    z: fromQ15(view.getInt16(6, false)),
  };
}

/** Euclidean norm ||q|| in ℝ⁴. */
export function norm(q: QuaternionState): number {
  return Math.sqrt(q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z);
}

/** Hamilton product q₁ q₂. */
export function multiply(q1: QuaternionState, q2: QuaternionState): QuaternionState {
  return {
    w: q1.w * q2.w - q1.x * q2.x - q1.y * q2.y - q1.z * q2.z,
    x: q1.w * q2.x + q1.x * q2.w + q1.y * q2.z - q1.z * q2.y,
    y: q1.w * q2.y - q1.x * q2.z + q1.y * q2.w + q1.z * q2.x,
    z: q1.w * q2.z + q1.x * q2.y - q1.y * q2.x + q1.z * q2.w,
  };
}

/** Quaternion conjugate q* = (w, −x, −y, −z). */
export function conjugate(q: QuaternionState): QuaternionState {
  return { w: q.w, x: -q.x, y: -q.y, z: -q.z };
}

/**
 * Rescale q to unit norm.  Throws on the zero quaternion (no well-defined
 * direction).  After this call, ||q|| = 1 to within floating-point ulp.
 */
export function normalize(q: QuaternionState): QuaternionState {
  const n = norm(q);
  if (n === 0) {
    throw new RangeError('cannot normalize the zero quaternion');
  }
  return { w: q.w / n, x: q.x / n, y: q.y / n, z: q.z / n };
}

/**
 * SLERP — Shoemake (1985), eq. (8). Spherical linear interpolation between
 * two unit quaternions at parameter t ∈ [0, 1].  When the inputs are very
 * close (1 − |dot| < SLERP_LINEAR_THRESHOLD) we fall back to normalized
 * linear interpolation to avoid division by sin(θ) ≈ 0; Shoemake recommends
 * this in §4 (Implementation).
 */
const SLERP_LINEAR_THRESHOLD = 1e-6;

export function slerp(
  q1: QuaternionState,
  q2: QuaternionState,
  t: number,
): QuaternionState {
  if (t < 0 || t > 1 || !Number.isFinite(t)) {
    throw new RangeError(`slerp parameter t must be in [0, 1], got ${t}`);
  }
  let dot = q1.w * q2.w + q1.x * q2.x + q1.y * q2.y + q1.z * q2.z;
  // Take the shorter great-circle arc by flipping q2 if dot < 0 (q and −q
  // represent the same rotation in SO(3); Shoemake (1985) §3).
  let q2w = q2.w, q2x = q2.x, q2y = q2.y, q2z = q2.z;
  if (dot < 0) {
    dot = -dot;
    q2w = -q2w; q2x = -q2x; q2y = -q2y; q2z = -q2z;
  }
  if (1 - dot < SLERP_LINEAR_THRESHOLD) {
    // Linear interpolation + renormalize (Shoemake §4).
    const w = q1.w + t * (q2w - q1.w);
    const x = q1.x + t * (q2x - q1.x);
    const y = q1.y + t * (q2y - q1.y);
    const z = q1.z + t * (q2z - q1.z);
    return normalize({ w, x, y, z });
  }
  const theta = Math.acos(dot);
  const sinTheta = Math.sin(theta);
  const a = Math.sin((1 - t) * theta) / sinTheta;
  const b = Math.sin(t * theta) / sinTheta;
  return {
    w: a * q1.w + b * q2w,
    x: a * q1.x + b * q2x,
    y: a * q1.y + b * q2y,
    z: a * q1.z + b * q2z,
  };
}

/**
 * Verify that ||q||² ≈ 1 to within Q15 tolerance.  The bound 7·10⁻⁵
 * has headroom over the proved worst-case 6.10·10⁻⁵ (≈ 2⁻¹⁴) from the
 * per-component round-to-nearest error analysis at the top of this file.
 * Useful for governance audits where
 * a quaternion has been packed/unpacked once and the auditor wants to
 * verify the token is still on (or near) the unit sphere.
 */
const Q15_NORM_TOLERANCE = 7e-5;

export function isApproximatelyUnit(q: QuaternionState): boolean {
  const n2 = q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z;
  return Math.abs(n2 - 1) <= Q15_NORM_TOLERANCE;
}
