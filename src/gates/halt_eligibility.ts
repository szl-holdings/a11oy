/**
 * halt_eligibility.ts
 *
 * Runtime instillation of Lean theorem:
 *   Lutar.HUKLLA.HaltEligibility
 *   File: Lutar/HUKLLA/HaltEligibility.lean
 *   Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * Lean theorems formalised here:
 *   - `halt_eligibility_monotone` (line ~81): eligibility is monotone in lambda_score
 *   - `halt_eligibility_decidable` (line ~96): Decidable instance
 *   - `not_eligible_of_low_score` (line ~103): score < 0.90 → not eligible
 *
 * Runtime contract:
 *   Given an ExecutionTrace (lambdaScore, receiptsClosed, rhoClosure),
 *   emit a DSSE receipt asserting whether the trace is halt-eligible.
 *   The 0.90 threshold matches A11OY_DOCTRINE_LAMBDA_FLOOR=0.90.
 *
 * Doctrine v7: No new axioms. No sorries. STAGED label: gate is FULLY WIRED.
 */

import { createHash } from "crypto";

// ---------------------------------------------------------------------------
// Domain types
// ---------------------------------------------------------------------------

/** Mirrors Lean `ExecutionTrace` structure. */
export interface ExecutionTrace {
  /** Lambda trust score ∈ [0, 1]. */
  lambdaScore: number;
  /** Receipts confirmed closed. */
  receiptsClosed: boolean;
  /** ρ-closure invariant satisfied. */
  rhoClosure: boolean;
}

/** DSSE-shaped receipt emitted after each gate evaluation. */
export interface DSSEReceipt {
  theorem: string;
  lean_commit_sha: string;
  inputs_hash: string;
  output: boolean;
  ts: string;
  sig: string;
}

/** Signer interface — production uses ECDSA P-256; tests use a mock. */
export type Signer = (payload: string) => string;

// ---------------------------------------------------------------------------
// Anchor constants (matches a11oy/deploy/manifests/a11oy-deployment.yaml L34–35)
// ---------------------------------------------------------------------------

/** The HUKLLA T01/T02 axis floor. */
export const LAMBDA_FLOOR = 0.90;

const LEAN_THEOREM = "Lutar.HUKLLA.HaltEligibility";
const LEAN_FILE_LINE = "Lutar/HUKLLA/HaltEligibility.lean:70";
const LEAN_COMMIT_SHA = "c4d13795689601324fce0236351bfe0ade990a43";

// ---------------------------------------------------------------------------
// Core predicate — mirrors Lean `isHaltEligible`
// ---------------------------------------------------------------------------

/**
 * Evaluates whether an execution trace satisfies HUKLLA halt-eligibility.
 *
 * Lean proof `halt_eligibility_monotone` guarantees: if `t1.lambdaScore ≤ t2.lambdaScore`
 * and booleans are equal, then eligibility is monotone (t1 eligible ⟹ t2 eligible).
 *
 * Lean proof `not_eligible_of_low_score` guarantees: score < 0.90 → false.
 *
 * @param trace - The execution trace to evaluate.
 * @returns true iff all three conditions hold.
 */
export function isHaltEligible(trace: ExecutionTrace): boolean {
  return (
    trace.lambdaScore >= LAMBDA_FLOOR &&
    trace.receiptsClosed &&
    trace.rhoClosure
  );
}

// ---------------------------------------------------------------------------
// Inputs hash helper
// ---------------------------------------------------------------------------

function hashInputs(trace: ExecutionTrace): string {
  const payload = JSON.stringify({
    lambdaScore: trace.lambdaScore,
    receiptsClosed: trace.receiptsClosed,
    rhoClosure: trace.rhoClosure,
  });
  return createHash("sha256").update(payload).digest("hex");
}

// ---------------------------------------------------------------------------
// DSSE receipt emitter
// ---------------------------------------------------------------------------

/**
 * Evaluates halt-eligibility and emits a DSSE-shaped receipt.
 *
 * Lean theorem: `Lutar.HUKLLA.HaltEligibility.halt_eligibility_monotone`
 * File: Lutar/HUKLLA/HaltEligibility.lean:81
 * Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * @param trace  - ExecutionTrace to evaluate.
 * @param signer - Signing function (ECDSA P-256 in production).
 * @returns DSSEReceipt containing the halt-eligibility verdict.
 */
export function emitHaltEligibilityReceipt(
  trace: ExecutionTrace,
  signer: Signer
): DSSEReceipt {
  const output = isHaltEligible(trace);
  const inputs_hash = hashInputs(trace);
  const ts = new Date().toISOString();

  const sigPayload = JSON.stringify({
    theorem: LEAN_THEOREM,
    lean_commit_sha: LEAN_COMMIT_SHA,
    inputs_hash,
    output,
    ts,
  });

  return {
    theorem: LEAN_THEOREM,
    lean_commit_sha: LEAN_COMMIT_SHA,
    inputs_hash,
    output,
    ts,
    sig: signer(sigPayload),
  };
}

// ---------------------------------------------------------------------------
// Gate entry point (convenience wrapper)
// ---------------------------------------------------------------------------

/**
 * The a11oy gate for Lutar.HUKLLA.HaltEligibility.
 * Returns `{ eligible, receipt }`.
 *
 * @param trace  - ExecutionTrace
 * @param signer - Signing function
 */
export function haltEligibilityGate(
  trace: ExecutionTrace,
  signer: Signer
): { eligible: boolean; receipt: DSSEReceipt } {
  const receipt = emitHaltEligibilityReceipt(trace, signer);
  return { eligible: receipt.output, receipt };
}
