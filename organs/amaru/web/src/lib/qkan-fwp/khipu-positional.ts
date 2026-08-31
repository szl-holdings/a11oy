/**
 * khipu-positional.ts — Khipu positional encoding for the QKAN-FWP
 * sequence memory (v15 §10.2 graft).
 *
 * Extends the QKAN-FWP receipt with an organ-aware positional encoding
 * keyed by the khipu pendant-cord index `(organId, decisionIndex)`. The
 * encoding is integer-canonical so that two sequence-memory states with
 * the same organ skeleton produce identical positional vectors, which is
 * the prerequisite for the audit-Reidemeister R2 (commutativity) lemma
 * downstream.
 *
 * Sources:
 *   - Urton 2003, "Signs of the Inka Khipu" (UT Press), pp. 41–62 — pendant
 *     hierarchy semantics.
 *   - Ascher & Ascher 1981, "Code of the Quipu" (U. Michigan Press) —
 *     summation-cord invariant.
 *   - Vaswani et al. 2017, "Attention Is All You Need", NeurIPS — sinusoidal
 *     positional encoding pattern this module specialises to a hierarchical
 *     (organ, decision) skeleton.
 *   - Bar-Natan 1995, *Topology* 34:423–472 — chord-diagram skeleton ↔
 *     positional index lineage.
 *
 * Lean obligation: TH11 `khipuReceipt_checksum_invariant` in
 * `lutar-lean/Lutar/Khipu/SummationInvariant.lean` covers the sum-of-sums
 * invariant. The positional encoding here is a downstream consumer.
 */

import type { FastWeightMatrix } from './qkan-fwp.ts';
import { fastWeightQuery } from './qkan-fwp.ts';

/** A khipu pendant-cord position: an organ identifier plus the
 * 0-based index of the decision within that organ. */
export interface KhipuPosition {
  readonly organId: string;
  readonly decisionIndex: number; // ≥ 0
}

/**
 * Deterministic 32-bit integer hash for a string (FNV-1a). Used to fold
 * the textual organId into a numeric organ slot for the positional
 * encoding without depending on `node:crypto` (so this module runs in
 * browser bundles).
 */
function fnv1a32(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  // Force unsigned 32-bit.
  return h >>> 0;
}

/**
 * Compute a khipu positional encoding vector of dimension `d` for the
 * given `(organId, decisionIndex)`. The encoding is a sinusoidal pattern
 * (Vaswani 2017) over the *combined* hierarchical index
 * `pos = organSlot · MAX_DECISIONS_PER_ORGAN + decisionIndex`,
 * so two positions in different organs are orthogonal almost everywhere
 * and two adjacent decisions in the same organ are smoothly close.
 *
 * `MAX_DECISIONS_PER_ORGAN` is fixed at 1024 to keep the combined index
 * stable across runs. Callers that need more should set it explicitly.
 */
export function khipuPositionalEncoding(
  pos: KhipuPosition,
  d: number,
  maxDecisionsPerOrgan: number = 1024,
): Float64Array {
  if (!Number.isInteger(d) || d < 2 || d % 2 !== 0) {
    throw new Error(`khipu PE dimension must be even integer ≥ 2, got ${d}`);
  }
  if (!Number.isInteger(pos.decisionIndex) || pos.decisionIndex < 0) {
    throw new Error(
      `decisionIndex must be non-negative integer, got ${pos.decisionIndex}`,
    );
  }
  if (pos.decisionIndex >= maxDecisionsPerOrgan) {
    throw new Error(
      `decisionIndex ${pos.decisionIndex} ≥ maxDecisionsPerOrgan ${maxDecisionsPerOrgan}`,
    );
  }
  const organSlot = fnv1a32(pos.organId) % 0xffff;
  const combined = organSlot * maxDecisionsPerOrgan + pos.decisionIndex;
  const v = new Float64Array(d);
  for (let i = 0; i < d / 2; i++) {
    const denom = Math.pow(10000, (2 * i) / d);
    v[2 * i] = Math.sin(combined / denom);
    v[2 * i + 1] = Math.cos(combined / denom);
  }
  return v;
}

/**
 * Combine a fast-weight query with a khipu positional encoding by
 * element-wise addition (the standard Transformer composition). Returns
 * a new Float64Array; inputs are not mutated.
 */
export function khipuPositionalQuery(
  W: FastWeightMatrix,
  key: Float64Array,
  pos: KhipuPosition,
): Float64Array {
  const queried = fastWeightQuery(W, key);
  const pe = khipuPositionalEncoding(pos, queried.length);
  const out = new Float64Array(queried.length);
  for (let i = 0; i < queried.length; i++) out[i] = queried[i]! + pe[i]!;
  return out;
}

/**
 * Skeleton-equivalence check: two sequence-memory states are
 * audit-Reidemeister R2 equivalent iff they have the same sorted multiset
 * of `(organSlot, decisionCount)` pairs. This is the runtime witness for
 * the conjectured R2 invariance of the v15 knot calculus (see
 * `lutar-lean/Lutar/Knot/ReidemeisterConjecture.lean`).
 */
export function khipuSkeletonTag(
  positions: ReadonlyArray<KhipuPosition>,
): string {
  const perOrgan = new Map<number, number>();
  for (const p of positions) {
    const slot = fnv1a32(p.organId);
    perOrgan.set(slot, (perOrgan.get(slot) ?? 0) + 1);
  }
  const skel = [...perOrgan.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([slot, count]) => `${slot}:${count}`)
    .join(';');
  return `skel|${skel}`;
}
