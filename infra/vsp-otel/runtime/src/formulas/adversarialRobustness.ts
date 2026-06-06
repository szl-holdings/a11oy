// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 4 — OpenTelemetry span wrapper for AdversarialRobustness
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/Composition/AdversarialRobustness.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371

import { createHash } from "node:crypto";
import type { OtelSpan } from "../exporter.js";

const FORMULA_NAME    = "AdversarialRobustness";
const LEAN_FILE       = "Lutar/Composition/AdversarialRobustness.lean";
const LEAN_COMMIT_SHA = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const LEAN_BLOB_SHA   = "a96e448f83da40f06f005e7f8ff0492e0870e819";

/**
 * Adversarial robustness composition bound.
 * Lean: `robustness_preserved_by_composition`
 * Lean file: Lutar/Composition/AdversarialRobustness.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 */
function _adversarialRobustness(l1: number, l2: number, delta: number):
  { epsilon1: number; epsilon2: number; composedLipschitz: number; lambdaScore: number } {
  const epsilon1 = l1 * delta;
  const epsilon2 = l2 * epsilon1;
  const composedLipschitz = l1 * l2;
  const lambdaScore = 1 / (1 + epsilon2);
  return { epsilon1, epsilon2, composedLipschitz, lambdaScore };
}

export interface AdversarialRobustnessSpanOpts {
  lipschitz1: number;
  lipschitz2: number;
  delta: number;
  traceId?: string;
}

export interface AdversarialRobustnessSpanResult {
  span: OtelSpan;
  epsilon2: number;
  lambdaScore: number;
}

/**
 * Invoke AdversarialRobustness and emit an OTLP-compatible OTel span with SZL formula attributes.
 */
export function adversarialRobustnessSpan(opts: AdversarialRobustnessSpanOpts): AdversarialRobustnessSpanResult {
  const { lipschitz1, lipschitz2, delta } = opts;

  if (lipschitz1 <= 0 || !Number.isFinite(lipschitz1))
    throw new Error(`AdversarialRobustness: lipschitz1 must be > 0; got ${lipschitz1}`);
  if (lipschitz2 <= 0 || !Number.isFinite(lipschitz2))
    throw new Error(`AdversarialRobustness: lipschitz2 must be > 0; got ${lipschitz2}`);
  if (delta <= 0 || !Number.isFinite(delta))
    throw new Error(`AdversarialRobustness: delta must be > 0; got ${delta}`);

  const startTime = Date.now();
  const { epsilon1, epsilon2, composedLipschitz, lambdaScore } = _adversarialRobustness(lipschitz1, lipschitz2, delta);
  const endTime = Date.now();

  const traceId = opts.traceId ?? createHash("sha256")
    .update(`${FORMULA_NAME}:${lipschitz1}:${lipschitz2}:${delta}:${startTime}`)
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
      "robustness.lipschitz1":   lipschitz1,
      "robustness.lipschitz2":   lipschitz2,
      "robustness.delta":        delta,
      "robustness.epsilon1":     epsilon1,
      "robustness.epsilon2":     epsilon2,
      "robustness.composed_lipschitz": composedLipschitz,
    },
  };

  return { span, epsilon2, lambdaScore };
}
