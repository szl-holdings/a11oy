/**
 * @szl-holdings/a11oy-qec-integrity
 *
 * QEC-derived receipt integrity primitives for the a11oy governance fabric.
 *
 * v17 grafts (see Lutar/QEC/ in szl-holdings/lutar-lean):
 *   • Hamming distance / weight over byte-arrays (Hamming 1950).
 *   • Shor [[9,1,3]] 9-fold receipt replication (Shor 1995).
 *   • CSS classical-to-stabilizer bridge (Calderbank-Shor-Steane 1996).
 *   • Kitaev surface-code vertex parity (Kitaev 1997 / 2003).
 *
 * Doctrine v6 clean.
 */

export {
  hammingDist,
  hammingWeight,
  hammingDistByte,
  minDistance,
  shorEncode,
  shorMajorityPayload,
  classicalToCSS,
  cssConsistent,
  vertexParity,
  singleSiteError,
  allErrors,
  noErrors,
} from './qec_lineage';

export type {
  PhysicalReceipt,
  StabilizerPair,
  Site,
  VertexCheck,
} from './qec_lineage';

/**
 * Helper specific to a11oy: compute receipt-integrity Hamming weight for
 * detection of doctrine corruption.  Returns the number of differing
 * bytes between a candidate receipt and the canonical one, byte-by-byte.
 */
export function receiptHammingWeight(
  candidate: Uint8Array,
  canonical: Uint8Array,
): number {
  if (candidate.length !== canonical.length) {
    throw new Error('receiptHammingWeight: length mismatch');
  }
  let w = 0;
  for (let i = 0; i < candidate.length; i += 1) {
    if (candidate[i] !== canonical[i]) w += 1;
  }
  return w;
}
