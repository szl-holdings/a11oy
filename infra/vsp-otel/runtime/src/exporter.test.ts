// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Tests: vsp-otel exporter — VSP

import { describe, it, expect, vi } from "vitest";
import {
  axesFromSpan,
  spanHash,
  signSpan,
  exportSpans,
  injectAnchorFormula,
  type OtelSpan,
  type AnchorFormulaDescriptor,
} from "./exporter.js";

function makeSpan(
  overrides: Partial<OtelSpan> = {},
  axisOverrides: Record<string, number> = {},
): OtelSpan {
  const base: Record<string, number> = {
    "lambda.moralGrounding":       0.96,
    "lambda.measurabilityHonesty": 0.96,
    "lambda.epistemicHumility":    0.92,
    "lambda.harmAvoidance":        0.91,
    "lambda.logicalCoherence":     0.93,
    "lambda.citationIntegrity":    0.91,
    "lambda.noveltyContribution":  0.91,
    "lambda.reproducibility":      0.92,
    "lambda.stakeholderAlignment": 0.91,
    ...axisOverrides,
  };
  return {
    spanId:    "span-001",
    traceId:   "trace-abc",
    name:      "test-operation",
    startTime: Date.now() - 100,
    endTime:   Date.now(),
    attributes: base,
    status:    "OK",
    ...overrides,
  };
}

/**
 * Synthetic anchor descriptor — labeled synthetic: true per Doctrine v6.
 *
 * Uses Lutar.Calibration.FalsePosition.false_position_correct, which is a
 * verified non-sorry theorem on lutar-lean main (confirmed 2026-05-30).
 * The formula_id slug "false_position" is one of the five canonical anchor
 * formulas in Doctrine v6.
 */
const SYNTHETIC_ANCHOR: AnchorFormulaDescriptor = {
  formula_id:       "false_position",
  lean_theorem_ref: "Lutar.Calibration.FalsePosition.false_position_correct",
  lean_commit_sha:  "c4d13795689601324fce0236351bfe0ade990a43", // lutar-lean main HEAD 2026-05-30
};

/**
 * Madhava-bound anchor descriptor — referenced by L7 witnessed forecasting.
 * Theorem confirmed to exist at Lutar/PACBayes/MadhavaBound.lean on main.
 */
const MADHAVA_ANCHOR: AnchorFormulaDescriptor = {
  formula_id:       "madhava_bound",
  lean_theorem_ref: "Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound",
  lean_commit_sha:  "c4d13795689601324fce0236351bfe0ade990a43",
};

describe("axesFromSpan", () => {
  it("reads axis scores from span attributes", () => {
    const axes = axesFromSpan(makeSpan());
    expect(axes.moralGrounding).toBe(0.96);
    expect(axes.measurabilityHonesty).toBe(0.96);
  });

  it("defaults to 0.90 for missing axes", () => {
    const span = makeSpan({}, {});
    // Remove one axis
    const { attributes } = span;
    delete (attributes as Record<string, unknown>)["lambda.epistemicHumility"];
    const axes = axesFromSpan({ ...span, attributes });
    expect(axes.epistemicHumility).toBe(0.90);
  });

  it("clamps axis values to [0, 1]", () => {
    const span = makeSpan({}, { "lambda.moralGrounding": 2.0 });
    const axes = axesFromSpan(span);
    expect(axes.moralGrounding).toBe(1.0);
  });
});

describe("spanHash", () => {
  it("returns a 64-char hex string", () => {
    expect(spanHash(makeSpan())).toHaveLength(64);
  });

  it("is deterministic for same span", () => {
    const span = makeSpan();
    expect(spanHash(span)).toBe(spanHash(span));
  });

  it("differs for different spans", () => {
    const s1 = makeSpan({ spanId: "span-001" });
    const s2 = makeSpan({ spanId: "span-002" });
    expect(spanHash(s1)).not.toBe(spanHash(s2));
  });
});

describe("injectAnchorFormula", () => {
  it("injects szl.anchor_formula.id, szl.lean_theorem_ref, szl.lean_commit_sha", () => {
    const span = makeSpan({ spanId: "anchor-inject-001" });
    injectAnchorFormula(span, SYNTHETIC_ANCHOR);

    expect(span.attributes["szl.anchor_formula.id"]).toBe("false_position");
    expect(span.attributes["szl.lean_theorem_ref"]).toBe(
      "Lutar.Calibration.FalsePosition.false_position_correct",
    );
    expect(span.attributes["szl.lean_commit_sha"]).toBe(
      "c4d13795689601324fce0236351bfe0ade990a43",
    );
  });

  it("returns the same attributes object reference", () => {
    const span = makeSpan({ spanId: "anchor-inject-002" });
    const returned = injectAnchorFormula(span, SYNTHETIC_ANCHOR);
    expect(returned).toBe(span.attributes);
  });

  it("does not overwrite existing non-anchor attributes", () => {
    const span = makeSpan({ spanId: "anchor-inject-003" });
    span.attributes["custom.key"] = "custom-value";
    injectAnchorFormula(span, SYNTHETIC_ANCHOR);
    expect(span.attributes["custom.key"]).toBe("custom-value");
  });

  it("accepts the madhava_bound anchor formula slug", () => {
    const span = makeSpan({ spanId: "madhava-anchor-001" });
    injectAnchorFormula(span, MADHAVA_ANCHOR);
    expect(span.attributes["szl.anchor_formula.id"]).toBe("madhava_bound");
    expect(span.attributes["szl.lean_theorem_ref"]).toBe(
      "Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound",
    );
  });

  it("lean_theorem_ref is non-empty string", () => {
    const span = makeSpan({ spanId: "anchor-inject-004" });
    injectAnchorFormula(span, SYNTHETIC_ANCHOR);
    const ref = span.attributes["szl.lean_theorem_ref"];
    expect(typeof ref).toBe("string");
    expect((ref as string).length).toBeGreaterThan(0);
  });

  it("formula_id contains no spaces (slug format)", () => {
    const span = makeSpan({ spanId: "anchor-inject-005" });
    injectAnchorFormula(span, SYNTHETIC_ANCHOR);
    const id = span.attributes["szl.anchor_formula.id"] as string;
    expect(id).not.toContain(" ");
  });
});

describe("signSpan", () => {
  it("returns a LambdaSignedSpan with pass=true for good axes", () => {
    const result = signSpan(makeSpan());
    expect(result.pass).toBe(true);
    expect(result.lambda).toBeGreaterThanOrEqual(0.90);
  });

  it("returns pass=false for failing axes", () => {
    const span = makeSpan({}, {
      "lambda.moralGrounding":       0.50,
      "lambda.measurabilityHonesty": 0.50,
    });
    const result = signSpan(span);
    expect(result.pass).toBe(false);
  });

  it("injects anchor formula attributes when anchor descriptor provided", () => {
    const span = makeSpan({ spanId: "sign-with-anchor-001" });
    const result = signSpan(span, SYNTHETIC_ANCHOR);

    // The attributes are injected into the span object in-place
    expect(result.span.attributes["szl.anchor_formula.id"]).toBe("false_position");
    expect(result.span.attributes["szl.lean_theorem_ref"]).toBe(
      "Lutar.Calibration.FalsePosition.false_position_correct",
    );
    expect(result.span.attributes["szl.lean_commit_sha"]).toBe(
      "c4d13795689601324fce0236351bfe0ade990a43",
    );
  });

  it("does NOT inject anchor attributes when no anchor provided (backward compat)", () => {
    const span = makeSpan({ spanId: "sign-no-anchor-001" });
    const result = signSpan(span);

    expect(result.span.attributes["szl.anchor_formula.id"]).toBeUndefined();
    expect(result.span.attributes["szl.lean_theorem_ref"]).toBeUndefined();
    expect(result.span.attributes["szl.lean_commit_sha"]).toBeUndefined();
  });

  it("span result still passes lambda gate when anchor is injected", () => {
    const span = makeSpan({ spanId: "sign-with-anchor-002" });
    const result = signSpan(span, MADHAVA_ANCHOR);
    expect(result.pass).toBe(true);
    expect(result.lambda).toBeGreaterThanOrEqual(0.85);
  });
});

describe("exportSpans", () => {
  it("batches multiple spans", () => {
    const spans = [makeSpan({ spanId: "s1" }), makeSpan({ spanId: "s2" })];
    const result = exportSpans(spans);
    expect(result.total).toBe(2);
    expect(result.signed).toHaveLength(2);
  });

  it("counts pass/fail correctly", () => {
    const good = makeSpan({ spanId: "good" });
    const bad  = makeSpan({ spanId: "bad" }, {
      "lambda.moralGrounding":       0.50,
      "lambda.measurabilityHonesty": 0.50,
    });
    const result = exportSpans([good, bad]);
    expect(result.passed).toBe(1);
    expect(result.failed).toBe(1);
  });
});
