// SPDX-License-Identifier: Apache-2.0
// Module: ouroboros/lambda-gate/knot-tag
// v15 §10.2 (Knot Calculus) graft. Adds a knot-invariant tag emission
// alongside every Λ check, so downstream auditors can compute audit-
// Reidemeister equivalence classes without re-running the gate.
//
// Sources:
//   - Reidemeister (1927), Abh. Math. Sem. Univ. Hamburg 5:24-32.
//   - Bar-Natan (1995), "On the Vassiliev knot invariants", Topology
//     34:423-472.
//   - Vassiliev (1990), "Cohomology of knot spaces", Adv. Sov. Math. 1:23-69.
//
// Lean obligation: Lutar/Knot/ReidemeisterConjecture.lean (CONJECTURE,
// target v16). The runtime tag emitted here is a deterministic witness
// that compares equal across receipts believed (per the conjecture) to lie
// in the same equivalence class; it is *not* itself a proof of equivalence.

import { createHash } from "node:crypto";
import type { Axes } from "@szl/ouroboros-types";
import { computeLambda, evaluateAxes, type EvalResult } from "./gate.js";

/** Knot-invariant tag for a Λ-check evaluation. The tag is a 16-hex-char
 * prefix of SHA-256(skeleton | Λ-bucket), where:
 *   - skeleton = sorted "(axisName:passBit)" pairs (the chord-diagram skeleton
 *     of the 9-axis receipt)
 *   - Λ-bucket = floor(Λ × 100) / 100  (centi-Λ; the audit-coarse Λ value
 *     that two receipts in the same audit-Reidemeister class must share).
 *
 * Two receipts that produce the same tag are *candidates* for the same
 * audit-Reidemeister equivalence class. The R1/R2/R3 conjectures in
 * Lutar/Knot/ReidemeisterConjecture.lean state that this candidacy is in
 * fact equality; the tag itself is a runtime witness, not a proof. */
export function knotInvariantTag(axes: Axes, lambda: number): string {
  const PASS = 0.9; // matches LAMBDA_THRESHOLD in gate.ts
  const skeleton = Object.entries(axes)
    .map(([k, v]) => `${k}:${v >= PASS ? 1 : 0}`)
    .sort()
    .join("|");
  // Centi-Λ bucket: two receipts with Λ in the same 1/100-th band share a tag.
  const lambdaBucket = Math.floor(lambda * 100) / 100;
  return createHash("sha256")
    .update(`knot|${skeleton}|${lambdaBucket.toFixed(2)}`)
    .digest("hex")
    .slice(0, 16);
}

/** Extends `EvalResult` with a knot-invariant tag. The returned object
 * preserves all original fields verbatim; downstream consumers that do not
 * care about v15 can ignore the new field. */
export interface KnotEvalResult extends EvalResult {
  knotTag: string;
}

/** Run the standard Λ-gate evaluation and attach a knot-invariant tag. */
export function evaluateAxesWithKnotTag(axes: Axes): KnotEvalResult {
  const result = evaluateAxes(axes);
  return { ...result, knotTag: knotInvariantTag(axes, result.lambda) };
}

/** Convenience: compute Λ + knot tag together without running the gate's
 * pass/fail logic. Useful for off-line audit pipelines. */
export function computeLambdaWithKnotTag(
  axes: Axes,
): { lambda: number; knotTag: string } {
  const lambda = computeLambda(axes);
  return { lambda, knotTag: knotInvariantTag(axes, lambda) };
}
