// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Tests: ouroboros/lambda-gate — TH1 (gate verdict) + TH11 (Λ bound)
//
// Λ unification (fix/lambda-unification): the `lambda` field on EvalResult
// is now the weighted geometric mean (canonical, see lambda-spec.md).
// Tests that previously asserted Λ = min(axes) are rewritten to assert
// (a) lambda = geomean, (b) weakestAxis = min, (c) verdict unchanged.

import { describe, it, expect } from "vitest";
import {
  evaluateAxes,
  computeLambda,
  weakestAxis,
  gateTransit,
  getReceipt,
  verifyReceipt,
  LAMBDA_THRESHOLD,
  type EvalResult,
} from "./gate.js";
import type { Axes } from "@szl/ouroboros-types";

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

const VALID_HASH = "b".repeat(64);
const FIXED_TS = "2026-05-16T00:00:00.000Z";
const makeRaw = (axes: Axes = PASSING_AXES, lambda = 0.92, ts: string = FIXED_TS) => ({
  hash:        VALID_HASH,
  timestamp:   ts,
  lambda,
  axes,
  payloadRef:  "ipfs://test",
  doctrineVer: "6",
});

describe("computeLambda — weighted geometric mean (canonical)", () => {
  it("returns the geomean of 9 equal axes", () => {
    const allNines: Axes = Object.fromEntries(
      Object.keys(PASSING_AXES).map((k) => [k, 0.9]),
    ) as Axes;
    // geomean(0.9, 0.9, ..., 0.9) = 0.9
    expect(computeLambda(allNines)).toBeCloseTo(0.9, 10);
  });

  it("matches the closed-form geomean for mixed inputs", () => {
    const v = { ...PASSING_AXES, citationIntegrity: 0.50 } as Axes;
    const vals = Object.values(v) as number[];
    const expected = Math.exp(vals.reduce((s, x) => s + Math.log(x), 0) / vals.length);
    expect(computeLambda(v)).toBeCloseTo(expected, 10);
  });

  it("returns 0 if any axis is 0", () => {
    const v = { ...PASSING_AXES, moralGrounding: 0 } as Axes;
    expect(computeLambda(v)).toBe(0);
  });

  it("returns 0 for non-finite or negative inputs", () => {
    const v = { ...PASSING_AXES, moralGrounding: NaN } as unknown as Axes;
    expect(computeLambda(v)).toBe(0);
    const v2 = { ...PASSING_AXES, moralGrounding: -0.1 } as unknown as Axes;
    expect(computeLambda(v2)).toBe(0);
  });

  it("satisfies min ≤ Λ ≤ max (TH11 bound)", () => {
    const v: Axes = { ...PASSING_AXES, citationIntegrity: 0.50 };
    const vals = Object.values(v) as number[];
    const Λ = computeLambda(v);
    expect(Λ).toBeGreaterThanOrEqual(Math.min(...vals) - 1e-12);
    expect(Λ).toBeLessThanOrEqual(Math.max(...vals) + 1e-12);
  });
});

describe("weakestAxis — diagnostic helper", () => {
  it("returns the MIN axis value (formerly mislabelled as Λ)", () => {
    const v: Axes = { ...PASSING_AXES, citationIntegrity: 0.50 };
    expect(weakestAxis(v)).toBeCloseTo(0.50);
  });
  it("is in general less than or equal to the geomean Λ", () => {
    const v: Axes = { ...PASSING_AXES, citationIntegrity: 0.50 };
    expect(weakestAxis(v)).toBeLessThanOrEqual(computeLambda(v) + 1e-12);
  });
});

describe("evaluateAxes — passing", () => {
  it("passes when all axes meet thresholds", () => {
    const result: EvalResult = evaluateAxes(PASSING_AXES);
    expect(result.pass).toBe(true);
    expect(result.reasons).toHaveLength(0);
    expect(result.lambda).toBeGreaterThanOrEqual(LAMBDA_THRESHOLD);
    // weakest is also reported and is ≤ lambda
    expect(result.weakestAxis).toBeLessThanOrEqual(result.lambda + 1e-12);
  });
});

describe("evaluateAxes — failing (verdict semantics preserved)", () => {
  it("fails when moralGrounding < 0.95 (critical axis)", () => {
    const axes = { ...PASSING_AXES, moralGrounding: 0.93 };
    const result = evaluateAxes(axes);
    expect(result.pass).toBe(false);
    expect(result.reasons.some((r) => r.includes("moralGrounding"))).toBe(true);
  });

  it("fails when measurabilityHonesty < 0.95 (critical axis)", () => {
    const axes = { ...PASSING_AXES, measurabilityHonesty: 0.94 };
    const result = evaluateAxes(axes);
    expect(result.pass).toBe(false);
  });

  it("fails when any non-critical axis < 0.90", () => {
    const axes = { ...PASSING_AXES, epistemicHumility: 0.88 };
    const result = evaluateAxes(axes);
    expect(result.pass).toBe(false);
  });

  it("reports multiple failures simultaneously", () => {
    const axes: Axes = Object.fromEntries(
      Object.keys(PASSING_AXES).map((k) => [k, 0.80]),
    ) as Axes;
    const result = evaluateAxes(axes);
    expect(result.pass).toBe(false);
    expect(result.reasons.length).toBeGreaterThan(2);
  });
});

describe("gateTransit + store + verifyReceipt", () => {
  it("stores receipt when pass=true", () => {
    const result = gateTransit(makeRaw());
    expect(result.stored).toBe(true);
    expect(getReceipt(VALID_HASH)).toBeDefined();
  });

  it("does not store receipt when pass=false", () => {
    const failAxes = { ...PASSING_AXES, moralGrounding: 0.50 };
    const result = gateTransit(makeRaw(failAxes, 0.50));
    expect(result.stored).toBe(false);
  });

  it("verifyReceipt returns found+pass for stored receipt", () => {
    gateTransit(makeRaw());
    const v = verifyReceipt(VALID_HASH);
    expect(v.found).toBe(true);
    expect(v.pass).toBe(true);
  });

  it("verifyReceipt returns found=false for unknown hash", () => {
    const v = verifyReceipt("f".repeat(64));
    expect(v.found).toBe(false);
  });
});
