// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 4 — OpenTelemetry span wrapper for LiuHuiPi
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/Banach/LiuHuiPi.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371

import { createHash } from "node:crypto";
import type { OtelSpan } from "../exporter.js";

const FORMULA_NAME    = "LiuHuiPi";
const LEAN_FILE       = "Lutar/Banach/LiuHuiPi.lean";
const LEAN_COMMIT_SHA = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const LEAN_BLOB_SHA   = "3c98c3a608d2d204900737b72fac60e51025083b";

/**
 * Liu Hui polygon-doubling π estimate at step k.
 * Lean: `sideSquared_bounds`, `liuHuiPi`
 * Lean file: Lutar/Banach/LiuHuiPi.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 */
function _liuHuiPi(k: number): { sideCount: number; piEstimate: number; absError: number; lambdaScore: number } {
  let sq = 1;
  for (let i = 0; i < k; i++) sq = 2 - Math.sqrt(4 - sq);
  const sideCount = 6 * Math.pow(2, k);
  const piEstimate = (sideCount * Math.sqrt(sq)) / 2;
  const absError = Math.abs(piEstimate - Math.PI);
  const lambdaScore = Math.max(0, 1 - absError / Math.PI);
  return { sideCount, piEstimate, absError, lambdaScore };
}

export interface LiuHuiPiSpanOpts {
  k: number;
  traceId?: string;
}

export interface LiuHuiPiSpanResult {
  span: OtelSpan;
  piEstimate: number;
  lambdaScore: number;
}

/**
 * Invoke LiuHuiPi and emit an OTLP-compatible OTel span with SZL formula attributes.
 */
export function liuHuiPiSpan(opts: LiuHuiPiSpanOpts): LiuHuiPiSpanResult {
  const { k } = opts;
  if (!Number.isInteger(k) || k < 0 || k > 50) {
    throw new Error(`LiuHuiPi: k must be a non-negative integer ≤ 50; got ${k}`);
  }

  const startTime = Date.now();
  const { sideCount, piEstimate, absError, lambdaScore } = _liuHuiPi(k);
  const endTime = Date.now();

  const traceId = opts.traceId ?? createHash("sha256")
    .update(`${FORMULA_NAME}:${k}:${startTime}`)
    .digest("hex").slice(0, 32);

  const spanId = createHash("sha256")
    .update(`${traceId}:${FORMULA_NAME}`)
    .digest("hex").slice(0, 16);

  const span: OtelSpan = {
    spanId,
    traceId,
    name:      `szl.formula.${FORMULA_NAME}`,
    startTime,
    endTime,
    status:    "OK",
    attributes: {
      "szl.formula.name":        FORMULA_NAME,
      "szl.formula.lean_file":   LEAN_FILE,
      "szl.formula.commit_sha":  LEAN_COMMIT_SHA,
      "szl.formula.blob_sha":    LEAN_BLOB_SHA,
      "szl.formula.lambda_score": lambdaScore,
      "liu_hui.k":               k,
      "liu_hui.side_count":      sideCount,
      "liu_hui.pi_estimate":     piEstimate,
      "liu_hui.abs_error":       absError,
    },
  };

  return { span, piEstimate, lambdaScore };
}
