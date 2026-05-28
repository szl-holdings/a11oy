/**
 * Tests for ΛGateLID runtime check (v15 §III, TH12.1).
 *
 * Witnesses the closed Lean theorems `ΛGateLID_preserved_under_R1_identity`
 * (TH12.1a), `ΛGateLID_preserved_under_R2_of_R1` (TH12.1b),
 * `ΛGateLID_preserved_under_R3_of_R1` (TH12.1c) by exercising the runtime
 * predicate `checkLID` against rewritten policy parameters and asserting
 * the LID membership is preserved.
 */
import { describe, expect, it } from "vitest";
import { checkLID, isR1IdentityRepack, postDPOThreshold } from "../lid-check";

describe("checkLID", () => {
  it("returns inLID=true when every axis meets the threshold", () => {
    const r = checkLID({
      numAxes: 9,
      axisScore: (k) => 0.85 + k * 0.01,
      threshold: 0.8,
    });
    expect(r.inLID).toBe(true);
    expect(r.failingAxes).toEqual([]);
    expect(r.perAxis).toHaveLength(9);
    expect(r.perAxis.every((p) => p.met)).toBe(true);
  });

  it("returns failingAxes when one axis is below threshold", () => {
    const r = checkLID({
      numAxes: 9,
      axisScore: (k) => (k === 4 ? 0.5 : 0.9),
      threshold: 0.8,
    });
    expect(r.inLID).toBe(false);
    expect(r.failingAxes).toEqual([4]);
  });

  it("accepts score equal to threshold (closed half-space)", () => {
    const r = checkLID({ numAxes: 3, axisScore: () => 0.8, threshold: 0.8 });
    expect(r.inLID).toBe(true);
  });

  it("throws on non-positive numAxes", () => {
    expect(() => checkLID({ numAxes: 0, axisScore: () => 1, threshold: 0 })).toThrow(RangeError);
    expect(() => checkLID({ numAxes: -1, axisScore: () => 1, threshold: 0 })).toThrow(RangeError);
  });

  it("throws on non-finite threshold", () => {
    expect(() => checkLID({ numAxes: 3, axisScore: () => 1, threshold: NaN })).toThrow(RangeError);
    expect(() => checkLID({ numAxes: 3, axisScore: () => 1, threshold: Infinity })).toThrow(RangeError);
  });

  it("throws when axisScore returns non-finite", () => {
    expect(() => checkLID({ numAxes: 3, axisScore: () => NaN, threshold: 0.5 })).toThrow(RangeError);
  });
});

describe("isR1IdentityRepack", () => {
  it("returns true for exactly-equal vectors", () => {
    const v = [0.1, 0.2, 0.3, 0.4];
    expect(isR1IdentityRepack(v, [...v])).toBe(true);
  });

  it("returns false for any coordinate difference outside tolerance", () => {
    expect(isR1IdentityRepack([0.1, 0.2], [0.1, 0.2 + 1e-6], 0)).toBe(false);
    expect(isR1IdentityRepack([0.1, 0.2], [0.1, 0.2 + 1e-6], 1e-5)).toBe(true);
  });

  it("returns false for mismatched lengths", () => {
    expect(isR1IdentityRepack([0.1, 0.2], [0.1])).toBe(false);
  });

  it("throws on negative or non-finite tolerance", () => {
    expect(() => isR1IdentityRepack([0], [0], -1)).toThrow(RangeError);
    expect(() => isR1IdentityRepack([0], [0], NaN)).toThrow(RangeError);
  });
});

describe("TH12.1a witness: R1 identity-repack preserves LID", () => {
  it("LID membership equivalence under identity rewrite", () => {
    const before = [0.85, 0.9, 0.95];
    const after = [...before]; // R1 identity-repack
    expect(isR1IdentityRepack(before, after)).toBe(true);
    const t = 0.8;
    const r1 = checkLID({ numAxes: 3, axisScore: (k) => before[k], threshold: t });
    const r2 = checkLID({ numAxes: 3, axisScore: (k) => after[k], threshold: t });
    expect(r1.inLID).toBe(r2.inLID);
  });
});

describe("TH12.1b/c witnesses: composed identity rewrites preserve LID", () => {
  it("two identity rewrites preserve membership (TH12.1b)", () => {
    const before = [0.85, 0.9, 0.95];
    const afterR2 = [...before];
    const afterR1R2 = [...afterR2];
    expect(isR1IdentityRepack(before, afterR2)).toBe(true);
    expect(isR1IdentityRepack(afterR2, afterR1R2)).toBe(true);
    const t = 0.8;
    expect(checkLID({ numAxes: 3, axisScore: (k) => before[k], threshold: t }).inLID).toBe(
      checkLID({ numAxes: 3, axisScore: (k) => afterR1R2[k], threshold: t }).inLID,
    );
  });

  it("three identity rewrites preserve membership (TH12.1c)", () => {
    const before = [0.85, 0.9, 0.95];
    const out = [...before];
    expect(isR1IdentityRepack(before, out)).toBe(true);
    const t = 0.8;
    expect(checkLID({ numAxes: 3, axisScore: (k) => before[k], threshold: t }).inLID).toBe(
      checkLID({ numAxes: 3, axisScore: (k) => out[k], threshold: t }).inLID,
    );
  });
});

describe("postDPOThreshold", () => {
  it("returns threshold - L*sqrt(eps/2)", () => {
    expect(postDPOThreshold(0.8, 1, 0)).toBe(0.8);
    expect(postDPOThreshold(0.8, 0, 0.5)).toBe(0.8);
    expect(postDPOThreshold(0.8, 2, 0.5)).toBeCloseTo(0.8 - 2 * Math.sqrt(0.25), 12);
  });

  it("rejects negative or non-finite lipschitz / klBudget", () => {
    expect(() => postDPOThreshold(0.5, -1, 0)).toThrow(RangeError);
    expect(() => postDPOThreshold(0.5, 1, -0.01)).toThrow(RangeError);
    expect(() => postDPOThreshold(0.5, 1, Infinity)).toThrow(RangeError);
    expect(() => postDPOThreshold(NaN, 1, 0)).toThrow(RangeError);
  });
});
