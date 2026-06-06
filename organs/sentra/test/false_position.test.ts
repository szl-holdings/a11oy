/**
 * Tests for False-Position Threshold Calibration Gate
 * Lean theorem: Lutar.Calibration.false_position_correct (GREEN)
 *
 * Key property: for affine f, falsePositionAffine achieves f(x*) = T exactly (1 step).
 * 1000 random affine functions and targets tested.
 */

import { describe, it, expect } from "vitest";
import {
  falsePositionCalibrate,
  falsePositionAffine,
} from "../src/calibration/threshold_calibrator";

// ---------------------------------------------------------------------------
// Deterministic affine cases — exact theorem validation
// ---------------------------------------------------------------------------

describe("falsePositionAffine — GREEN theorem false_position_correct", () => {
  it("affine f(x) = 2x + 1, target = 5: x* = 2 exactly", () => {
    const r = falsePositionAffine(0, 1, 4, 9, 5);
    expect(r.threshold).toBeCloseTo(2, 9);
    expect(r.residual).toBeLessThan(1e-9);
    expect(r.iterations).toBe(1);
    expect(r.converged).toBe(true);
  });

  it("affine f(x) = -3x + 6, target = 0: x* = 2", () => {
    const r = falsePositionAffine(0, 6, 1, 3, 0);
    expect(r.threshold).toBeCloseTo(2, 9);
    expect(r.residual).toBeLessThan(1e-9);
  });

  it("affine f(x) = x, target = 7: x* = 7", () => {
    const r = falsePositionAffine(0, 0, 10, 10, 7);
    expect(r.threshold).toBeCloseTo(7, 9);
    expect(r.residual).toBeLessThan(1e-9);
  });

  it("receipt contains correct lean_theorem", () => {
    const r = falsePositionAffine(0, 0, 1, 1, 0.5);
    expect(r.receipt.lean_theorem).toBe("Lutar.Calibration.false_position_correct");
    expect(r.receipt.formula).toBe("false_position_correct");
    expect(r.receipt.lean_file).toBe("Lutar/Calibration/FalsePosition.lean");
    expect(r.receipt.inputs_hash).toHaveLength(64);
  });

  it("1000 random affine functions: f(x*) = target to 1e-9", () => {
    let failures = 0;
    for (let i = 0; i < 1000; i++) {
      const m = (Math.random() - 0.5) * 20; // slope ≠ 0
      const c = (Math.random() - 0.5) * 100;
      if (Math.abs(m) < 0.01) continue; // skip near-zero slope
      const x1 = (Math.random() - 0.5) * 50;
      const x2 = x1 + Math.random() * 10 + 1;
      const y1 = m * x1 + c;
      const y2 = m * x2 + c;
      const target = m * ((x1 + x2) / 2) + c + (Math.random() - 0.5) * 5;
      const r = falsePositionAffine(x1, y1, x2, y2, target);
      if (r.residual > 1e-7) failures++;
    }
    expect(failures).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// falsePositionCalibrate with general functions
// ---------------------------------------------------------------------------

describe("falsePositionCalibrate — general monotone functions", () => {
  it("cubic f(x) = x^3, target = 8: x* ≈ 2", () => {
    const r = falsePositionCalibrate(
      (x) => x ** 3,
      0,
      4,
      8,
      1e-9
    );
    expect(r.threshold).toBeCloseTo(2, 6);
    expect(r.residual).toBeLessThan(1e-8);
    expect(r.converged).toBe(true);
  });

  it("exp function f(x) = e^x, target = 1: x* ≈ 0", () => {
    const r = falsePositionCalibrate(
      (x) => Math.exp(x),
      -2,
      2,
      1,
      1e-9
    );
    expect(r.threshold).toBeCloseTo(0, 6);
    expect(r.converged).toBe(true);
  });

  it("linear (affine) via general API: 1 iteration", () => {
    const m = 3, c = -5;
    const r = falsePositionCalibrate(
      (x) => m * x + c,
      0,
      10,
      10, // m*x+c=10 → x=5
      1e-12
    );
    expect(r.threshold).toBeCloseTo(5, 9);
    expect(r.iterations).toBe(1);
  });

  it("throws on zero-slope bracket", () => {
    expect(() =>
      falsePositionCalibrate((x) => 5, 0, 10, 3) // constant function
    ).toThrow();
  });
});
