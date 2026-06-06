// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: ouroboros/lambda-gate  Thesis: TH1 (Λ-Gate), TH11 (Bound)
// Doctrine V6 preflight: ✓ (no forbidden patterns)
//
// Λ unification (fix/lambda-unification): the scalar Λ returned in
// EvalResult.lambda is now the weighted geometric mean with Egyptian
// unit-fraction weights, matching:
//   - Thesis v14 §3.3 Theorem 1 (Uniqueness)
//   - lutar-lean/Lutar/Invariant.lean
//   - platform/packages/ouroboros-invariant/src/lutar-invariant-9.ts
// The previous MIN-fold is retained as `weakestAxis(...)` for diagnostics
// (i.e. "which axis is dragging the gate down?"). It is NOT Λ — see
// ouroboros/docs/lambda-spec.md §3–§4 for the derivation.

import { createHash } from "node:crypto";
import { parseReceipt, type Receipt, type Axes } from "@szl/ouroboros-types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const LAMBDA_THRESHOLD   = 0.90 as const;
export const CRITICAL_THRESHOLD = 0.95 as const;
export const CRITICAL_AXES: ReadonlyArray<keyof Axes> = [
  "moralGrounding",
  "measurabilityHonesty",
] as const;

// ---------------------------------------------------------------------------
// Λ evaluation
// ---------------------------------------------------------------------------

export interface EvalResult {
  /** Λ scalar: weighted geometric mean (canonical, see lambda-spec.md §1). */
  lambda:  number;
  /** Diagnostic: the weakest axis value. NOT Λ. Useful for explaining refusals. */
  weakestAxis: number;
  pass:    boolean;
  axes:    Axes;
  reasons: string[];
}

/** Compute the canonical Λ scalar: weighted geometric mean with Egyptian
 *  unit-fraction weights (all weights = 1/k). Matches Lutar.Invariant.lean. */
export function computeLambda(axes: Axes): number {
  const values = Object.values(axes) as number[];
  if (values.length === 0) return 0;
  for (const v of values) {
    if (!Number.isFinite(v) || v < 0) return 0;
    if (v === 0) return 0;
  }
  const k = values.length;
  let logSum = 0;
  for (const v of values) logSum += Math.log(v);
  return Math.exp(logSum / k);
}

/** Diagnostic helper: minimum axis value. Surfaces "the failing axis" in
 *  reasons / UIs. This is NOT the Λ scalar — see lambda-spec.md §4. */
export function weakestAxis(axes: Axes): number {
  const values = Object.values(axes) as number[];
  if (values.length === 0) return 0;
  return Math.min(...values);
}

/**
 * Conjunctive AND gate verdict (thesis §3.3 Definition 2):
 *  1. Every axis ≥ LAMBDA_THRESHOLD
 *  2. Critical axes (moralGrounding, measurabilityHonesty) ≥ CRITICAL_THRESHOLD
 *  3. Composite Λ (geomean) ≥ LAMBDA_THRESHOLD
 *
 * Verdict semantics are unchanged from the prior MIN-based implementation
 * for the case where all per-axis thresholds equal LAMBDA_THRESHOLD; the
 * critical-axis check was always evaluated separately. The Λ scalar
 * stored on the result now matches the thesis / Lean definition.
 */
export function evaluateAxes(axes: Axes): EvalResult {
  const reasons: string[] = [];
  const lambda = computeLambda(axes);
  const minAxis = weakestAxis(axes);

  for (const [key, val] of Object.entries(axes) as [keyof Axes, number][]) {
    if (val < LAMBDA_THRESHOLD) {
      reasons.push(`axis ${key}=${val.toFixed(3)} < ${LAMBDA_THRESHOLD}`);
    }
  }
  for (const key of CRITICAL_AXES) {
    if (axes[key] < CRITICAL_THRESHOLD) {
      reasons.push(
        `critical axis ${key}=${axes[key].toFixed(3)} < ${CRITICAL_THRESHOLD}`,
      );
    }
  }
  if (lambda < LAMBDA_THRESHOLD) {
    reasons.push(`composite Λ=${lambda.toFixed(4)} < ${LAMBDA_THRESHOLD}`);
  }

  return { lambda, weakestAxis: minAxis, axes, pass: reasons.length === 0, reasons };
}

// ---------------------------------------------------------------------------
// Receipt store (in-memory; production: replace with persistent adapter)
// ---------------------------------------------------------------------------

const store = new Map<string, Receipt>();

export function storeReceipt(r: Receipt): void {
  store.set(r.hash, r);
}

export function getReceipt(hash: string): Receipt | undefined {
  return store.get(hash);
}

export function allReceipts(): Receipt[] {
  return Array.from(store.values());
}

// ---------------------------------------------------------------------------
// Hash helper
// ---------------------------------------------------------------------------

export function hashPayload(payload: unknown): string {
  return createHash("sha256")
    .update(JSON.stringify(payload))
    .digest("hex");
}

// ---------------------------------------------------------------------------
// Gate transit — main entry point
// ---------------------------------------------------------------------------

export interface GateTransitResult {
  receipt: Receipt;
  eval:    EvalResult;
  stored:  boolean;
}

/**
 * Evaluate a raw receipt candidate through the Λ-gate.
 * Stores it only when pass=true.
 */
export function gateTransit(raw: unknown): GateTransitResult {
  const receipt = parseReceipt(raw);
  const evalResult = evaluateAxes(receipt.axes);
  const stored = evalResult.pass;
  if (stored) storeReceipt(receipt);
  return { receipt, eval: evalResult, stored };
}

// ---------------------------------------------------------------------------
// Replay verification
// ---------------------------------------------------------------------------

export interface VerifyResult {
  found:  boolean;
  pass:   boolean;
  lambda: number;
  reasons: string[];
}

/** Retrieve a stored receipt by hash and re-run the gate evaluation. */
export function verifyReceipt(hash: string): VerifyResult {
  const r = getReceipt(hash);
  if (!r) return { found: false, pass: false, lambda: 0, reasons: ["not found"] };
  const { eval: ev } = gateTransit(r);
  return { found: true, pass: ev.pass, lambda: ev.lambda, reasons: ev.reasons };
}
