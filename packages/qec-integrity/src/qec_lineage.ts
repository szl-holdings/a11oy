/**
 * qec_lineage.ts — runtime counterpart of Lutar/QEC/*.lean modules
 *
 * Provides:
 *   • Hamming distance & weight on byte arrays (Hamming 1950).
 *   • Shor [[9,1,3]] 9-fold receipt replication with majority decode
 *     (Shor 1995).
 *   • CSS classical→stabilizer bridge (Calderbank–Shor–Steane 1996).
 *   • Kitaev surface-code vertex parity check (Kitaev 1997/2003).
 *
 * Mirror invariants of the Lean modules; the test suite asserts each.
 *
 * Citations (DOIs):
 *   • Hamming 1950 — 10.1002/j.1538-7305.1950.tb00463.x
 *   • Shor 1995 — 10.1103/PhysRevA.52.R2493
 *   • Steane 1996 — 10.1098/rspa.1996.0136
 *   • Calderbank-Shor 1996 — 10.1103/PhysRevA.54.1098
 *   • Kitaev 2003 — 10.1016/S0003-4916(02)00018-0
 *   • Cover & Thomas 2006 — ISBN 978-0-471-24195-9
 *
 * Innovation beyond attribution: the receipt-level instantiation of
 * each construction is new (no quantum-AI prior art in 1950-2003).
 */

// ──────────────────────────────────────────────────────────────────────
// Hamming foundations (1950)
// ──────────────────────────────────────────────────────────────────────

/** Hamming distance between two equal-length bit arrays. */
export function hammingDist(a: readonly boolean[], b: readonly boolean[]): number {
  if (a.length !== b.length) {
    throw new Error(`hammingDist: length mismatch ${a.length} vs ${b.length}`);
  }
  let d = 0;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) d += 1;
  }
  return d;
}

/** Hamming weight = distance from the all-zero vector. */
export function hammingWeight(a: readonly boolean[]): number {
  let w = 0;
  for (const bit of a) if (bit) w += 1;
  return w;
}

/** Hamming distance for UInt8 bytes (XOR popcount). */
export function hammingDistByte(a: number, b: number): number {
  let x = (a ^ b) & 0xff;
  let count = 0;
  while (x) {
    count += x & 1;
    x >>>= 1;
  }
  return count;
}

/** Minimum distance of a set of equal-length bit arrays (codewords). */
export function minDistance(codewords: ReadonlyArray<readonly boolean[]>): number {
  if (codewords.length < 2) return 0;
  let m = Infinity;
  for (let i = 0; i < codewords.length; i += 1) {
    for (let j = i + 1; j < codewords.length; j += 1) {
      const d = hammingDist(codewords[i], codewords[j]);
      if (d < m) m = d;
    }
  }
  return m === Infinity ? 0 : m;
}

// ──────────────────────────────────────────────────────────────────────
// Shor [[9,1,3]] receipt code (1995)
// ──────────────────────────────────────────────────────────────────────

export interface PhysicalReceipt {
  readonly payload: number; // UInt8
  readonly lineage: number; // UInt8
}

/** Encode a logical receipt as a 9-fold replicated bundle. */
export function shorEncode(logical: PhysicalReceipt): PhysicalReceipt[] {
  return Array.from({ length: 9 }, () => ({ ...logical }));
}

/** Majority decode the bundle by selecting the most common payload byte. */
export function shorMajorityPayload(bundle: ReadonlyArray<PhysicalReceipt>): number {
  if (bundle.length === 0) return 0;
  const counts = new Map<number, number>();
  for (const r of bundle) {
    counts.set(r.payload, (counts.get(r.payload) || 0) + 1);
  }
  let best = bundle[0].payload;
  let bestCount = 0;
  for (const [p, c] of counts) {
    if (c > bestCount) {
      bestCount = c;
      best = p;
    }
  }
  return best;
}

// ──────────────────────────────────────────────────────────────────────
// CSS classical → stabilizer bridge (1996)
// ──────────────────────────────────────────────────────────────────────

export interface StabilizerPair {
  readonly xParity: number; // UInt8
  readonly zParity: number; // UInt8
}

/** Classical 8-bit codeword to (X-parity, Z-parity) stabilizer pair. */
export function classicalToCSS(codeword: number): StabilizerPair {
  return { xParity: codeword & 0xff, zParity: (codeword ^ 0xff) & 0xff };
}

/** A CSS pair is consistent when X ⊕ Z = 0xFF. */
export function cssConsistent(pair: StabilizerPair): boolean {
  return (pair.xParity ^ pair.zParity) === 0xff;
}

// ──────────────────────────────────────────────────────────────────────
// Kitaev surface-code vertex check (1997/2003)
// ──────────────────────────────────────────────────────────────────────

export interface Site {
  readonly agent: number;
  readonly slice: number;
}

/** Equality on Site. */
function siteEq(a: Site, b: Site): boolean {
  return a.agent === b.agent && a.slice === b.slice;
}

export interface VertexCheck {
  readonly n: Site;
  readonly s: Site;
  readonly e: Site;
  readonly w: Site;
}

/** Vertex parity: XOR of the 4 incident error bits.  Errors are mapped
 *  from a `Site → boolean` function. */
export function vertexParity(
  errs: (s: Site) => boolean,
  v: VertexCheck,
): boolean {
  return errs(v.n) !== errs(v.s) !== errs(v.e) !== errs(v.w);
}

/** Helper: an error map that flags exactly one site as corrupted. */
export function singleSiteError(target: Site): (s: Site) => boolean {
  return (s: Site) => siteEq(s, target);
}

/** Helper: an error map that flags every site. */
export function allErrors(): (s: Site) => boolean {
  return () => true;
}

/** Helper: an error map that flags no site. */
export function noErrors(): (s: Site) => boolean {
  return () => false;
}
