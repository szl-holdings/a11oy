/**
 * css_bridge.ts
 *
 * Runtime instillation of Lean theorem:
 *   Lutar.QEC.CSS (CSSBridge module)
 *   File: Lutar/QEC/CSSBridge.lean
 *   Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * Lean theorems formalised here:
 *   - `css_bridge_consistent`: every classical codeword yields a consistent
 *      CSS stabilizer pair (X-parity ⊕ Z-parity = 0xFF).
 *   - `css_bridge_injective`: the bridge is injective — distinct classical
 *      codewords yield distinct stabilizer pairs.
 *
 * Runtime contract:
 *   Given a classical 8-bit codeword (UInt8 as number 0–255), produce the
 *   CSS StabilizerPair and verify consistency (X ⊕ Z = 0xFF).
 *   The bridge models doctrine receipt stabilizer codes in the SZL QEC layer.
 *
 * Citations (from Lean file):
 *   - Calderbank & Shor (1996) DOI 10.1103/PhysRevA.54.1098
 *   - Steane (1996) DOI 10.1098/rspa.1996.0136
 *
 * Doctrine V6: No new axioms. No sorries. STAGED label: FULLY WIRED.
 */

import { createHash } from "crypto";

// ---------------------------------------------------------------------------
// Domain types — mirrors Lean types
// ---------------------------------------------------------------------------

/** Mirrors Lean `ClassicalCodeword` (UInt8). Valid range [0, 255]. */
export type ClassicalCodeword = number;

/** Mirrors Lean `StabilizerPair`. */
export interface StabilizerPair {
  /** X-type parity byte. */
  xParity: number;
  /** Z-type parity byte. */
  zParity: number;
}

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

const LEAN_THEOREM = "Lutar.QEC.CSS.css_bridge_consistent";
const LEAN_FILE_LINE = "Lutar/QEC/CSSBridge.lean:52";
const LEAN_COMMIT_SHA = "c4d13795689601324fce0236351bfe0ade990a43";

const UINT8_MASK = 0xff;

// ---------------------------------------------------------------------------
// Core functions — mirror Lean definitions
// ---------------------------------------------------------------------------

/**
 * Validates a classical codeword is within UInt8 range.
 * @param codeword - The value to validate.
 */
function validateCodeword(codeword: ClassicalCodeword): void {
  if (!Number.isInteger(codeword) || codeword < 0 || codeword > 255) {
    throw new RangeError(
      `classicalToCSS: codeword must be integer in [0,255], got ${codeword}`
    );
  }
}

/**
 * Maps a classical codeword to a CSS StabilizerPair.
 * Mirrors Lean: `def classicalToCSS (c : ClassicalCodeword) : StabilizerPair := ⟨c, c ^^^ 0xFF⟩`
 *
 * @param codeword - 8-bit classical codeword (0–255).
 * @returns StabilizerPair with xParity = codeword, zParity = ~codeword & 0xFF.
 */
export function classicalToCSS(codeword: ClassicalCodeword): StabilizerPair {
  validateCodeword(codeword);
  return {
    xParity: codeword,
    zParity: (codeword ^ UINT8_MASK) & UINT8_MASK,
  };
}

/**
 * Checks whether a stabilizer pair is consistent: xParity ⊕ zParity = 0xFF.
 * Mirrors Lean: `def consistent (p : StabilizerPair) : Bool := (p.xParity ^^^ p.zParity) = 0xFF`
 *
 * Lean theorem `css_bridge_consistent` guarantees that for any codeword c,
 * `consistent (classicalToCSS c) = true`.
 *
 * @param pair - The stabilizer pair to check.
 * @returns true iff consistent.
 */
export function consistent(pair: StabilizerPair): boolean {
  return ((pair.xParity ^ pair.zParity) & UINT8_MASK) === UINT8_MASK;
}

/**
 * Verifies CSS bridge injectivity: distinct codewords yield distinct pairs.
 * Mirrors Lean: `css_bridge_injective`
 *
 * @param a - First codeword.
 * @param b - Second codeword.
 * @returns true iff classicalToCSS(a) ≠ classicalToCSS(b) when a ≠ b.
 */
export function verifyBridgeInjective(
  a: ClassicalCodeword,
  b: ClassicalCodeword
): boolean {
  if (a === b) return true; // trivially, same input → same output
  const pairA = classicalToCSS(a);
  const pairB = classicalToCSS(b);
  return pairA.xParity !== pairB.xParity || pairA.zParity !== pairB.zParity;
}

// ---------------------------------------------------------------------------
// Inputs hash helper
// ---------------------------------------------------------------------------

function hashInputs(codeword: ClassicalCodeword): string {
  return createHash("sha256")
    .update(JSON.stringify({ codeword }))
    .digest("hex");
}

// ---------------------------------------------------------------------------
// DSSE receipt emitter
// ---------------------------------------------------------------------------

/**
 * Applies the CSS bridge to a codeword and emits a DSSE receipt.
 *
 * Lean theorem: `Lutar.QEC.CSS.css_bridge_consistent`
 * File: Lutar/QEC/CSSBridge.lean:52
 * Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * The `output` field in the receipt is `true` iff the produced pair is
 * consistent (which the Lean theorem proves universally).
 *
 * @param codeword - 8-bit classical codeword.
 * @param signer   - Signing function.
 * @returns DSSEReceipt with `output = consistent(classicalToCSS(codeword))`.
 */
export function emitCSSBridgeReceipt(
  codeword: ClassicalCodeword,
  signer: Signer
): { pair: StabilizerPair; receipt: DSSEReceipt } {
  const pair = classicalToCSS(codeword);
  const output = consistent(pair);
  const inputs_hash = hashInputs(codeword);
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

  return { pair, receipt };
}

/**
 * Gate entry point for Lutar.QEC.CSS.css_bridge_consistent.
 */
export function cssBridgeGate(
  codeword: ClassicalCodeword,
  signer: Signer
): { pair: StabilizerPair; consistent: boolean; receipt: DSSEReceipt } {
  const { pair, receipt } = emitCSSBridgeReceipt(codeword, signer);
  return { pair, consistent: receipt.output, receipt };
}
