// SPDX-License-Identifier: Apache-2.0
// Tests: ouroboros/lambda-gate/knot-tag — v15 §10.2 knot-invariant tag.

import { describe, it, expect } from "vitest";
import type { Axes } from "@szl/ouroboros-types";
import {
  knotInvariantTag,
  evaluateAxesWithKnotTag,
  computeLambdaWithKnotTag,
} from "./knot-tag.js";

const PASSING_AXES: Axes = {
  moralGrounding:       0.96,
  measurabilityHonesty: 0.95,
  epistemicHumility:    0.92,
  harmAvoidance:        0.91,
  logicalCoherence:     0.93,
  citationIntegrity:    0.90,
  noveltyContribution:  0.91,
  reproducibility:      0.92,
  stakeholderAlignment: 0.90,
};

const FAILING_AXES: Axes = {
  ...PASSING_AXES,
  moralGrounding: 0.50, // fails CRITICAL threshold
};

describe("knotInvariantTag — deterministic 16-hex tag", () => {
  it("is deterministic on identical inputs", () => {
    const t1 = knotInvariantTag(PASSING_AXES, 0.93);
    const t2 = knotInvariantTag(PASSING_AXES, 0.93);
    expect(t1).toBe(t2);
    expect(t1).toHaveLength(16);
  });

  it("changes when a per-axis pass-bit flips", () => {
    const tPass = knotInvariantTag(PASSING_AXES, 0.93);
    const tFail = knotInvariantTag(FAILING_AXES, 0.85);
    expect(tPass).not.toBe(tFail);
  });

  it("changes when the Λ centi-bucket changes (identical skeleton)", () => {
    const t1 = knotInvariantTag(PASSING_AXES, 0.92);
    const t2 = knotInvariantTag(PASSING_AXES, 0.94);
    expect(t1).not.toBe(t2);
  });

  it("is equal within the same Λ centi-bucket (identical skeleton)", () => {
    // 0.921 and 0.929 both bucket to 0.92.
    const t1 = knotInvariantTag(PASSING_AXES, 0.921);
    const t2 = knotInvariantTag(PASSING_AXES, 0.929);
    expect(t1).toBe(t2);
  });
});

describe("evaluateAxesWithKnotTag — preserves gate verdict", () => {
  it("attaches a tag while leaving pass/fail untouched", () => {
    const ev = evaluateAxesWithKnotTag(PASSING_AXES);
    expect(ev.pass).toBe(true);
    expect(typeof ev.knotTag).toBe("string");
    expect(ev.knotTag).toHaveLength(16);

    const ev2 = evaluateAxesWithKnotTag(FAILING_AXES);
    expect(ev2.pass).toBe(false);
    expect(ev2.reasons.length).toBeGreaterThan(0);
  });
});

describe("Audit-Reidemeister R2 smoke test", () => {
  it("identical axes + identical Λ → identical tag", () => {
    const a = computeLambdaWithKnotTag(PASSING_AXES);
    const b = computeLambdaWithKnotTag(PASSING_AXES);
    expect(a.knotTag).toBe(b.knotTag);
    expect(a.lambda).toBe(b.lambda);
  });
});
