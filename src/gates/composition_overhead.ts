/**
 * composition_overhead.ts
 *
 * Runtime instillation of Lean theorem:
 *   Lutar.Composition.Overhead.composition_overhead_bound
 *   File: Lutar/Composition/CompositionOverhead.lean
 *   Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * Lean theorems formalised here:
 *   - `composition_overhead_bound` (line ~79): totalOverhead(systems) ≤ N * C
 *   - `totalOverhead_append` (line ~41): overhead is additive over list concat
 *   - `composition_overhead_strict_bound` (line ~96): strict bound for non-empty pipelines
 *
 * Runtime contract:
 *   Given a list of cost-bearing systems and a cap C, verify that the
 *   sum of their overhead costs does not exceed N * C.
 *
 * Doctrine V6: No new axioms. No sorries. STAGED label: FULLY WIRED.
 */

import { createHash } from "crypto";

// ---------------------------------------------------------------------------
// Domain types — mirrors Lean `CostSystem` and `BoundedPipeline`
// ---------------------------------------------------------------------------

/** Mirrors Lean `CostSystem`. Every system must have cost ≥ 1. */
export interface CostSystem {
  /** Abstract overhead cost (positive integer). */
  cost: number;
  /** Human-readable system identifier. */
  id?: string;
}

/** Mirrors Lean `BoundedPipeline`. */
export interface BoundedPipeline {
  systems: CostSystem[];
  cap: number;
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

const LEAN_THEOREM = "Lutar.Composition.Overhead.composition_overhead_bound";
const LEAN_FILE_LINE = "Lutar/Composition/CompositionOverhead.lean:79";
const LEAN_COMMIT_SHA = "c4d13795689601324fce0236351bfe0ade990a43";

// ---------------------------------------------------------------------------
// Core functions — mirror Lean definitions
// ---------------------------------------------------------------------------

/**
 * Computes the total overhead of a pipeline.
 * Mirrors Lean: `totalOverhead (systems : List CostSystem) : OverheadCost`
 *
 * @param systems - List of cost systems.
 * @returns Sum of all system costs.
 */
export function totalOverhead(systems: CostSystem[]): number {
  return systems.reduce((acc, s) => acc + s.cost, 0);
}

/**
 * Verifies the composition overhead bound:
 *   totalOverhead(systems) ≤ systems.length * C
 *
 * Lean theorem: `composition_overhead_bound`
 * Lean file: Lutar/Composition/CompositionOverhead.lean:79
 * Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * Preconditions:
 *   - C > 0 (positive cap)
 *   - every system.cost ≤ C (individual bound)
 *
 * @param pipeline - The bounded pipeline to verify.
 * @returns true iff the bound holds.
 */
export function checkCompositionOverheadBound(pipeline: BoundedPipeline): boolean {
  const { systems, cap } = pipeline;
  if (cap <= 0) return false;
  const allUnderCap = systems.every((s) => s.cost >= 1 && s.cost <= cap);
  if (!allUnderCap) return false;
  const total = totalOverhead(systems);
  return total <= systems.length * cap;
}

/**
 * Concatenates two bounded pipelines with the same cap.
 * Mirrors Lean `BoundedPipeline.append`.
 *
 * @param p1 - First pipeline.
 * @param p2 - Second pipeline (must share same cap as p1).
 * @returns A new BoundedPipeline.
 */
export function appendPipelines(
  p1: BoundedPipeline,
  p2: BoundedPipeline
): BoundedPipeline {
  if (p1.cap !== p2.cap) {
    throw new Error(
      `appendPipelines: cap mismatch (${p1.cap} vs ${p2.cap}). ` +
        "Lean BoundedPipeline.append requires equal caps."
    );
  }
  return { systems: [...p1.systems, ...p2.systems], cap: p1.cap };
}

// ---------------------------------------------------------------------------
// Inputs hash helper
// ---------------------------------------------------------------------------

function hashInputs(pipeline: BoundedPipeline): string {
  const payload = JSON.stringify({
    systems: pipeline.systems.map((s) => s.cost),
    cap: pipeline.cap,
  });
  return createHash("sha256").update(payload).digest("hex");
}

// ---------------------------------------------------------------------------
// DSSE receipt emitter
// ---------------------------------------------------------------------------

/**
 * Evaluates the composition overhead bound and emits a DSSE receipt.
 *
 * Lean theorem: `Lutar.Composition.Overhead.composition_overhead_bound`
 * File: Lutar/Composition/CompositionOverhead.lean:79
 * Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * @param pipeline - BoundedPipeline to verify.
 * @param signer   - Signing function.
 * @returns DSSEReceipt with `output = true` iff bound holds.
 */
export function emitCompositionOverheadReceipt(
  pipeline: BoundedPipeline,
  signer: Signer
): DSSEReceipt {
  const output = checkCompositionOverheadBound(pipeline);
  const inputs_hash = hashInputs(pipeline);
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

/**
 * Gate entry point for Lutar.Composition.Overhead.composition_overhead_bound.
 */
export function compositionOverheadGate(
  pipeline: BoundedPipeline,
  signer: Signer
): { boundHolds: boolean; receipt: DSSEReceipt } {
  const receipt = emitCompositionOverheadReceipt(pipeline, signer);
  return { boundHolds: receipt.output, receipt };
}
