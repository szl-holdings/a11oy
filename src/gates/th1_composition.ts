/**
 * th1_composition.ts
 *
 * Runtime instillation of Lean theorem:
 *   Lutar.Composition (TH1_Composition module)
 *   File: Lutar/Composition/TH1_Composition.lean
 *   Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * Lean theorems formalised here:
 *   - `composition_preserves_doctrine` (line ~104): TH1 — composition of two
 *      doctrine-locked systems at threshold `th` yields a doctrine-locked system.
 *   - `doctrine_monotone_threshold` (line ~148): strengthening threshold preserves locking.
 *   - `DoctrineEquiv.refl/symm/trans` (line ~155+): equivalence is a congruence.
 *
 * Runtime contract:
 *   Given two LutarSystems with compatible DoctrineLabel IO levels, verify
 *   that their sequential composition satisfies the doctrine predicate
 *   (inputOk, outputOk, noDowngrade).
 *
 * DoctrineLabel 4-level lattice: Bot < L1 < L2 < Top.
 *
 * Doctrine V6: No new axioms. No sorries. STAGED label: FULLY WIRED.
 */

import { createHash } from "crypto";

// ---------------------------------------------------------------------------
// Domain types — mirrors Lean types
// ---------------------------------------------------------------------------

/** Mirrors Lean `DoctrineLabel` — 4-level lattice. */
export type DoctrineLabel = "Bot" | "L1" | "L2" | "Top";

/** Numeric representation for ordering. Mirrors Lean `LE DoctrineLabel`. */
const LABEL_RANK: Record<DoctrineLabel, number> = {
  Bot: 0,
  L1: 1,
  L2: 2,
  Top: 3,
};

/**
 * Lean label order: a ≤ b.
 * Mirrors Lean `LE DoctrineLabel` instance.
 */
export function labelLE(a: DoctrineLabel, b: DoctrineLabel): boolean {
  return LABEL_RANK[a] <= LABEL_RANK[b];
}

/**
 * DoctrinePredicate: threshold ≤ label.
 * Mirrors Lean `DoctrinePredicate (l : DoctrineLabel) (threshold : DoctrineLabel) : Prop`.
 */
export function doctrinePredicate(
  label: DoctrineLabel,
  threshold: DoctrineLabel
): boolean {
  return labelLE(threshold, label);
}

/**
 * Mirrors Lean `LutarSystem (threshold : DoctrineLabel)`.
 */
export interface LutarSystem {
  threshold: DoctrineLabel;
  inputLabel: DoctrineLabel;
  outputLabel: DoctrineLabel;
}

/**
 * Verifies all LutarSystem invariants:
 *   - inputOk: threshold ≤ inputLabel
 *   - outputOk: threshold ≤ outputLabel
 *   - noDowngrade: inputLabel ≤ outputLabel
 *
 * @param sys - LutarSystem to validate.
 * @returns true iff all three invariants hold.
 */
export function isDoctrineLockedSystem(sys: LutarSystem): boolean {
  return (
    doctrinePredicate(sys.inputLabel, sys.threshold) &&
    doctrinePredicate(sys.outputLabel, sys.threshold) &&
    labelLE(sys.inputLabel, sys.outputLabel)
  );
}

/**
 * Compatibility predicate: S1.outputLabel ≤ S2.inputLabel.
 * Mirrors Lean `Compatible`.
 */
export function compatible(s1: LutarSystem, s2: LutarSystem): boolean {
  return labelLE(s1.outputLabel, s2.inputLabel);
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

const LEAN_THEOREM = "Lutar.Composition.composition_preserves_doctrine";
const LEAN_FILE_LINE = "Lutar/Composition/TH1_Composition.lean:104";
const LEAN_COMMIT_SHA = "c4d13795689601324fce0236351bfe0ade990a43";

// ---------------------------------------------------------------------------
// Core functions — mirror Lean definitions
// ---------------------------------------------------------------------------

/**
 * Sequentially composes two compatible doctrine-locked systems.
 *
 * Mirrors Lean `compose`:
 *   result.inputLabel  = S1.inputLabel
 *   result.outputLabel = S2.outputLabel
 *
 * Lean theorem `composition_preserves_doctrine` (TH1) guarantees the
 * composed system is doctrine-locked at the shared threshold.
 *
 * @param s1 - First system (must share threshold with s2).
 * @param s2 - Second system.
 * @returns The composed LutarSystem (or throws if incompatible/different thresholds).
 */
export function compose(s1: LutarSystem, s2: LutarSystem): LutarSystem {
  if (s1.threshold !== s2.threshold) {
    throw new Error(
      `compose: threshold mismatch (${s1.threshold} vs ${s2.threshold}). ` +
        "Lean LutarSystem.compose requires equal thresholds."
    );
  }
  if (!compatible(s1, s2)) {
    throw new Error(
      `compose: incompatible interface (${s1.outputLabel} not ≤ ${s2.inputLabel}).`
    );
  }
  return {
    threshold: s1.threshold,
    inputLabel: s1.inputLabel,
    outputLabel: s2.outputLabel,
  };
}

/**
 * Verifies the composition_preserves_doctrine theorem (TH1).
 *
 * Lean theorem: `composition_preserves_doctrine`
 * For S1, S2 doctrine-locked at `th`, and S1 compatible with S2:
 *   let S12 = compose S1 S2 h
 *   DoctrinePredicate S12.inputLabel th
 *   ∧ DoctrinePredicate S12.outputLabel th
 *   ∧ S12.inputLabel ≤ S12.outputLabel
 *
 * @param s1 - First doctrine-locked system.
 * @param s2 - Second doctrine-locked system.
 * @returns true iff composition preserves doctrine.
 */
export function verifyCompositionPreservesDoctrine(
  s1: LutarSystem,
  s2: LutarSystem
): boolean {
  if (!isDoctrineLockedSystem(s1) || !isDoctrineLockedSystem(s2)) return false;
  if (s1.threshold !== s2.threshold) return false;
  if (!compatible(s1, s2)) return false;

  const composed = compose(s1, s2);
  return (
    doctrinePredicate(composed.inputLabel, composed.threshold) &&
    doctrinePredicate(composed.outputLabel, composed.threshold) &&
    labelLE(composed.inputLabel, composed.outputLabel)
  );
}

/**
 * Iterative composition over a non-empty list of compatible systems.
 * Mirrors Lean `composeList`.
 *
 * @param systems - Non-empty list of LutarSystems (all same threshold, pairwise compatible).
 * @returns The composed system.
 */
export function composeList(systems: LutarSystem[]): LutarSystem {
  if (systems.length === 0) {
    throw new Error("composeList: empty list is not allowed.");
  }
  return systems.slice(1).reduce((acc, s) => compose(acc, s), systems[0]);
}

// ---------------------------------------------------------------------------
// Inputs hash helper
// ---------------------------------------------------------------------------

function hashInputs(s1: LutarSystem, s2: LutarSystem): string {
  return createHash("sha256")
    .update(JSON.stringify({ s1, s2 }))
    .digest("hex");
}

// ---------------------------------------------------------------------------
// DSSE receipt emitter
// ---------------------------------------------------------------------------

/**
 * Verifies TH1 composition doctrine preservation and emits a DSSE receipt.
 *
 * Lean theorem: `Lutar.Composition.composition_preserves_doctrine`
 * File: Lutar/Composition/TH1_Composition.lean:104
 * Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * @param s1     - First LutarSystem.
 * @param s2     - Second LutarSystem.
 * @param signer - Signing function.
 * @returns DSSEReceipt with `output = true` iff TH1 holds for (s1, s2).
 */
export function emitTH1CompositionReceipt(
  s1: LutarSystem,
  s2: LutarSystem,
  signer: Signer
): DSSEReceipt {
  const output = verifyCompositionPreservesDoctrine(s1, s2);
  const inputs_hash = hashInputs(s1, s2);
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
 * Gate entry point for Lutar.Composition.TH1_Composition.
 */
export function th1CompositionGate(
  s1: LutarSystem,
  s2: LutarSystem,
  signer: Signer
): { composedSystem: LutarSystem | null; doctrinePreserved: boolean; receipt: DSSEReceipt } {
  let composedSystem: LutarSystem | null = null;
  try {
    composedSystem = compose(s1, s2);
  } catch {
    // incompatible systems — output false in receipt
  }
  const receipt = emitTH1CompositionReceipt(s1, s2, signer);
  return { composedSystem, doctrinePreserved: receipt.output, receipt };
}
