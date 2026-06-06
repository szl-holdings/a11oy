// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 4 — OpenTelemetry span wrapper for FalsePosition
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/Calibration/FalsePosition.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371

import { createHash } from "node:crypto";
import type { OtelSpan } from "../exporter.js";

const FORMULA_NAME    = "FalsePosition";
const LEAN_FILE       = "Lutar/Calibration/FalsePosition.lean";
const LEAN_COMMIT_SHA = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const LEAN_BLOB_SHA   = "8a6624ce183ede9d634f4d251f53c57f54ffaae4";

/**
 * False-position correction for affine gate calibration.
 * Lean: `false_position_correct`
 * Lean file: Lutar/Calibration/FalsePosition.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 */
function _falsePosition(x1: number, y1: number, x2: number, y2: number, T: number):
  { xStar: number; lambdaScore: number } {
  const dy = y2 - y1;
  if (Math.abs(dy) < Number.EPSILON * Math.max(Math.abs(y1), Math.abs(y2), 1)) {
    throw new Error("FalsePosition: degenerate samples (y₁ = y₂)");
  }
  const xStar = x1 + ((T - y1) * (x2 - x1)) / dy;
  const m = dy / (x2 - x1);
  const c = y1 - m * x1;
  const residual = Math.abs(m * xStar + c - T);
  const lambdaScore = Math.max(0, 1 - residual / (1 + Math.abs(T)));
  return { xStar, lambdaScore };
}

export interface FalsePositionSpanOpts {
  x1: number; y1: number;
  x2: number; y2: number;
  T: number;
  traceId?: string;
}

export interface FalsePositionSpanResult {
  span: OtelSpan;
  xStar: number;
  lambdaScore: number;
}

/**
 * Invoke FalsePosition and emit an OTLP-compatible OTel span with SZL formula attributes.
 */
export function falsePositionSpan(opts: FalsePositionSpanOpts): FalsePositionSpanResult {
  const { x1, y1, x2, y2, T } = opts;

  const startTime = Date.now();
  const { xStar, lambdaScore } = _falsePosition(x1, y1, x2, y2, T);
  const endTime = Date.now();

  const traceId = opts.traceId ?? createHash("sha256")
    .update(`${FORMULA_NAME}:${x1}:${y1}:${x2}:${y2}:${T}:${startTime}`)
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
      "false_position.x1": x1,
      "false_position.y1": y1,
      "false_position.x2": x2,
      "false_position.y2": y2,
      "false_position.T":  T,
      "false_position.xStar": xStar,
    },
  };

  return { span, xStar, lambdaScore };
}
