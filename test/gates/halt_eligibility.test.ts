/**
 * halt_eligibility.test.ts
 *
 * Vitest tests for the Lutar.HUKLLA.HaltEligibility gate.
 *
 * Tests:
 *   1. 1000-input random parity test — verifies the monotonicity inequality holds
 *   2. Edge case: exactly at LAMBDA_FLOOR
 *   3. Edge case: just below LAMBDA_FLOOR
 *   4. Edge case: false receipts/rho flags
 *   5. Receipt emission with mock signer
 *
 * Lean commit: c4d13795689601324fce0236351bfe0ade990a43
 */

import { describe, it, expect } from "vitest";
import {
  isHaltEligible,
  emitHaltEligibilityReceipt,
  haltEligibilityGate,
  LAMBDA_FLOOR,
  type ExecutionTrace,
  type Signer,
} from "../../src/gates/halt_eligibility";

// ---------------------------------------------------------------------------
// Seeded pseudo-random (LCG — deterministic across runs)
// ---------------------------------------------------------------------------

function seedRandom(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0;
    return s / 0x100000000;
  };
}

// ---------------------------------------------------------------------------
// Mock signer
// ---------------------------------------------------------------------------

const mockSigner: Signer = (payload: string) =>
  `mock-sig::${Buffer.from(payload).slice(0, 16).toString("hex")}`;

// ---------------------------------------------------------------------------
// 1. 1000-input random parity / monotonicity test
// ---------------------------------------------------------------------------

describe("halt_eligibility: 1000-input random monotonicity test", () => {
  it("monotonicity holds: t1.lambda ≤ t2.lambda ∧ bools match ∧ t1 eligible → t2 eligible", () => {
    const rand = seedRandom(0xdeadbeef);
    let violations = 0;

    for (let i = 0; i < 1000; i++) {
      const score1 = rand();
      // t2 always has score ≥ score1 (monotonicity direction)
      const score2 = score1 + rand() * (1 - score1);
      const rc = rand() > 0.5;
      const rho = rand() > 0.5;

      const t1: ExecutionTrace = { lambdaScore: score1, receiptsClosed: rc, rhoClosure: rho };
      const t2: ExecutionTrace = { lambdaScore: score2, receiptsClosed: rc, rhoClosure: rho };

      const e1 = isHaltEligible(t1);
      const e2 = isHaltEligible(t2);

      // Lean theorem halt_eligibility_monotone: e1 = true → e2 = true
      if (e1 && !e2) violations++;
    }

    expect(violations).toBe(0);
  });

  it("score below LAMBDA_FLOOR always yields false (not_eligible_of_low_score)", () => {
    const rand = seedRandom(0xcafebabe);
    let violated = false;

    for (let i = 0; i < 1000; i++) {
      const score = rand() * (LAMBDA_FLOOR - 1e-10); // strictly below floor
      const trace: ExecutionTrace = {
        lambdaScore: score,
        receiptsClosed: true,
        rhoClosure: true,
      };
      if (isHaltEligible(trace)) violated = true;
    }

    expect(violated).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 2. Edge cases
// ---------------------------------------------------------------------------

describe("halt_eligibility: edge cases", () => {
  it("score exactly at LAMBDA_FLOOR with bools true → eligible", () => {
    const trace: ExecutionTrace = {
      lambdaScore: LAMBDA_FLOOR,
      receiptsClosed: true,
      rhoClosure: true,
    };
    expect(isHaltEligible(trace)).toBe(true);
  });

  it("score just below LAMBDA_FLOOR → not eligible", () => {
    const trace: ExecutionTrace = {
      lambdaScore: LAMBDA_FLOOR - Number.EPSILON,
      receiptsClosed: true,
      rhoClosure: true,
    };
    expect(isHaltEligible(trace)).toBe(false);
  });

  it("score above floor but receiptsClosed=false → not eligible", () => {
    const trace: ExecutionTrace = {
      lambdaScore: 0.95,
      receiptsClosed: false,
      rhoClosure: true,
    };
    expect(isHaltEligible(trace)).toBe(false);
  });

  it("score above floor but rhoClosure=false → not eligible", () => {
    const trace: ExecutionTrace = {
      lambdaScore: 0.95,
      receiptsClosed: true,
      rhoClosure: false,
    };
    expect(isHaltEligible(trace)).toBe(false);
  });

  it("score=1.0 all true → eligible", () => {
    const trace: ExecutionTrace = {
      lambdaScore: 1.0,
      receiptsClosed: true,
      rhoClosure: true,
    };
    expect(isHaltEligible(trace)).toBe(true);
  });

  it("score=0.0 → not eligible regardless of bools", () => {
    const trace: ExecutionTrace = {
      lambdaScore: 0.0,
      receiptsClosed: true,
      rhoClosure: true,
    };
    expect(isHaltEligible(trace)).toBe(false);
  });

  it("all false → not eligible", () => {
    const trace: ExecutionTrace = {
      lambdaScore: 0.0,
      receiptsClosed: false,
      rhoClosure: false,
    };
    expect(isHaltEligible(trace)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 3. Receipt emission test
// ---------------------------------------------------------------------------

describe("halt_eligibility: DSSE receipt emission", () => {
  it("emits receipt with correct theorem and commit SHA", () => {
    const trace: ExecutionTrace = { lambdaScore: 0.95, receiptsClosed: true, rhoClosure: true };
    const receipt = emitHaltEligibilityReceipt(trace, mockSigner);

    expect(receipt.theorem).toBe("Lutar.HUKLLA.HaltEligibility");
    expect(receipt.lean_commit_sha).toBe("c4d13795689601324fce0236351bfe0ade990a43");
    expect(receipt.output).toBe(true);
    expect(receipt.inputs_hash).toMatch(/^[0-9a-f]{64}$/);
    expect(receipt.sig).toContain("mock-sig::");
    expect(receipt.ts).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it("receipt output matches isHaltEligible for random traces", () => {
    const rand = seedRandom(0x12345678);

    for (let i = 0; i < 50; i++) {
      const trace: ExecutionTrace = {
        lambdaScore: rand(),
        receiptsClosed: rand() > 0.5,
        rhoClosure: rand() > 0.5,
      };
      const receipt = emitHaltEligibilityReceipt(trace, mockSigner);
      expect(receipt.output).toBe(isHaltEligible(trace));
    }
  });

  it("gate returns eligible and receipt fields consistently", () => {
    const trace: ExecutionTrace = { lambdaScore: 0.91, receiptsClosed: true, rhoClosure: true };
    const { eligible, receipt } = haltEligibilityGate(trace, mockSigner);
    expect(eligible).toBe(true);
    expect(receipt.output).toBe(true);
  });

  it("two identical traces yield identical inputs_hash", () => {
    const trace: ExecutionTrace = { lambdaScore: 0.95, receiptsClosed: true, rhoClosure: true };
    const r1 = emitHaltEligibilityReceipt(trace, mockSigner);
    const r2 = emitHaltEligibilityReceipt(trace, mockSigner);
    expect(r1.inputs_hash).toBe(r2.inputs_hash);
  });

  it("different traces yield different inputs_hash", () => {
    const t1: ExecutionTrace = { lambdaScore: 0.95, receiptsClosed: true, rhoClosure: true };
    const t2: ExecutionTrace = { lambdaScore: 0.80, receiptsClosed: true, rhoClosure: true };
    const r1 = emitHaltEligibilityReceipt(t1, mockSigner);
    const r2 = emitHaltEligibilityReceipt(t2, mockSigner);
    expect(r1.inputs_hash).not.toBe(r2.inputs_hash);
  });
});
