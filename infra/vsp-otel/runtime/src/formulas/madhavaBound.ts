// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 4 — OpenTelemetry span wrapper for MadhavaBound
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/PACBayes/MadhavaBound.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// Wraps the madhavaBound formula in an OTel span with required SZL attributes:
//   szl.formula.name         — "MadhavaBound"
//   szl.formula.lean_file    — "Lutar/PACBayes/MadhavaBound.lean"
//   szl.formula.commit_sha   — "1dca00032dfc9aa8559cc6c2e4b63192fcf52371"
//   szl.formula.lambda_score — the Λ-score returned by the formula
//
// Pattern: reuses OtelSpan from runtime/src/exporter.ts (no @opentelemetry/api dep)

import { createHash } from "node:crypto";
import type { OtelSpan } from "../exporter.js";

// ── Formula constants ─────────────────────────────────────────────────────────

const FORMULA_NAME      = "MadhavaBound";
const LEAN_FILE         = "Lutar/PACBayes/MadhavaBound.lean";
const LEAN_COMMIT_SHA   = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const LEAN_BLOB_SHA     = "c8c07dc93a5dbfd6350673065c81b50eb28b940b";

// ── Inline MadhavaBound implementation (mirrors ouroboros Layer 2) ───────────
// Doc-comment references the Lean theorem explicitly.

/**
 * Mādhava alternating-series remainder bound.
 * Lean: `madhavaRemainderBound_nonneg` and `MadhavaBound`
 * Lean file: Lutar/PACBayes/MadhavaBound.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 *
 * Returns: remainderBound = |x|^(2N+1)/(2N+1), and partial N-term sum.
 */
function _madhavaBound(x: number, N: number): { partial: number; remainderBound: number; lambdaScore: number } {
  let partial = 0;
  for (let n = 0; n < N; n++) {
    partial += (n % 2 === 0 ? 1 : -1) * Math.pow(x, 2 * n + 1) / (2 * n + 1);
  }
  const remainderBound = Math.pow(Math.abs(x), 2 * N + 1) / (2 * N + 1);
  const lambdaScore = Math.max(0, Math.min(1, 1 - remainderBound));
  return { partial, remainderBound, lambdaScore };
}

// ── OTel span wrapper ─────────────────────────────────────────────────────────

export interface MadhavaBoundSpanOpts {
  x: number;
  N: number;
  traceId?: string;
}

export interface MadhavaBoundSpanResult {
  span: OtelSpan;
  partial: number;
  remainderBound: number;
  lambdaScore: number;
}

/**
 * Invoke MadhavaBound and emit an OTLP-compatible OTel span with SZL formula attributes.
 *
 * Required span attributes (Doctrine v6 formula layer):
 *   szl.formula.name, szl.formula.lean_file, szl.formula.commit_sha, szl.formula.lambda_score
 */
export function madhavaBoundSpan(opts: MadhavaBoundSpanOpts): MadhavaBoundSpanResult {
  const { x, N } = opts;

  if (!Number.isFinite(x) || Math.abs(x) > 1 + Number.EPSILON) {
    throw new Error(`MadhavaBound: |x| must be ≤ 1; got ${x}`);
  }
  if (!Number.isInteger(N) || N < 1) {
    throw new Error(`MadhavaBound: N must be a positive integer; got ${N}`);
  }

  const startTime = Date.now();
  const { partial, remainderBound, lambdaScore } = _madhavaBound(x, N);
  const endTime = Date.now();

  const traceId = opts.traceId ?? createHash("sha256")
    .update(`${FORMULA_NAME}:${x}:${N}:${startTime}`)
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
      "madhava.x":               x,
      "madhava.N":               N,
      "madhava.partial":         partial,
      "madhava.remainder_bound": remainderBound,
    },
  };

  return { span, partial, remainderBound, lambdaScore };
}
