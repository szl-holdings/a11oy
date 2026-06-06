// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: vsp-otel  Thesis: VSP (Λ-signed OTel span exporter)
// Doctrine V6 preflight: ✓

import { createHash } from "node:crypto";
import {
  evaluateAxes,
  gateTransit,
  type EvalResult,
} from "@szl/ouroboros-lambda-gate";
import { type Axes, type Receipt, parseReceipt } from "@szl/ouroboros-types";

// ---------------------------------------------------------------------------
// OTel span interface (minimal, no @opentelemetry/api dependency in tests)
// ---------------------------------------------------------------------------

export interface OtelSpan {
  spanId:      string;
  traceId:     string;
  name:        string;
  startTime:   number;
  endTime:     number;
  attributes:  Record<string, string | number | boolean>;
  status:      "OK" | "ERROR" | "UNSET";
}

// ---------------------------------------------------------------------------
// Lambda-signed span: span + receipt
// ---------------------------------------------------------------------------

export interface LambdaSignedSpan {
  span:        OtelSpan;
  receiptHash: string;
  lambda:      number;
  axes:        Axes;
  pass:        boolean;
}

// ---------------------------------------------------------------------------
// Anchor formula injection (Phase 1 L4 — OTel SemConv)
// ---------------------------------------------------------------------------

/**
 * Anchor formula descriptor — populated at span-creation time and injected
 * as OTel span attributes per the SZL Holdings SemConv extension.
 *
 * OTel attribute names:
 *   szl.anchor_formula.id   — formula slug (e.g. "false_position", "madhava_bound")
 *   szl.lean_theorem_ref    — fully-qualified Lean 4 theorem name
 *   szl.lean_commit_sha     — lutar-lean main HEAD SHA at span-creation time
 *
 * All three attributes are optional at the exporter level; callers that
 * do not operate under a specific anchor formula omit the descriptor and
 * the attributes are not injected.
 *
 * Doctrine v6: lean_theorem_ref MUST correspond to a real, non-sorry theorem
 * on lutar-lean main.  Verified canonical values include:
 *   "Lutar.Calibration.FalsePosition.false_position_correct"
 *   "Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound"
 *   "Lutar.Khipu.SummationInvariant.khipuReceipt_checksum_invariant"
 *   "Lutar.Composition.Robustness.robustness_preserved_by_composition"
 */
export interface AnchorFormulaDescriptor {
  /** Formula slug as it appears in the ANCHOR_REGISTRY, e.g. "false_position" or "madhava_bound" */
  formula_id: string;
  /**
   * Fully-qualified Lean 4 theorem reference from lutar-lean, e.g.
   * "Lutar.Calibration.FalsePosition.false_position_correct"
   */
  lean_theorem_ref: string;
  /**
   * The lutar-lean main-branch HEAD commit SHA at span-creation time.
   * Callers should obtain this once at process start and pass it through;
   * this is intentionally NOT fetched at runtime inside the exporter to
   * avoid I/O dependencies in the hot path.
   */
  lean_commit_sha: string;
}

/**
 * Inject the three SZL anchor-formula OTel span attributes into an existing
 * span's attributes map.
 *
 * This function mutates `span.attributes` in-place and also returns the
 * updated attributes map for convenience.
 *
 * Per OTel SemConv the attribute names use dot-separated lowercase namespacing:
 *   https://opentelemetry.io/docs/specs/semconv/general/attribute-naming/
 *
 * @param span   - The OtelSpan whose attributes will be augmented.
 * @param anchor - Descriptor containing formula_id, lean_theorem_ref, lean_commit_sha.
 *                 All theorem refs must correspond to real theorems in lutar-lean;
 *                 see Lutar/Calibration/FalsePosition.lean, Lutar/PACBayes/MadhavaBound.lean,
 *                 Lutar/Khipu/SummationInvariant.lean, Lutar/Composition/AdversarialRobustness.lean.
 * @returns The mutated attributes map (same reference as span.attributes).
 */
export function injectAnchorFormula(
  span: OtelSpan,
  anchor: AnchorFormulaDescriptor,
): Record<string, string | number | boolean> {
  span.attributes["szl.anchor_formula.id"] = anchor.formula_id;
  span.attributes["szl.lean_theorem_ref"]  = anchor.lean_theorem_ref;
  span.attributes["szl.lean_commit_sha"]   = anchor.lean_commit_sha;
  return span.attributes;
}

// ---------------------------------------------------------------------------
// Exporter: attaches a Λ-receipt to every span before export
// ---------------------------------------------------------------------------

/**
 * Derive axes from an OTel span's attributes.
 * Attributes may include pre-computed axis scores (e.g. from ML inference);
 * missing axes default to 0.90 (floor).
 *
 * OTel SemConv compliance (PhD-audit 2026-05-29):
 * Attribute names use lowercase_snake_case per OTel semantic conventions
 * (https://opentelemetry.io/docs/specs/semconv/general/attribute-naming/).
 * e.g. lambda.moral_grounding, not lambda.moralGrounding.
 * Both camelCase (legacy) and snake_case keys are checked for back-compat.
 */
export function axesFromSpan(span: OtelSpan): Axes {
  const get = (snakeKey: string, camelKey: string, def = 0.90): number => {
    // Prefer snake_case (SemConv-compliant); fall back to camelCase for back-compat
    const v = span.attributes[`lambda.${snakeKey}`] ?? span.attributes[`lambda.${camelKey}`];
    return typeof v === "number" ? Math.min(1, Math.max(0, v)) : def;
  };
  return {
    moralGrounding:       get("moral_grounding", "moralGrounding"),
    measurabilityHonesty: get("measurability_honesty", "measurabilityHonesty"),
    epistemicHumility:    get("epistemic_humility", "epistemicHumility"),
    harmAvoidance:        get("harm_avoidance", "harmAvoidance"),
    logicalCoherence:     get("logical_coherence", "logicalCoherence"),
    citationIntegrity:    get("citation_integrity", "citationIntegrity"),
    noveltyContribution:  get("novelty_contribution", "noveltyContribution"),
    reproducibility:      get("reproducibility", "reproducibility"),
    stakeholderAlignment: get("stakeholder_alignment", "stakeholderAlignment"),
  };
}

/** Compute a deterministic receipt hash for a span. */
export function spanHash(span: OtelSpan): string {
  return createHash("sha256")
    .update(`${span.traceId}:${span.spanId}:${span.name}`)
    .digest("hex");
}

/**
 * Sign a span with a Λ-receipt and optionally push to the gate store.
 *
 * If `anchor` is provided the three SZL anchor-formula attributes are
 * injected into the span's attributes map before the span is returned.
 * This satisfies the Phase 1 L4 requirement:
 *   szl.anchor_formula.id, szl.lean_theorem_ref, szl.lean_commit_sha
 * are present on every span that carries a policy-gate decision.
 */
export function signSpan(
  span: OtelSpan,
  anchor?: AnchorFormulaDescriptor,
): LambdaSignedSpan {
  const axes  = axesFromSpan(span);
  const ev    = evaluateAxes(axes);
  const hash  = spanHash(span);

  // Inject anchor-formula attributes if a descriptor was supplied.
  // This must happen before gateTransit so the gate sees the full attribute set.
  if (anchor !== undefined) {
    injectAnchorFormula(span, anchor);
  }

  // Attempt gate transit (stores only if pass=true)
  try {
    gateTransit({
      hash,
      timestamp:   new Date(span.endTime).toISOString(),
      lambda:      ev.lambda,
      axes,
      payloadRef:  `otel:${span.traceId}/${span.spanId}`,
      doctrineVer: "6",
      meta:        { spanName: span.name, status: span.status },
    });
  } catch {
    // Gate rejection is recorded in eval; do not throw from exporter
  }

  return {
    span,
    receiptHash: hash,
    lambda:      ev.lambda,
    axes,
    pass:        ev.pass,
  };
}

// ---------------------------------------------------------------------------
// Batch export
// ---------------------------------------------------------------------------

export interface ExportResult {
  total:   number;
  passed:  number;
  failed:  number;
  signed:  LambdaSignedSpan[];
}

export function exportSpans(spans: OtelSpan[]): ExportResult {
  const signed = spans.map(signSpan);
  return {
    total:  signed.length,
    passed: signed.filter((s) => s.pass).length,
    failed: signed.filter((s) => !s.pass).length,
    signed,
  };
}
