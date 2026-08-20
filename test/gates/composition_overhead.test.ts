/**
 * composition_overhead.test.ts
 *
 * Vitest tests for the Lutar.Composition.Overhead.composition_overhead_bound gate.
 *
 * Tests:
 *   1. 1000-input random test — verifies totalOverhead ≤ N*C inequality holds
 *   2. Edge cases: empty pipeline, singleton, large N
 *   3. Pipeline append tests
 *   4. Receipt emission with mock signer
 *
 * Lean commit: c4d13795689601324fce0236351bfe0ade990a43
 */

import { describe, it, expect } from "vitest";
import {
  totalOverhead,
  checkCompositionOverheadBound,
  appendPipelines,
  emitCompositionOverheadReceipt,
  compositionOverheadGate,
  type CostSystem,
  type BoundedPipeline,
  type Signer,
} from "../../src/gates/composition_overhead";

// ---------------------------------------------------------------------------
// Seeded LCG
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
// 1. 1000-input random overhead bound test
// ---------------------------------------------------------------------------

describe("composition_overhead: 1000-input random bound test", () => {
  it("totalOverhead ≤ N * C always holds when all costs ≤ C", () => {
    const rand = seedRandom(0xabcdef01);
    let violations = 0;

    for (let i = 0; i < 1000; i++) {
      const cap = Math.ceil(rand() * 100) + 1; // cap in [1,101]
      const N = Math.ceil(rand() * 20) + 1;     // N in [1,21]
      const systems: CostSystem[] = Array.from({ length: N }, () => ({
        cost: Math.ceil(rand() * cap), // cost in [1, cap]
      }));

      const total = totalOverhead(systems);
      const bound = N * cap;
      if (total > bound) violations++;
    }

    expect(violations).toBe(0);
  });

  it("checkCompositionOverheadBound returns true for 1000 random valid pipelines", () => {
    const rand = seedRandom(0xbeef1234);
    let failures = 0;

    for (let i = 0; i < 1000; i++) {
      const cap = Math.ceil(rand() * 50) + 1;
      const N = Math.ceil(rand() * 15) + 1;
      const systems: CostSystem[] = Array.from({ length: N }, () => ({
        cost: Math.ceil(rand() * cap),
      }));
      const pipeline: BoundedPipeline = { systems, cap };
      if (!checkCompositionOverheadBound(pipeline)) failures++;
    }

    expect(failures).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 2. Edge cases
// ---------------------------------------------------------------------------

describe("composition_overhead: edge cases", () => {
  it("empty pipeline has totalOverhead = 0", () => {
    expect(totalOverhead([])).toBe(0);
  });

  it("singleton pipeline: overhead = cost", () => {
    const s: CostSystem = { cost: 7 };
    expect(totalOverhead([s])).toBe(7);
  });

  it("singleton pipeline bound: 7 ≤ 1 * 10", () => {
    const pipeline: BoundedPipeline = { systems: [{ cost: 7 }], cap: 10 };
    expect(checkCompositionOverheadBound(pipeline)).toBe(true);
  });

  it("pipeline where all costs = cap → bound is tight (N*C = N*C)", () => {
    const cap = 5;
    const N = 4;
    const systems: CostSystem[] = Array.from({ length: N }, () => ({ cost: cap }));
    expect(totalOverhead(systems)).toBe(N * cap);
    expect(checkCompositionOverheadBound({ systems, cap })).toBe(true);
  });

  it("returns false when a system cost exceeds cap", () => {
    const pipeline: BoundedPipeline = {
      systems: [{ cost: 5 }, { cost: 15 }],
      cap: 10,
    };
    expect(checkCompositionOverheadBound(pipeline)).toBe(false);
  });

  it("returns false when cap = 0", () => {
    const pipeline: BoundedPipeline = { systems: [{ cost: 1 }], cap: 0 };
    expect(checkCompositionOverheadBound(pipeline)).toBe(false);
  });

  it("large N (1000) all costs = 1, cap = 1 → bound tight", () => {
    const N = 1000;
    const systems: CostSystem[] = Array.from({ length: N }, () => ({ cost: 1 }));
    expect(totalOverhead(systems)).toBe(N);
    expect(checkCompositionOverheadBound({ systems, cap: 1 })).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 3. Pipeline append (BoundedPipeline.append)
// ---------------------------------------------------------------------------

describe("composition_overhead: pipeline append", () => {
  it("appending two pipelines with same cap is valid", () => {
    const p1: BoundedPipeline = { systems: [{ cost: 3 }, { cost: 2 }], cap: 5 };
    const p2: BoundedPipeline = { systems: [{ cost: 1 }, { cost: 4 }], cap: 5 };
    const merged = appendPipelines(p1, p2);
    expect(merged.systems.length).toBe(4);
    expect(merged.cap).toBe(5);
    expect(checkCompositionOverheadBound(merged)).toBe(true);
  });

  it("appending throws on cap mismatch", () => {
    const p1: BoundedPipeline = { systems: [{ cost: 3 }], cap: 5 };
    const p2: BoundedPipeline = { systems: [{ cost: 2 }], cap: 7 };
    expect(() => appendPipelines(p1, p2)).toThrow("cap mismatch");
  });

  it("overhead additivity: append preserves total overhead sum", () => {
    const p1: BoundedPipeline = { systems: [{ cost: 3 }, { cost: 2 }], cap: 10 };
    const p2: BoundedPipeline = { systems: [{ cost: 1 }, { cost: 4 }], cap: 10 };
    const merged = appendPipelines(p1, p2);
    expect(totalOverhead(merged.systems)).toBe(
      totalOverhead(p1.systems) + totalOverhead(p2.systems)
    );
  });
});

// ---------------------------------------------------------------------------
// 4. Receipt emission
// ---------------------------------------------------------------------------

describe("composition_overhead: DSSE receipt emission", () => {
  it("emits receipt with correct theorem and commit SHA", () => {
    const pipeline: BoundedPipeline = {
      systems: [{ cost: 3 }, { cost: 2 }],
      cap: 5,
    };
    const receipt = emitCompositionOverheadReceipt(pipeline, mockSigner);
    expect(receipt.theorem).toBe(
      "Lutar.Composition.Overhead.composition_overhead_bound"
    );
    expect(receipt.lean_commit_sha).toBe(
      "c4d13795689601324fce0236351bfe0ade990a43"
    );
    expect(receipt.output).toBe(true);
    expect(receipt.inputs_hash).toMatch(/^[0-9a-f]{64}$/);
    expect(receipt.sig).toContain("mock-sig::");
  });

  it("receipt output = false when bound violated", () => {
    const pipeline: BoundedPipeline = {
      systems: [{ cost: 20 }],
      cap: 5,
    };
    const receipt = emitCompositionOverheadReceipt(pipeline, mockSigner);
    expect(receipt.output).toBe(false);
  });

  it("gate returns boundHolds and receipt", () => {
    const pipeline: BoundedPipeline = { systems: [{ cost: 4 }], cap: 4 };
    const { boundHolds, receipt } = compositionOverheadGate(pipeline, mockSigner);
    expect(boundHolds).toBe(true);
    expect(receipt.output).toBe(true);
  });

  it("identical pipelines yield identical inputs_hash", () => {
    const p: BoundedPipeline = { systems: [{ cost: 2 }], cap: 5 };
    const r1 = emitCompositionOverheadReceipt(p, mockSigner);
    const r2 = emitCompositionOverheadReceipt(p, mockSigner);
    expect(r1.inputs_hash).toBe(r2.inputs_hash);
  });
});
