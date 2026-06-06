/**
 * multi_source_sync.ts — Shor-replicated convergent ingest for Amaru.
 *
 * Maps the Shor [[9,1,3]] receipt code (Shor 1995, PRA 52:R2493) to
 * Amaru's multi-source data sync: up to 9 parallel sources can be
 * ingested for one logical delta; majority-decode survives single
 * source corruption.
 *
 * Citations:
 *   - Shor 1995 — 10.1103/PhysRevA.52.R2493
 *   - Hamming 1950 — 10.1002/j.1538-7305.1950.tb00463.x
 *
 * Innovation: Shor's construction was qubits; here we apply it to
 * append-only deltas from heterogeneous sources.  Receipt-level QEC.
 */

import {
  shorEncode,
  shorMajorityPayload,
  hammingDistByte,
  PhysicalReceipt,
} from './qec_lineage';

export interface SourceDelta {
  readonly sourceId: string;
  readonly payload: number; // single-byte digest of the delta (UInt8)
  readonly lineage: number;
}

/** Convergence: given up to 9 source deltas for the same logical record,
 *  return the majority-decoded payload. */
export function convergeSources(deltas: ReadonlyArray<SourceDelta>): number {
  if (deltas.length === 0) return 0;
  // Pad up to 9 by repeating the first delta (Shor [[9,1,3]] bundle).
  const padded: PhysicalReceipt[] = [];
  for (let i = 0; i < 9; i += 1) {
    const d = deltas[i % deltas.length];
    padded.push({ payload: d.payload, lineage: d.lineage });
  }
  return shorMajorityPayload(padded);
}

/** Detect corruption: returns the number of sources whose payload
 *  differs from the majority. */
export function detectCorruptedSources(deltas: ReadonlyArray<SourceDelta>): number {
  const majority = convergeSources(deltas);
  return deltas.filter((d) => d.payload !== majority).length;
}

/** Source-pair Hamming distance (bytes): for fingerprinting drift. */
export function sourcePairDistance(a: SourceDelta, b: SourceDelta): number {
  return hammingDistByte(a.payload, b.payload) + hammingDistByte(a.lineage, b.lineage);
}

export { shorEncode, shorMajorityPayload };
export type { PhysicalReceipt };
