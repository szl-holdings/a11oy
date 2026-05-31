/**
 * kitaev_surface.ts
 *
 * Runtime instillation of Lean theorem:
 *   Lutar.QEC.Kitaev (KitaevSurface module)
 *   File: Lutar/QEC/KitaevSurface.lean
 *   Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * Lean theorems formalised here:
 *   - `kitaev_single_site_flips_parity_n` (line ~72): a single site error
 *      at the north vertex flips parity to true.
 *   - `kitaev_no_errors_zero_parity` (line ~79): no errors → zero parity.
 *   - `kitaev_all_errors_zero_parity` (line ~84): all errors → zero parity
 *      (weight-4 undetectable error, distance-1 limit).
 *
 * Runtime contract:
 *   Given a VertexCheck (4 adjacent lattice sites) and an error map
 *   (site → bool), compute vertex parity and detect syndromes.
 *   Agents-as-rows, time-slices-as-columns model for receipt lattice.
 *
 * Citations (from Lean file):
 *   - Kitaev (2003) DOI 10.1016/S0003-4916(02)00018-0
 *   - Bravyi & Kitaev (1998) arXiv:quant-ph/9811052
 *
 * Doctrine v7: No new axioms. No sorries. STAGED label: FULLY WIRED.
 */

import { createHash } from "crypto";

// ---------------------------------------------------------------------------
// Domain types — mirrors Lean types
// ---------------------------------------------------------------------------

/** Mirrors Lean `Site`. A lattice site is (agent, slice). */
export interface Site {
  agent: number; // AgentId
  slice: number; // SliceIdx
}

/** Mirrors Lean `VertexCheck`. Models a vertex parity check over 4 sites. */
export interface VertexCheck {
  n: Site; // north
  s: Site; // south
  e: Site; // east
  w: Site; // west
}

/** Mirrors Lean `ErrorBit`. false = clean, true = corrupted. */
export type ErrorBit = boolean;

/** Error map: site key → ErrorBit. Key is `"${agent}:${slice}"`. */
export type ErrorMap = Map<string, ErrorBit>;

/** DSSE-shaped receipt. */
export interface DSSEReceipt {
  theorem: string;
  lean_commit_sha: string;
  inputs_hash: string;
  output: boolean;
  ts: string;
  sig: string;
}

export type Signer = (payload: string) => string;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LEAN_THEOREM = "Lutar.QEC.Kitaev.kitaev_single_site_flips_parity_n";
const LEAN_FILE_LINE = "Lutar/QEC/KitaevSurface.lean:72";
const LEAN_COMMIT_SHA = "c4d13795689601324fce0236351bfe0ade990a43";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Serialize a Site to a string key for the ErrorMap. */
export function siteKey(s: Site): string {
  return `${s.agent}:${s.slice}`;
}

/** Look up the ErrorBit for a site. Absent sites are clean (false). */
function siteError(errors: ErrorMap, s: Site): ErrorBit {
  return errors.get(siteKey(s)) ?? false;
}

// ---------------------------------------------------------------------------
// Core functions — mirror Lean definitions
// ---------------------------------------------------------------------------

/**
 * Computes vertex parity: XOR of the 4 incident error bits.
 * Odd parity (true) flags a syndrome.
 *
 * Mirrors Lean:
 *   `def vertexParity (errs : Site → ErrorBit) (v : VertexCheck) : Bool :=
 *      errs v.n != errs v.s != errs v.e != errs v.w`
 *
 * Lean theorem `kitaev_single_site_flips_parity_n` proves that a single
 * north-site error produces parity = true.
 *
 * @param errors - ErrorMap (site → bool).
 * @param v      - VertexCheck specifying the 4 adjacent sites.
 * @returns true iff the vertex has an odd-parity syndrome.
 */
export function vertexParity(errors: ErrorMap, v: VertexCheck): boolean {
  const en = siteError(errors, v.n);
  const es = siteError(errors, v.s);
  const ee = siteError(errors, v.e);
  const ew = siteError(errors, v.w);
  // XOR chain matches Lean's `!=` (Bool XOR)
  return en !== es !== ee !== ew;
}

/**
 * Scans all vertices in a lattice for syndromes.
 *
 * @param vertices - Array of VertexChecks.
 * @param errors   - ErrorMap.
 * @returns Array of syndrome vertices (those with parity = true).
 */
export function detectSyndromes(
  vertices: VertexCheck[],
  errors: ErrorMap
): VertexCheck[] {
  return vertices.filter((v) => vertexParity(errors, v));
}

/**
 * Constructs an error map from a single corrupted site.
 * Utility for testing/simulation.
 *
 * @param corruptedSite - The one site to mark as corrupted.
 * @returns ErrorMap with exactly one true entry.
 */
export function singleSiteError(corruptedSite: Site): ErrorMap {
  const m = new Map<string, ErrorBit>();
  m.set(siteKey(corruptedSite), true);
  return m;
}

// ---------------------------------------------------------------------------
// Inputs hash helper
// ---------------------------------------------------------------------------

function hashInputs(v: VertexCheck, errorSites: Site[]): string {
  const payload = JSON.stringify({ v, errorSites });
  return createHash("sha256").update(payload).digest("hex");
}

// ---------------------------------------------------------------------------
// DSSE receipt emitter
// ---------------------------------------------------------------------------

/**
 * Evaluates vertex parity for a given VertexCheck + error list and emits a
 * DSSE receipt.
 *
 * Lean theorem: `Lutar.QEC.Kitaev.kitaev_single_site_flips_parity_n`
 * File: Lutar/QEC/KitaevSurface.lean:72
 * Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * The `output` field is `true` iff the vertex has a syndrome (odd parity).
 *
 * @param v          - VertexCheck to evaluate.
 * @param errorSites - List of corrupted sites.
 * @param signer     - Signing function.
 * @returns DSSEReceipt.
 */
export function emitKitaevSurfaceReceipt(
  v: VertexCheck,
  errorSites: Site[],
  signer: Signer
): { parity: boolean; receipt: DSSEReceipt } {
  const errors: ErrorMap = new Map();
  for (const site of errorSites) {
    errors.set(siteKey(site), true);
  }

  const output = vertexParity(errors, v);
  const inputs_hash = hashInputs(v, errorSites);
  const ts = new Date().toISOString();

  const sigPayload = JSON.stringify({
    theorem: LEAN_THEOREM,
    lean_commit_sha: LEAN_COMMIT_SHA,
    inputs_hash,
    output,
    ts,
  });

  const receipt: DSSEReceipt = {
    theorem: LEAN_THEOREM,
    lean_commit_sha: LEAN_COMMIT_SHA,
    inputs_hash,
    output,
    ts,
    sig: signer(sigPayload),
  };

  return { parity: output, receipt };
}

/**
 * Gate entry point for Lutar.QEC.Kitaev.
 */
export function kitaevSurfaceGate(
  v: VertexCheck,
  errorSites: Site[],
  signer: Signer
): { hasSyndrome: boolean; receipt: DSSEReceipt } {
  const { parity, receipt } = emitKitaevSurfaceReceipt(v, errorSites, signer);
  return { hasSyndrome: parity, receipt };
}
