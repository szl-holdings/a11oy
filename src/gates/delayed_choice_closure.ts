/**
 * delayed_choice_closure.ts
 *
 * Runtime instillation of Lean theorem:
 *   Lutar.Wheeler (DelayedChoiceClosure module)
 *   File: Lutar/Wheeler/DelayedChoiceClosure.lean
 *   Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * Lean theorems formalised here:
 *   - `delayed_choice_idempotent` (line ~100): closing label twice yields same label.
 *   - `wheeler_window_safety` (line ~111): late receipts → Bot (past-immutable).
 *   - `wheeler_window_admits_zero_offset` (line ~121): receipt at span end is admissible.
 *   - `wheeler_window_admits_max_offset` (line ~130): receipt at span end + W is admissible.
 *   - `early_receipt_rejected` (line ~139): pre-span receipts are inadmissible.
 *   - `wrong_span_rejected` (line ~148): wrong span ID → inadmissible.
 *
 * Runtime contract:
 *   Given a span (id, start, endAt) and a receipt (span, closeAt, label),
 *   determine admissibility within the Wheeler window W=1000 ticks.
 *   Return the closed doctrine label (or Bot for inadmissible receipts).
 *
 * Citations (from Lean file):
 *   - Wheeler (1978) — delayed-choice double-slit experiment
 *   - Jacques et al. (2007) DOI 10.1126/science.1136303
 *   - Manning et al. (2015) DOI 10.1038/nphys3343
 *
 * Doctrine V6: No new axioms. No sorries. STAGED label: FULLY WIRED.
 */

import { createHash } from "crypto";

// ---------------------------------------------------------------------------
// Domain types — mirrors Lean types
// ---------------------------------------------------------------------------

/** Doctrine label — 4-level lattice. Mirrors Lean `DoctrineLabel`. */
export type DoctrineLabel = "Bot" | "L1" | "L2" | "Top";

/** Mirrors Lean `Span`. */
export interface Span {
  id: number;
  start: number; // Tick (TAI64N abstract)
  endAt: number;
}

/** Mirrors Lean `Receipt`. */
export interface WheelerReceipt {
  span: number;       // SpanId
  closeAt: number;    // Tick
  label: DoctrineLabel;
}

/** DSSE-shaped receipt. */
export interface DSSEReceipt {
  theorem: string;
  lean_commit_sha: string;
  inputs_hash: string;
  output: DoctrineLabel;
  ts: string;
  sig: string;
}

export type Signer = (payload: string) => string;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Wheeler window size in abstract ticks. Mirrors Lean `W : Tick := 1000`. */
export const WHEELER_WINDOW = 1000;

const LEAN_THEOREM = "Lutar.Wheeler.delayed_choice_idempotent";
const LEAN_FILE_LINE = "Lutar/Wheeler/DelayedChoiceClosure.lean:100";
const LEAN_COMMIT_SHA = "c4d13795689601324fce0236351bfe0ade990a43";

// ---------------------------------------------------------------------------
// Core functions — mirror Lean definitions
// ---------------------------------------------------------------------------

/**
 * Determines whether a receipt is admissible for a span.
 *
 * Mirrors Lean:
 *   `def admissible (s : Span) (r : Receipt) : Prop :=
 *      r.span = s.id ∧ s.endAt ≤ r.closeAt ∧ r.closeAt ≤ s.endAt + W`
 *
 * Lean theorem `early_receipt_rejected` proves pre-span receipts fail.
 * Lean theorem `wrong_span_rejected` proves wrong-span receipts fail.
 * Lean theorem `wheeler_window_safety` proves late receipts are rejected.
 *
 * @param span    - The execution span.
 * @param receipt - The candidate receipt.
 * @returns true iff the receipt is admissible.
 */
export function admissible(span: Span, receipt: WheelerReceipt): boolean {
  return (
    receipt.span === span.id &&
    span.endAt <= receipt.closeAt &&
    receipt.closeAt <= span.endAt + WHEELER_WINDOW
  );
}

/**
 * Computes the closed doctrine label for a span given a receipt.
 *
 * Mirrors Lean:
 *   `def closeLabel (s : Span) (r : Receipt) : DoctrineLabel :=
 *      if admissible s r then r.label else DoctrineLabel.Bot`
 *
 * Lean theorem `delayed_choice_idempotent`: stable under re-closure.
 * Lean theorem `wheeler_window_safety`: late receipt → Bot.
 *
 * @param span    - The execution span.
 * @param receipt - The candidate receipt.
 * @returns The resolved DoctrineLabel.
 */
export function closeLabel(span: Span, receipt: WheelerReceipt): DoctrineLabel {
  return admissible(span, receipt) ? receipt.label : "Bot";
}

// ---------------------------------------------------------------------------
// Inputs hash helper
// ---------------------------------------------------------------------------

function hashInputs(span: Span, receipt: WheelerReceipt): string {
  return createHash("sha256")
    .update(JSON.stringify({ span, receipt }))
    .digest("hex");
}

// ---------------------------------------------------------------------------
// DSSE receipt emitter
// ---------------------------------------------------------------------------

/**
 * Applies Wheeler audit closure and emits a DSSE receipt.
 *
 * Lean theorem: `Lutar.Wheeler.delayed_choice_idempotent`
 * File: Lutar/Wheeler/DelayedChoiceClosure.lean:100
 * Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * The `output` field holds the resolved DoctrineLabel.
 *
 * @param span       - The execution span.
 * @param receipt    - The candidate receipt.
 * @param signer     - Signing function.
 * @returns DSSE receipt containing the resolved label.
 */
export function emitDelayedChoiceReceipt(
  span: Span,
  receipt: WheelerReceipt,
  signer: Signer
): { label: DoctrineLabel; dsse: DSSEReceipt } {
  const label = closeLabel(span, receipt);
  const inputs_hash = hashInputs(span, receipt);
  const ts = new Date().toISOString();

  const sigPayload = JSON.stringify({
    theorem: LEAN_THEOREM,
    lean_commit_sha: LEAN_COMMIT_SHA,
    inputs_hash,
    output: label,
    ts,
  });

  const dsse: DSSEReceipt = {
    theorem: LEAN_THEOREM,
    lean_commit_sha: LEAN_COMMIT_SHA,
    inputs_hash,
    output: label,
    ts,
    sig: signer(sigPayload),
  };

  return { label, dsse };
}

/**
 * Gate entry point for Lutar.Wheeler.DelayedChoiceClosure.
 */
export function delayedChoiceClosureGate(
  span: Span,
  receipt: WheelerReceipt,
  signer: Signer
): { label: DoctrineLabel; admissible: boolean; dsse: DSSEReceipt } {
  const isAdmissible = admissible(span, receipt);
  const { label, dsse } = emitDelayedChoiceReceipt(span, receipt, signer);
  return { label, admissible: isAdmissible, dsse };
}
