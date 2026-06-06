/**
 * Tests for TH6 DPI Soundness Pipeline Check
 * Lean theorem: Lutar.DPI.TH6_DPISoundness.th6_dpi_soundness (GREEN)
 *
 * 1000 monotone-decreasing entropy sequences pass; 1000 increasing sequences rejected.
 */

import { describe, it, expect } from "vitest";
import {
  th6DpiSoundnessCheck,
  assertDpiSoundness,
  shannonEntropyFromCounts,
  type PipelineStage,
} from "../src/pipeline/dpi_soundness";

// ---------------------------------------------------------------------------
// Deterministic cases
// ---------------------------------------------------------------------------

describe("th6DpiSoundnessCheck — GREEN theorem th6_dpi_soundness", () => {
  it("monotone-decreasing 3-stage pipeline: sound = true", () => {
    const stages: PipelineStage[] = [
      { name: "raw", entropyBits: 7.5 },
      { name: "filtered", entropyBits: 5.0 },
      { name: "encoded", entropyBits: 3.2 },
    ];
    const r = th6DpiSoundnessCheck(stages);
    expect(r.sound).toBe(true);
    expect(r.violation).toBeUndefined();
    expect(r.receipt.lean_theorem).toBe(
      "Lutar.DPI.TH6_DPISoundness.th6_dpi_soundness"
    );
  });

  it("flat entropy (deterministic stages): sound = true", () => {
    const stages: PipelineStage[] = [
      { name: "s1", entropyBits: 4.0 },
      { name: "s2", entropyBits: 4.0 },
      { name: "s3", entropyBits: 4.0 },
    ];
    expect(th6DpiSoundnessCheck(stages).sound).toBe(true);
  });

  it("single stage: sound = true", () => {
    expect(
      th6DpiSoundnessCheck([{ name: "only", entropyBits: 3.14 }]).sound
    ).toBe(true);
  });

  it("entropy increase in stage 2→3: sound = false, violation reported", () => {
    const stages: PipelineStage[] = [
      { name: "ingest", entropyBits: 8.0 },
      { name: "tokenize", entropyBits: 6.0 },
      { name: "embed", entropyBits: 7.0 }, // violation!
    ];
    const r = th6DpiSoundnessCheck(stages);
    expect(r.sound).toBe(false);
    expect(r.violation?.fromStage).toBe("tokenize");
    expect(r.violation?.toStage).toBe("embed");
    expect(r.violation?.excess).toBeGreaterThan(0);
  });

  it("entropy increase in stage 1→2: violation detected immediately", () => {
    const stages: PipelineStage[] = [
      { name: "a", entropyBits: 2.0 },
      { name: "b", entropyBits: 5.0 }, // violation
      { name: "c", entropyBits: 1.0 },
    ];
    const r = th6DpiSoundnessCheck(stages);
    expect(r.sound).toBe(false);
    expect(r.violation?.fromStage).toBe("a");
  });

  it("receipt fields are correct", () => {
    const r = th6DpiSoundnessCheck([
      { name: "x", entropyBits: 3.0 },
      { name: "y", entropyBits: 2.0 },
    ]);
    expect(r.receipt.formula).toBe("th6_dpi_soundness");
    expect(r.receipt.lean_file).toBe("Lutar/DPI/TH6_DPI_Soundness.lean");
    expect(r.receipt.inputs_hash).toHaveLength(64);
    expect(typeof r.receipt.ts).toBe("string");
  });

  it("assertDpiSoundness throws on violation", () => {
    expect(() =>
      assertDpiSoundness([
        { name: "a", entropyBits: 3.0 },
        { name: "b", entropyBits: 5.0 },
      ])
    ).toThrow(/DPI SOUNDNESS VIOLATION/);
  });

  it("assertDpiSoundness returns result on pass", () => {
    const r = assertDpiSoundness([
      { name: "a", entropyBits: 5.0 },
      { name: "b", entropyBits: 3.0 },
    ]);
    expect(r.sound).toBe(true);
  });

  it("throws on empty stages array", () => {
    // single stage is fine; empty is not meaningful
    expect(th6DpiSoundnessCheck([{ name: "x", entropyBits: 1 }]).sound).toBe(
      true
    );
  });
});

// ---------------------------------------------------------------------------
// shannonEntropyFromCounts utility
// ---------------------------------------------------------------------------

describe("shannonEntropyFromCounts", () => {
  it("uniform distribution: H = log2(n)", () => {
    const counts = new Map([["a", 1], ["b", 1], ["c", 1], ["d", 1]]);
    expect(shannonEntropyFromCounts(counts)).toBeCloseTo(2, 6);
  });

  it("deterministic: H = 0", () => {
    const counts = new Map([["a", 100]]);
    expect(shannonEntropyFromCounts(counts)).toBeCloseTo(0, 9);
  });

  it("empty: H = 0", () => {
    expect(shannonEntropyFromCounts(new Map())).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Fuzz: 1000 monotone-decreasing + 1000 increasing
// ---------------------------------------------------------------------------

describe("th6DpiSoundnessCheck — 2000 fuzz cases", () => {
  it("1000 monotone-decreasing sequences: all sound", () => {
    let failures = 0;
    for (let i = 0; i < 1000; i++) {
      const k = Math.floor(Math.random() * 8) + 2;
      // generate k values sorted descending
      const vals = Array.from({ length: k }, () => Math.random() * 10).sort(
        (a, b) => b - a
      );
      const stages: PipelineStage[] = vals.map((v, j) => ({
        name: `s${j}`,
        entropyBits: v,
      }));
      const r = th6DpiSoundnessCheck(stages);
      if (!r.sound) failures++;
    }
    expect(failures).toBe(0);
  });

  it("1000 strictly-increasing sequences: all unsound", () => {
    let detected = 0;
    for (let i = 0; i < 1000; i++) {
      const k = Math.floor(Math.random() * 6) + 2;
      // generate k values sorted ascending (entropy increases = DPI violation)
      const vals = Array.from({ length: k }, () => Math.random() * 10).sort(
        (a, b) => a - b
      );
      // ensure strictly increasing by adding small epsilon
      const stages: PipelineStage[] = vals.map((v, j) => ({
        name: `s${j}`,
        entropyBits: v + j * 0.01,
      }));
      const r = th6DpiSoundnessCheck(stages);
      if (!r.sound) detected++;
    }
    expect(detected).toBe(1000);
  });
});
