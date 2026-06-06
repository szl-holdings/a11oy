// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 4 — OpenTelemetry span wrapper for SummationInvariant
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/Khipu/SummationInvariant.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371

import { createHash } from "node:crypto";
import type { OtelSpan } from "../exporter.js";

const FORMULA_NAME    = "SummationInvariant";
const LEAN_FILE       = "Lutar/Khipu/SummationInvariant.lean";
const LEAN_COMMIT_SHA = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const LEAN_BLOB_SHA   = "a661e6b41d9f1f756f7746a83c3e5d9fbe11ba5c";

export interface KhipuOrgLeaf { decisionId: string; value: number; }
export interface KhipuOrg    { organId: string; decisions: KhipuOrgLeaf[]; }

/**
 * Khipu summation invariant check.
 * Lean: `khipuReceipt_checksum_invariant`
 * Lean file: Lutar/Khipu/SummationInvariant.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 */
function _summationInvariant(organs: KhipuOrg[], primaryCord: number):
  { pendantValues: number[]; computedTotal: number; invariantHolds: boolean; lambdaScore: number } {
  const pendantValues = organs.map((o) => o.decisions.reduce((s, d) => s + d.value, 0));
  const computedTotal = pendantValues.reduce((s, v) => s + v, 0);
  const invariantHolds = computedTotal === primaryCord;
  return { pendantValues, computedTotal, invariantHolds, lambdaScore: invariantHolds ? 1 : 0 };
}

export interface SummationInvariantSpanOpts {
  khipuId: string;
  organs: KhipuOrg[];
  primaryCord: number;
  traceId?: string;
}

export interface SummationInvariantSpanResult {
  span: OtelSpan;
  invariantHolds: boolean;
  computedTotal: number;
  lambdaScore: number;
}

/**
 * Invoke SummationInvariant and emit an OTLP-compatible OTel span with SZL formula attributes.
 */
export function summationInvariantSpan(opts: SummationInvariantSpanOpts): SummationInvariantSpanResult {
  const { khipuId, organs, primaryCord } = opts;

  const startTime = Date.now();
  const { pendantValues, computedTotal, invariantHolds, lambdaScore } =
    _summationInvariant(organs, primaryCord);
  const endTime = Date.now();

  const traceId = opts.traceId ?? createHash("sha256")
    .update(`${FORMULA_NAME}:${khipuId}:${primaryCord}:${startTime}`)
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
    status:    invariantHolds ? "OK" : "ERROR",
    attributes: {
      "szl.formula.name":        FORMULA_NAME,
      "szl.formula.lean_file":   LEAN_FILE,
      "szl.formula.commit_sha":  LEAN_COMMIT_SHA,
      "szl.formula.blob_sha":    LEAN_BLOB_SHA,
      "szl.formula.lambda_score": lambdaScore,
      "khipu.id":                khipuId,
      "khipu.organ_count":       organs.length,
      "khipu.primary_cord":      primaryCord,
      "khipu.computed_total":    computedTotal,
      "khipu.invariant_holds":   invariantHolds,
      "khipu.pendant_values":    JSON.stringify(pendantValues),
    },
  };

  return { span, invariantHolds, computedTotal, lambdaScore };
}
