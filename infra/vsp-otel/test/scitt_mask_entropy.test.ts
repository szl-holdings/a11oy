/**
 * Tests for SCITT Mask Entropy Redaction Gate
 * Lean theorem: Lutar.DPI.SCITT.scitt_mask_entropy_bound (GREEN)
 *
 * All 1000+ random-input assertions verify H(masked) ≤ H(original).
 */

import { describe, it, expect } from "vitest";
import {
  scittMaskEntropyGate,
  scittMaskEntropyBatch,
  type ScittMaskResult,
} from "../src/redaction/scitt_mask_entropy";

// ---------------------------------------------------------------------------
// Deterministic cases
// ---------------------------------------------------------------------------

describe("scittMaskEntropyGate — GREEN theorem scitt_mask_entropy_bound", () => {
  it("masking all fields produces entropy ≤ original", () => {
    const orig = { a: "foo", b: "bar", c: "baz" };
    const masked = { a: null, b: null, c: null };
    const r = scittMaskEntropyGate(orig, masked);
    expect(r.maskedEntropy).toBeLessThanOrEqual(r.originalEntropy + 1e-9);
    expect(r.receipt.lean_theorem).toBe(
      "Lutar.DPI.SCITT.scitt_mask_entropy_bound"
    );
    expect(r.valid).toBe(true);
  });

  it("masking no fields: entropy equal to original", () => {
    const orig = { a: "x", b: "y", c: "z" };
    const masked = { a: "x", b: "y", c: "z" };
    const r = scittMaskEntropyGate(orig, masked);
    expect(Math.abs(r.maskedEntropy - r.originalEntropy)).toBeLessThan(1e-9);
    expect(r.valid).toBe(true);
  });

  it("single-value field: entropy = 0 before and after masking", () => {
    const orig = { ip: "1.2.3.4" };
    const masked = { ip: "1.2.3.4" };
    const r = scittMaskEntropyGate(orig, masked);
    expect(r.originalEntropy).toBeCloseTo(0, 9);
    expect(r.maskedEntropy).toBeCloseTo(0, 9);
  });

  it("uniform distribution: partial masking reduces entropy", () => {
    // 4 distinct values — H = 2 bits; mask 2 → they collapse, entropy drops
    const orig = { a: "w", b: "x", c: "y", d: "z" };
    const masked = { a: null, b: null, c: "y", d: "z" };
    const r = scittMaskEntropyGate(orig, masked);
    expect(r.maskedEntropy).toBeLessThanOrEqual(r.originalEntropy + 1e-9);
  });

  it("receipt has correct formula and file fields", () => {
    const r = scittMaskEntropyGate({ k: "v" }, { k: null });
    expect(r.receipt.formula).toBe("scitt_mask_entropy_bound");
    expect(r.receipt.lean_file).toBe("Lutar/DPI/SCITTMaskEntropy.lean");
    expect(typeof r.receipt.inputs_hash).toBe("string");
    expect(r.receipt.inputs_hash).toHaveLength(64); // sha256 hex
    expect(typeof r.receipt.ts).toBe("string");
  });

  it("throws on field set mismatch", () => {
    expect(() =>
      scittMaskEntropyGate({ a: "1", b: "2" }, { a: null } as any)
    ).toThrow(/field mismatch/);
  });
});

// ---------------------------------------------------------------------------
// Fuzz: 1000 random field sets
// ---------------------------------------------------------------------------

describe("scittMaskEntropyGate — 1000 random field sets (theorem fuzz)", () => {
  it("mask entropy ≤ original entropy for 1000 random records", () => {
    const VOCAB = ["alpha", "beta", "gamma", "delta", "epsilon"];
    let failures = 0;
    for (let i = 0; i < 1000; i++) {
      const n = Math.floor(Math.random() * 8) + 1;
      const orig = Object.fromEntries(
        Array.from({ length: n }, (_, k) => [
          `f${k}`,
          VOCAB[Math.floor(Math.random() * VOCAB.length)]!,
        ])
      );
      const masked = Object.fromEntries(
        Object.keys(orig).map((k) => [
          k,
          Math.random() > 0.5 ? null : orig[k]!,
        ])
      );
      const r = scittMaskEntropyGate(orig, masked);
      if (!r.valid) failures++;
    }
    expect(failures).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Batch API
// ---------------------------------------------------------------------------

describe("scittMaskEntropyBatch", () => {
  it("processes 500 pairs; all valid", () => {
    const pairs = Array.from({ length: 500 }, (_, i) => ({
      original: { id: String(i % 7), val: String(i % 3) },
      masked: { id: null, val: i % 2 === 0 ? null : String(i % 3) },
    }));
    const results = scittMaskEntropyBatch(pairs);
    expect(results).toHaveLength(500);
    for (const r of results) {
      expect(r.valid).toBe(true);
      expect(r.maskedEntropy).toBeLessThanOrEqual(r.originalEntropy + 1e-9);
    }
  });
});
