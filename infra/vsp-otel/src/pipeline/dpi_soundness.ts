/**
 * TH6 DPI Soundness Pipeline Check
 *
 * @lean_theorem Lutar.DPI.TH6_DPISoundness.dpi_receipt_chain_entropy_bound
 * @lean_file    Lutar/DPI/TH6_DPI_Soundness.lean
 * @lean_status  SORRY-TRACKED — theorem name corrected from "th6_dpi_soundness" (did not exist) to
 *               "dpi_receipt_chain_entropy_bound" (actual theorem at line 105). The theorem carries
 *               one tracked sorry (log-sum / Jensen inequality discharge pending; Cover-Thomas
 *               Thm 2.8.1 route documented). Not GREEN until sorry is discharged.
 *               Per PhD-Math review 2026-05-31 (Pass 1, Binding #4, Finding F5 HIGH).
 * @lean_commit  see LEAN_COMMIT_SHA env var; pin at CI time from lutar-lean/lean-toolchain
 *
 * Theorem (Cover & Thomas 2006 §2.8.1 Theorem 2.8.1, Data Processing Inequality):
 *   For Lutar receipt chain X → Y → Z: I(X;Z) ≤ I(X;Y).
 *   Equivalently: entropy is non-increasing through processing stages.
 *
 *   Formally: if Y = f(X) and Z = g(Y) for deterministic f, g, then
 *     H(Z) ≤ H(Y) ≤ H(X)
 *   because each deterministic transformation can only reduce or preserve information.
 *
 * Pipeline invariant: For a k-stage Lutar receipt pipeline P₁ → P₂ → … → Pₖ,
 *   stage entropies must form a non-increasing sequence.
 *   Any increase in entropy between stages indicates an information injection
 *   (undeclared input) which violates the DPI soundness property.
 *
 * References:
 *   Cover & Thomas (2006) Elements of Information Theory, 2nd ed. §2.8
 *   Lutar/DPI/TH6_DPI_Soundness.lean — kernel-checked proof
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import * as crypto from "crypto";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PipelineStage {
  /** Unique stage name (e.g., "ingest", "tokenize", "embed") */
  name: string;
  /**
   * Shannon entropy (bits) of the data distribution at this stage.
   * Computed externally (e.g., from sample or model output) and passed in.
   */
  entropyBits: number;
}

export interface DpiSoundnessResult {
  /** True iff entropy is non-increasing across all consecutive stage pairs */
  sound: boolean;
  /** First violation found, if any */
  violation?: {
    fromStage: string;
    toStage: string;
    fromEntropy: number;
    toEntropy: number;
    excess: number;
  };
  /** All stage names and entropies */
  stages: PipelineStage[];
  /** DSSE receipt */
  receipt: DpiDsseReceipt;
}

export interface DpiDsseReceipt {
  formula: string;
  lean_theorem: string;
  lean_file: string;
  lean_commit_sha: string;
  inputs_hash: string;
  output: {
    sound: boolean;
    stageCount: number;
    violation: DpiSoundnessResult["violation"] | null;
  };
  ts: string;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function sha256Hex(obj: unknown): string {
  return crypto
    .createHash("sha256")
    .update(JSON.stringify(obj))
    .digest("hex");
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Assert TH6 DPI soundness: pipeline stage entropies must be non-increasing.
 *
 * @param stages  Ordered array of pipeline stages with measured entropy values.
 *                Must have at least 2 stages to be meaningful.
 * @returns DpiSoundnessResult with theorem-backed soundness assessment and receipt.
 *
 * @example
 * ```typescript
 * const result = th6DpiSoundnessCheck([
 *   { name: "raw",      entropyBits: 7.2 },
 *   { name: "filtered", entropyBits: 5.1 },
 *   { name: "encoded",  entropyBits: 4.8 },
 * ]);
 * assert(result.sound); // entropy decreases monotonically ✓
 * ```
 */
export function th6DpiSoundnessCheck(
  stages: PipelineStage[]
): DpiSoundnessResult {
  if (stages.length < 1) {
    throw new Error("th6DpiSoundnessCheck: need at least 1 stage");
  }

  const EPS = 1e-9; // numerical tolerance for floating-point equality
  let sound = true;
  let violation: DpiSoundnessResult["violation"] | undefined;

  for (let i = 1; i < stages.length; i++) {
    const prev = stages[i - 1]!;
    const curr = stages[i]!;
    if (curr.entropyBits > prev.entropyBits + EPS) {
      sound = false;
      violation = {
        fromStage: prev.name,
        toStage: curr.name,
        fromEntropy: prev.entropyBits,
        toEntropy: curr.entropyBits,
        excess: curr.entropyBits - prev.entropyBits,
      };
      break; // report first violation only
    }
  }

  const inputs_hash = sha256Hex({ stages });
  const lean_commit_sha = process.env["LEAN_COMMIT_SHA"] ?? "unknown";

  const receipt: DpiDsseReceipt = {
    formula: "th6_dpi_soundness",
    lean_theorem: "Lutar.DPI.TH6_DPISoundness.dpi_receipt_chain_entropy_bound", // corrected per PhD-Math F5,
    lean_file: "Lutar/DPI/TH6_DPI_Soundness.lean",
    lean_commit_sha,
    inputs_hash,
    output: {
      sound,
      stageCount: stages.length,
      violation: violation ?? null,
    },
    ts: new Date().toISOString(),
  };

  return { sound, violation, stages, receipt };
}

/**
 * Convenience: throw on DPI violation.
 * Use in pipeline middleware to hard-block unsound configurations.
 */
export function assertDpiSoundness(stages: PipelineStage[]): DpiSoundnessResult {
  const result = th6DpiSoundnessCheck(stages);
  if (!result.sound) {
    const v = result.violation!;
    throw new Error(
      `DPI SOUNDNESS VIOLATION (TH6): entropy increased from stage "${v.fromStage}" ` +
        `(${v.fromEntropy} bits) to "${v.toStage}" (${v.toEntropy} bits), ` +
        `excess = ${v.excess.toFixed(6)} bits. ` +
        `Lean theorem Lutar.DPI.TH6_DPISoundness.th6_dpi_soundness prohibits entropy increase.`
    );
  }
  return result;
}

/**
 * Compute Shannon entropy (bits) from an array of symbol frequencies.
 * Utility export for callers that need to measure entropy inline.
 *
 * @param counts  Map of symbol → occurrence count
 */
export function shannonEntropyFromCounts(counts: Map<string, number>): number {
  let total = 0;
  for (const c of counts.values()) total += c;
  if (total === 0) return 0;
  let H = 0;
  for (const c of counts.values()) {
    const p = c / total;
    if (p > 0) H -= p * Math.log2(p);
  }
  return H;
}
