/**
 * posture_drift_lattice.ts — Kitaev surface code for posture drift
 * detection in Sentra.
 *
 * Map (Kitaev 2003, DOI 10.1016/S0003-4916(02)00018-0):
 *   • Surface qubits → assets × time-slices (lattice sites).
 *   • Stabilizer parity checks → local drift-syndrome detectors.
 *   • Endpoint detection → multi-asset correlated-incident detection.
 *
 * Innovation: Kitaev's anyons become "drift events" at lattice
 * endpoints.  This is novel as a security-posture primitive.
 */

import {
  Site,
  VertexCheck,
  vertexParity,
  singleSiteError,
  noErrors,
} from './qec_lineage';

export interface AssetTimeKey {
  readonly asset: string;
  readonly slice: number;
}

/** Convert an asset/time key to a Site.  Hashes the asset string to a
 *  small integer; same string always maps to same integer. */
export function assetToSite(key: AssetTimeKey): Site {
  let h = 0;
  for (const c of key.asset) h = ((h * 31) + c.charCodeAt(0)) | 0;
  return { agent: h, slice: key.slice };
}

/** Check the local drift parity around a "vertex" of 4 adjacent
 *  (asset × slice) sites. Returns true if a drift syndrome is detected.
 *
 *  LIMITATION (weight-4 blind spot): this is a single vertex stabilizer
 *  (XOR parity over 4 sites). Like the underlying Kitaev surface code, it
 *  detects odd-weight drift (1 or 3 of the 4 sites drifted) but is BLIND to
 *  even-weight drift — if all 4 sites (or exactly 2) drift together, the
 *  parity cancels and this check returns false. A correlated incident that
 *  simultaneously moves a full vertex of assets will NOT raise a local
 *  syndrome here; detection of such events requires overlapping vertex/
 *  plaquette checks across the lattice (full surface-code decoding), which
 *  this single-vertex primitive does not perform. Covered by the
 *  "all 4 assets drifted -> parity cancels" case in the test suite. */
export function detectLocalDrift(
  northKey: AssetTimeKey,
  southKey: AssetTimeKey,
  eastKey: AssetTimeKey,
  westKey: AssetTimeKey,
  driftedAssets: ReadonlySet<string>,
): boolean {
  const v: VertexCheck = {
    n: assetToSite(northKey),
    s: assetToSite(southKey),
    e: assetToSite(eastKey),
    w: assetToSite(westKey),
  };

  const errs = (site: Site): boolean => {
    // Reverse-lookup: does any drifted asset hash to this agent slot?
    for (const a of driftedAssets) {
      let h = 0;
      for (const c of a) h = ((h * 31) + c.charCodeAt(0)) | 0;
      if (h === site.agent) return true;
    }
    return false;
  };

  return vertexParity(errs, v);
}

export { vertexParity, singleSiteError, noErrors };
export type { Site, VertexCheck };
