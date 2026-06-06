/**
 * Binding-drift guard — dpi_soundness.ts
 *
 * Strike 1 (Watunakuy): these tests assert that the @lean_theorem annotation
 * in dpi_soundness.ts cites the CORRECT real theorem name
 * "dpi_receipt_chain_entropy_bound" (not the non-existent "th6_dpi_soundness"),
 * and that @lean_status is not falsely GREEN while a sorry is present.
 *
 * PhD-Math finding F5 (HIGH, 2026-05-31): the prior annotation cited
 * "Lutar.DPI.TH6_DPISoundness.th6_dpi_soundness" which does not exist.
 * The real theorem at line 105 of TH6_DPI_Soundness.lean is
 * "dpi_receipt_chain_entropy_bound", which carries one tracked sorry
 * (log-sum / Jensen inequality, Cover-Thomas Thm 2.8.1 route documented).
 *
 * These tests will FAIL if someone re-introduces the false annotation or
 * falsely restores GREEN before the sorry is discharged.
 *
 * Lean corpus reference: 749 declarations / 14 unique axioms / 163 sorries
 * @ c7c0ba17 (canonical HEAD 2026-05-31).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import * as fs from "fs";
import * as path from "path";
import { describe, it, expect } from "vitest";
import {
  th6DpiSoundnessCheck,
  assertDpiSoundness,
  shannonEntropyFromCounts,
  type PipelineStage,
} from "../src/pipeline/dpi_soundness";

// ---------------------------------------------------------------------------
// Helpers: read source annotation
// ---------------------------------------------------------------------------

const SRC_FILE = path.resolve(__dirname, "../src/pipeline/dpi_soundness.ts");

function readAnnotations(): { theorem: string; status: string } {
  const src = fs.readFileSync(SRC_FILE, "utf-8");
  const theoremMatch = src.match(/@lean_theorem\s+(\S+)/);
  const statusMatch = src.match(/@lean_status\s+(\S+)/);
  return {
    theorem: theoremMatch?.[1] ?? "",
    status: statusMatch?.[1] ?? "",
  };
}

// ---------------------------------------------------------------------------
// Strike 1 — Binding annotation integrity tests
// ---------------------------------------------------------------------------

describe("lean_binding_drift — dpi_soundness.ts (PhD-Math F5)", () => {
  it("@lean_theorem must NOT cite the non-existent 'th6_dpi_soundness'", () => {
    const { theorem } = readAnnotations();
    expect(theorem).not.toContain("th6_dpi_soundness");
    // Rationale: this identifier does not exist in TH6_DPI_Soundness.lean at c7c0ba17.
    // The real theorem is dpi_receipt_chain_entropy_bound. PhD-Math Pass 1 Binding #4.
  });

  it("@lean_theorem must cite 'dpi_receipt_chain_entropy_bound' (the real theorem)", () => {
    const { theorem } = readAnnotations();
    // The real theorem at TH6_DPI_Soundness.lean:105 at c7c0ba17.
    // Accept either fully qualified or when alias is added.
    expect(theorem).toContain("dpi_receipt_chain_entropy_bound");
  });

  it("@lean_status must NOT be a bare 'GREEN' while the theorem has a sorry", () => {
    const { status } = readAnnotations();
    // The theorem dpi_receipt_chain_entropy_bound carries one tracked sorry
    // (log-sum / Jensen inequality via Mathlib convexity). GREEN = fake-green (§2).
    // Must be SORRY-TRACKED or UNVERIFIED until sorry is discharged.
    expect(status).not.toBe("GREEN");
  });

  it("receipt.lean_theorem must NOT cite the non-existent theorem name", () => {
    const stages: PipelineStage[] = [
      { name: "a", entropyBits: 5.0 },
      { name: "b", entropyBits: 3.0 },
    ];
    const result = th6DpiSoundnessCheck(stages);
    // The emitted DSSE receipt must not falsely claim the non-existent theorem.
    expect(result.receipt.lean_theorem).not.toContain("th6_dpi_soundness");
  });

  it("receipt.lean_theorem must cite the corrected real theorem name", () => {
    const stages: PipelineStage[] = [
      { name: "a", entropyBits: 5.0 },
      { name: "b", entropyBits: 3.0 },
    ];
    const result = th6DpiSoundnessCheck(stages);
    expect(result.receipt.lean_theorem).toContain("dpi_receipt_chain_entropy_bound");
  });
});

// ---------------------------------------------------------------------------
// Strike 1 — Behavioral correctness (regression guard)
// The DPI soundness check logic is correct TS regardless of Lean sorry status.
// ---------------------------------------------------------------------------

describe("th6DpiSoundnessCheck — behavioral regression (dpi_receipt_chain_entropy_bound)", () => {
  it("happy path: monotone-decreasing entropy => sound = true", () => {
    const stages: PipelineStage[] = [
      { name: "raw", entropyBits: 7.5 },
      { name: "filtered", entropyBits: 5.0 },
      { name: "encoded", entropyBits: 3.2 },
    ];
    const r = th6DpiSoundnessCheck(stages);
    expect(r.sound).toBe(true);
    expect(r.violation).toBeUndefined();
  });

  it("edge case: flat entropy (all equal) => sound = true (non-strict)", () => {
    const stages: PipelineStage[] = [
      { name: "s1", entropyBits: 4.0 },
      { name: "s2", entropyBits: 4.0 },
    ];
    expect(th6DpiSoundnessCheck(stages).sound).toBe(true);
  });

  it("failure path: entropy increase => sound = false, violation reported", () => {
    const stages: PipelineStage[] = [
      { name: "ingest", entropyBits: 4.0 },
      { name: "augment", entropyBits: 6.0 }, // violation
    ];
    const r = th6DpiSoundnessCheck(stages);
    expect(r.sound).toBe(false);
    expect(r.violation?.fromStage).toBe("ingest");
    expect(r.violation?.toStage).toBe("augment");
  });
});

// ---------------------------------------------------------------------------
// Strike 4 — Property test: DPI monotonicity holds for N=100 random sequences
// For any monotone-decreasing sequence of length 3-10, sound must be true.
// For any sequence with at least one strict increase, sound must be false.
// ---------------------------------------------------------------------------

describe("th6DpiSoundnessCheck — property tests (N=100)", () => {
  function randomDecreasing(length: number): PipelineStage[] {
    let val = 10 + Math.random() * 10;
    return Array.from({ length }, (_, i) => {
      const stage = { name: `s${i}`, entropyBits: val };
      val -= Math.random() * 2; // strictly decrease
      return stage;
    });
  }

  it("100 random monotone-decreasing sequences: all sound = true", () => {
    for (let i = 0; i < 100; i++) {
      const stages = randomDecreasing(3 + Math.floor(Math.random() * 8));
      const r = th6DpiSoundnessCheck(stages);
      expect(r.sound).toBe(true);
    }
  });

  it("100 random sequences with a guaranteed increase: all sound = false", () => {
    for (let i = 0; i < 100; i++) {
      const base = randomDecreasing(3);
      // Inject a violation at position 1: set stage 1 entropy above stage 0
      base[1]!.entropyBits = base[0]!.entropyBits + 1 + Math.random();
      const r = th6DpiSoundnessCheck(base);
      expect(r.sound).toBe(false);
    }
  });
});
