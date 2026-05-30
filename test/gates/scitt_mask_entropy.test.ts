/**
 * scitt_mask_entropy.test.ts
 *
 * Vitest tests for the Lutar.DPI.SCITT.SCITTMaskEntropy gate.
 *
 * Tests:
 *   1. 1000-input random entropy bound test: H(mask(X)) ≤ H(X)
 *   2. Hash preservation edge cases
 *   3. Full-mask, empty-mask, partial-mask
 *   4. Receipt emission with mock signer
 *
 * Lean commit: c4d13795689601324fce0236351bfe0ade990a43
 */

import { describe, it, expect } from "vitest";
import {
  applyMask,
  shannonEntropy,
  maskedEntropy,
  verifySCITTMaskEntropyBound,
  verifyMaskRefinementMono,
  verifyHashPreservation,
  emitSCITTMaskEntropyReceipt,
  scittMaskEntropyGate,
  type SCITTStatement,
  type MaskSpec,
  type StmtDist,
  type Signer,
} from "../../src/gates/scitt_mask_entropy";

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

const mockSigner: Signer = (p: string) =>
  `mock-sig::${Buffer.from(p).slice(0, 16).toString("hex")}`;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeUniformDist(K: number): StmtDist {
  const statements: SCITTStatement[] = Array.from({ length: K }, (_, i) => ({
    fields: [i, i + 1, i + 2],
    hash: `hash-${i}`,
  }));
  const probs = Array(K).fill(1 / K);
  return { statements, probs };
}

function makeRandomDist(K: number, rand: () => number): StmtDist {
  // Generate unnormalised weights then normalise
  const weights = Array.from({ length: K }, () => rand());
  const total = weights.reduce((a, b) => a + b, 0);
  const probs = weights.map((w) => w / total);
  const statements: SCITTStatement[] = Array.from({ length: K }, (_, i) => ({
    fields: [i, i * 2],
    hash: `h-${i}`,
  }));
  return { statements, probs };
}

// ---------------------------------------------------------------------------
// 1. 1000-input random entropy bound test
// ---------------------------------------------------------------------------

describe("scitt_mask_entropy: 1000-input random entropy bound", () => {
  it("H(mask(X)) ≤ H(X) for 1000 random distributions and masks", () => {
    const rand = seedRandom(0x98765432);
    let violations = 0;

    for (let i = 0; i < 1000; i++) {
      const K = Math.floor(rand() * 8) + 2; // K in [2,9]
      const nFields = Math.floor(rand() * 4) + 1; // nFields in [1,4]
      const dist = makeRandomDist(K, rand);
      const mask: MaskSpec = {
        redacted: Array.from({ length: nFields }, () => rand() > 0.5),
      };

      if (!verifySCITTMaskEntropyBound(mask, dist)) violations++;
    }

    expect(violations).toBe(0);
  });

  it("mask refinement monotonicity holds for 1000 random pairs", () => {
    const rand = seedRandom(0x12345678);
    let violations = 0;

    for (let i = 0; i < 1000; i++) {
      const K = Math.floor(rand() * 6) + 2;
      const nFields = Math.floor(rand() * 4) + 1;
      const dist = makeRandomDist(K, rand);

      // mask1: random redaction
      const r1 = Array.from({ length: nFields }, () => rand() > 0.5);
      // mask2: superset — any field redacted in mask1 is also redacted in mask2
      const r2 = r1.map((b) => b || rand() > 0.7);

      const mask1: MaskSpec = { redacted: r1 };
      const mask2: MaskSpec = { redacted: r2 };

      if (!verifyMaskRefinementMono(mask1, mask2, dist)) violations++;
    }

    expect(violations).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 2. Hash preservation
// ---------------------------------------------------------------------------

describe("scitt_mask_entropy: hash preservation (scitt_mask_preserves_hash)", () => {
  it("applyMask preserves hash for all statements", () => {
    const rand = seedRandom(0xaabbccdD);

    for (let i = 0; i < 100; i++) {
      const nFields = Math.floor(rand() * 5) + 1;
      const stmt: SCITTStatement = {
        fields: Array.from({ length: nFields }, () => Math.floor(rand() * 10)),
        hash: `hash-${i}-${Math.floor(rand() * 100000)}`,
      };
      const mask: MaskSpec = {
        redacted: Array.from({ length: nFields }, () => rand() > 0.5),
      };
      const masked = applyMask(mask, stmt);
      expect(masked.hash).toBe(stmt.hash);
    }
  });

  it("verifyHashPreservation returns true for all statements in a dist", () => {
    const dist = makeUniformDist(5);
    const mask: MaskSpec = { redacted: [true, false, true] };
    expect(verifyHashPreservation(mask, dist.statements)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 3. Full-mask, empty-mask, partial-mask
// ---------------------------------------------------------------------------

describe("scitt_mask_entropy: mask variants", () => {
  const dist4 = makeUniformDist(4);
  const fullMask: MaskSpec = { redacted: [true, true, true] };
  const emptyMask: MaskSpec = { redacted: [false, false, false] };
  const partialMask: MaskSpec = { redacted: [true, false, false] };

  it("full mask entropy bound holds", () => {
    expect(verifySCITTMaskEntropyBound(fullMask, dist4)).toBe(true);
  });

  it("empty mask entropy equals original", () => {
    const hOrig = shannonEntropy(dist4.probs);
    const hMasked = maskedEntropy(emptyMask, dist4);
    expect(Math.abs(hMasked - hOrig)).toBeLessThan(1e-10);
  });

  it("partial mask entropy bound holds", () => {
    expect(verifySCITTMaskEntropyBound(partialMask, dist4)).toBe(true);
  });

  it("applyMask zeroes redacted fields", () => {
    const stmt: SCITTStatement = { fields: [3, 7, 11], hash: "h0" };
    const masked = applyMask(fullMask, stmt);
    expect(masked.fields).toEqual([0, 0, 0]);
    expect(masked.hash).toBe("h0");
  });

  it("applyMask leaves non-redacted fields unchanged", () => {
    const stmt: SCITTStatement = { fields: [3, 7, 11], hash: "h1" };
    const masked = applyMask(emptyMask, stmt);
    expect(masked.fields).toEqual([3, 7, 11]);
  });

  it("shannonEntropy of uniform 4-dist ≈ 2 bits", () => {
    const h = shannonEntropy(dist4.probs);
    expect(h).toBeCloseTo(2.0, 5);
  });

  it("shannonEntropy of [1] = 0 (certain distribution)", () => {
    expect(shannonEntropy([1])).toBeCloseTo(0, 10);
  });
});

// ---------------------------------------------------------------------------
// 4. Receipt emission
// ---------------------------------------------------------------------------

describe("scitt_mask_entropy: DSSE receipt emission", () => {
  const dist = makeUniformDist(4);
  const mask: MaskSpec = { redacted: [false, true, false] };

  it("emits receipt with correct theorem and commit SHA", () => {
    const receipt = emitSCITTMaskEntropyReceipt(mask, dist, mockSigner);
    expect(receipt.theorem).toBe("Lutar.DPI.SCITT.scitt_mask_entropy_bound");
    expect(receipt.lean_commit_sha).toBe("c4d13795689601324fce0236351bfe0ade990a43");
    expect(receipt.output).toBe(true);
    expect(receipt.inputs_hash).toMatch(/^[0-9a-f]{64}$/);
    expect(receipt.sig).toContain("mock-sig::");
  });

  it("gate returns entropyBoundHolds=true and entropies", () => {
    const result = scittMaskEntropyGate(mask, dist, mockSigner);
    expect(result.entropyBoundHolds).toBe(true);
    expect(result.originalEntropy).toBeCloseTo(2.0, 5);
    expect(result.maskedEntropy).toBeCloseTo(2.0, 5);
    expect(result.receipt.output).toBe(true);
  });

  it("inputs_hash is deterministic", () => {
    const r1 = emitSCITTMaskEntropyReceipt(mask, dist, mockSigner);
    const r2 = emitSCITTMaskEntropyReceipt(mask, dist, mockSigner);
    expect(r1.inputs_hash).toBe(r2.inputs_hash);
  });
});
