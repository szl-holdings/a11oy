// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 4 — OpenTelemetry span wrapper for BekensteinBound
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/Putnam/BekensteinBound.lean
//   Lean commit SHA: 7ec70ba760f3953db34738e8805d67c6cc64bd7e
//   Lean blob SHA:   5b8c84a576d8a94fbf30c89479f5e8fc425feff0
//
// Wraps the bekensteinBound formula in an OTel span with required SZL attributes:
//   szl.formula.name         — "bekenstein_bound"
//   szl.formula.lean_file    — "Lutar/Putnam/BekensteinBound.lean"
//   szl.formula.commit_sha   — "7ec70ba760f3953db34738e8805d67c6cc64bd7e"
//   szl.formula.lambda_score — the Λ-score returned by the formula
//
// Pattern: reuses OtelSpan from runtime/src/exporter.ts (no @opentelemetry/api dep),
// mirroring runtime/src/formulas/madhavaBound.ts.

import { createHash } from "node:crypto";
import type { OtelSpan } from "../exporter.js";

// ── Formula constants ─────────────────────────────────────────────────────────

const FORMULA_NAME      = "bekenstein_bound";
const LEAN_FILE         = "Lutar/Putnam/BekensteinBound.lean";
const LEAN_COMMIT_SHA   = "7ec70ba760f3953db34738e8805d67c6cc64bd7e";
const LEAN_BLOB_SHA     = "5b8c84a576d8a94fbf30c89479f5e8fc425feff0";

// ── Inline BekensteinBound implementation ────────────────────────────────────
// Doc-comment references the Lean theorem explicitly.
//
// The Bekenstein bound: for a bounded region with mass-energy E and radius R,
// the maximum information content (entropy S, nats) is bounded by
//   S ≤ 2π E R / (ℏ c).
// Placeholder constants (ℏ = c = 1) mirror the Lean stub, whose physically
// calibrated values are not yet available in Mathlib at this depth.

const HBAR = 1; // ℏ placeholder — NOT physically calibrated (see Lean docstring)
const C    = 1; // c  placeholder — NOT physically calibrated (see Lean docstring)

/**
 * Bekenstein entropy bound.
 * Lean: `bekenstein_bound` (zero-sorry scaffold) and
 *       `bekenstein_bound_conjecture` (sorry-tagged full bound)
 * Lean file: Lutar/Putnam/BekensteinBound.lean
 *   (commit 7ec70ba760f3953db34738e8805d67c6cc64bd7e)
 *
 * Returns: the upper bound on entropy/information content, and a Λ-score.
 */
function _bekensteinBound(E: number, R: number): { bound: number; lambdaScore: number } {
  const bound = (2 * Math.PI * E * R) / (HBAR * C);
  // Λ-score is a normalized saturation proxy in [0,1]; for the scaffold we
  // report full confidence in the (proved) nonnegativity of the coefficient.
  const lambdaScore = bound >= 0 ? 1 : 0;
  return { bound, lambdaScore };
}

// ── OTel span wrapper ─────────────────────────────────────────────────────────

export interface BekensteinBoundSpanOpts {
  /** Mass-energy E (≥ 0). */
  E: number;
  /** Enclosing radius R (≥ 0). */
  R: number;
  traceId?: string;
}

export interface BekensteinBoundSpanResult {
  span: OtelSpan;
  bound: number;
  lambdaScore: number;
}

/**
 * Invoke BekensteinBound and emit an OTLP-compatible OTel span with SZL formula
 * attributes. Emits `szl.formula.name = "bekenstein_bound"` whenever the
 * Bekenstein bound formula is computed in the agentic formulas runtime.
 *
 * Required span attributes (Doctrine v11 formula layer):
 *   szl.formula.name, szl.formula.lean_file, szl.formula.commit_sha, szl.formula.lambda_score
 */
export function bekensteinBoundSpan(opts: BekensteinBoundSpanOpts): BekensteinBoundSpanResult {
  const { E, R } = opts;

  if (!Number.isFinite(E) || E < 0) {
    throw new Error(`bekenstein_bound: E must be a nonnegative finite number; got ${E}`);
  }
  if (!Number.isFinite(R) || R < 0) {
    throw new Error(`bekenstein_bound: R must be a nonnegative finite number; got ${R}`);
  }

  const startTime = Date.now();
  const { bound, lambdaScore } = _bekensteinBound(E, R);
  const endTime = Date.now();

  const traceId = opts.traceId ?? createHash("sha256")
    .update(`${FORMULA_NAME}:${E}:${R}:${startTime}`)
    .digest("hex")
    .slice(0, 32);

  const spanId = createHash("sha256")
    .update(`${traceId}:${FORMULA_NAME}`)
    .digest("hex")
    .slice(0, 16);

  const span: OtelSpan = {
    spanId,
    traceId,
    name:      `szl.formula.${FORMULA_NAME}`,
    startTime,
    endTime,
    status:    "OK",
    attributes: {
      // Required SZL formula attributes
      "szl.formula.name":        FORMULA_NAME,
      "szl.formula.lean_file":   LEAN_FILE,
      "szl.formula.commit_sha":  LEAN_COMMIT_SHA,
      "szl.formula.blob_sha":    LEAN_BLOB_SHA,
      "szl.formula.lambda_score": lambdaScore,
      // Formula-specific inputs/outputs
      "bekenstein.E":            E,
      "bekenstein.R":            R,
      "bekenstein.bound":        bound,
      "bekenstein.hbar":         HBAR,
      "bekenstein.c":            C,
    },
  };

  return { span, bound, lambdaScore };
}
