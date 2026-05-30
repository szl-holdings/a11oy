/**
 * @file runtime/src/rae1/chain_gate.test.ts
 * @description Vitest tests for RAE-1 SHA-256 chain integrity enforcement.
 *
 * Lean ref:  SZL.AGI.PACBayes.capability_improvement_rate_bound
 * Lean file: Lutar/PACBayes/CapabilityImprovementRate.lean
 * Lean commit: c4d1379568
 *
 * Acceptance criteria (per PR-2 spec, 15+ cases):
 *   ✓ 12-receipt chain validates
 *   ✓ tampered receipt detected
 *   ✓ chain_head matches expected hex
 *   ✓ score_01 = n_solved / n_receipts
 */

import { describe, it, expect } from "vitest";
import { createHash } from "crypto";
import {
  computeLineHash,
  validateReceiptChain,
  computeChainHead,
  verifyReceiptLinkage,
  serializeEnvelope,
} from "./chain_gate.js";
import { encodePayload } from "./validate.js";
import type { DSSEEnvelope, RAE1Payload } from "./schema.js";
import { RAE1_PAYLOAD_TYPE } from "./schema.js";

// ─── Test fixture helpers ─────────────────────────────────────────────────────

function makePayload(
  index: number,
  prevHash: string,
  isSolved: boolean,
  overrides: Partial<RAE1Payload> = {}
): RAE1Payload {
  return {
    schema_version: "rae1.0",
    run_id: "test-run-id-12345",
    run_timestamp: "2026-05-27T18:34:00Z",
    benchmark_name: "bench-2024",
    benchmark_year: 2024,
    harness_version: "v2.0.0",
    harness_commit_sha: "3672670ee8be63aa5f116ca6124f3f3a4545b4e0",
    problem_id: `bench-2024-problem-${index}`,
    problem_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    domain: "algebra",
    judges: [
      {
        judge_id: "judge-0-rigorous",
        model_name: "claude-3-5-sonnet-20241022",
        system_prompt_variant: "rigorous",
        verdict: isSolved ? "SOLVED" : "WRONG",
        confidence_01: 0.8,
        latency_ms: 1000,
        token_usage: { input: 100, output: 100, total: 200 },
      },
      {
        judge_id: "judge-1-creative",
        model_name: "claude-3-5-sonnet-20241022",
        system_prompt_variant: "creative",
        verdict: isSolved ? "SOLVED" : "WRONG",
        confidence_01: 0.75,
        latency_ms: 950,
        token_usage: { input: 100, output: 90, total: 190 },
      },
      {
        judge_id: "judge-2-verification",
        model_name: "gpt-4o-2024-11-20",
        system_prompt_variant: "verification",
        verdict: isSolved ? "SOLVED" : "WRONG",
        confidence_01: 0.85,
        latency_ms: 800,
        token_usage: { input: 100, output: 80, total: 180 },
      },
    ],
    ensemble_verdict: isSolved ? "SOLVED" : "WRONG",
    votes_solved: isSolved ? 3 : 0,
    votes_unclear: 0,
    votes_wrong: isSolved ? 0 : 3,
    is_solved: isSolved,
    prev_hash: prevHash,
    receipt_index: index,
    lean_theorem_name: "SZL.AGI.PACBayes.capability_improvement_rate_bound",
    lean_theorem_file: "Lutar/PACBayes/CapabilityImprovementRate.lean",
    lean_commit_sha: "c4d1379568abcdef1234567890abcdef12345678",
    lean_repo: "szl-holdings/lutar-lean",
    lean_build_status: "sorry_disclosed",
    lean_sorry_count: 2,
    staged_advisory: false,
    ...overrides,
  };
}

function makeEnvelopeLine(payload: RAE1Payload): string {
  const envelope: DSSEEnvelope = {
    payloadType: RAE1_PAYLOAD_TYPE,
    payload: encodePayload(payload),
    signatures: [{ keyid: "hmac-sha256:testkey", sig: "dGVzdA" }],
  };
  return serializeEnvelope(envelope);
}

/**
 * Builds a valid JSONL chain of n receipts.
 * Only the first receipt is solved (index 0).
 */
function buildChain(n: number, solvedIndices: Set<number> = new Set([0])): string[] {
  const lines: string[] = [];
  let prevHash = "GENESIS";
  for (let i = 0; i < n; i++) {
    const payload = makePayload(i, prevHash, solvedIndices.has(i));
    const line = makeEnvelopeLine(payload);
    lines.push(line);
    prevHash = computeLineHash(line);
  }
  return lines;
}

// ─── Tests: computeLineHash ───────────────────────────────────────────────────

describe("computeLineHash", () => {
  it("returns a 64-character lowercase hex string", () => {
    const hash = computeLineHash("hello world");
    expect(hash).toMatch(/^[0-9a-f]{64}$/);
  });

  it("matches Node.js crypto reference implementation", () => {
    const input = '{"payloadType":"test","payload":"abc"}';
    const expected = createHash("sha256").update(input, "utf8").digest("hex");
    expect(computeLineHash(input)).toBe(expected);
  });

  it("is sensitive to a single character change", () => {
    const h1 = computeLineHash("abc");
    const h2 = computeLineHash("abd");
    expect(h1).not.toBe(h2);
  });

  it("is deterministic across multiple calls", () => {
    const h1 = computeLineHash("test input");
    const h2 = computeLineHash("test input");
    expect(h1).toBe(h2);
  });
});

// ─── Tests: validateReceiptChain — valid chains ───────────────────────────────

describe("validateReceiptChain — valid chains", () => {
  it("validates a 1-receipt GENESIS chain", () => {
    const lines = buildChain(1);
    const result = validateReceiptChain(lines.join("\n"));
    expect(result.valid).toBe(true);
    expect(result.n_receipts).toBe(1);
    expect(result.n_solved).toBe(1);
    expect(result.score_01).toBe(1.0);
    expect(result.chain_root).toBe("GENESIS");
    expect(result.errors).toHaveLength(0);
  });

  it("validates a 12-receipt chain with 1 solved (score_01 = 1/12)", () => {
    const lines = buildChain(12, new Set([0]));
    const result = validateReceiptChain(lines.join("\n"));
    expect(result.valid).toBe(true);
    expect(result.n_receipts).toBe(12);
    expect(result.n_solved).toBe(1);
    expect(result.score_01).toBeCloseTo(1 / 12, 6);
    expect(result.errors).toHaveLength(0);
  });

  it("chain_head for 12-receipt chain matches manual SHA-256 of last line", () => {
    const lines = buildChain(12, new Set([0]));
    const result = validateReceiptChain(lines.join("\n"));
    const expectedHead = computeLineHash(lines[11]);
    expect(result.chain_head).toBe(expectedHead);
  });

  it("validates a 12-receipt chain with 4 solved (score_01 = 4/12)", () => {
    const solvedSet = new Set([0, 3, 7, 11]);
    const lines = buildChain(12, solvedSet);
    const result = validateReceiptChain(lines.join("\n"));
    expect(result.valid).toBe(true);
    expect(result.n_solved).toBe(4);
    expect(result.score_01).toBeCloseTo(4 / 12, 6);
  });

  it("returns score_01 = 0 for an empty JSONL string", () => {
    const result = validateReceiptChain("");
    expect(result.valid).toBe(true);
    expect(result.n_receipts).toBe(0);
    expect(result.score_01).toBe(0);
    expect(result.chain_head).toBe("GENESIS");
  });

  it("ignores blank lines in JSONL input", () => {
    const lines = buildChain(3);
    const withBlanks = lines.join("\n\n") + "\n";
    const result = validateReceiptChain(withBlanks);
    expect(result.valid).toBe(true);
    expect(result.n_receipts).toBe(3);
  });
});

// ─── Tests: validateReceiptChain — tampered chains ───────────────────────────

describe("validateReceiptChain — tampered chains", () => {
  it("detects prev_hash mismatch (tampered receipt body)", () => {
    const lines = buildChain(5);
    // Tamper with line 2 by replacing its payload (the prev_hash check for line 3 will fail)
    const tamperedPayload = makePayload(2, "GENESIS", false); // Wrong prev_hash
    const tamperedLine = makeEnvelopeLine(tamperedPayload);
    lines[2] = tamperedLine;

    const result = validateReceiptChain(lines.join("\n"));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("prev_hash mismatch"))).toBe(true);
  });

  it("detects receipt_index mismatch", () => {
    const lines = buildChain(5);
    // Manually decode and re-encode with wrong receipt_index
    const payload = makePayload(3, computeLineHash(lines[2]), false, { receipt_index: 99 });
    lines[3] = makeEnvelopeLine(payload);
    const result = validateReceiptChain(lines.join("\n"));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("receipt_index"))).toBe(true);
  });

  it("detects JSON parse error on a corrupted line", () => {
    const lines = buildChain(4);
    lines[1] = "{not valid json!!!";
    const result = validateReceiptChain(lines.join("\n"));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("JSON parse error"))).toBe(true);
  });

  it("detects payload decode error on a corrupt base64 field", () => {
    const lines = buildChain(4);
    // Replace the payload field with non-base64url JSON
    const env = JSON.parse(lines[2]) as Record<string, unknown>;
    env.payload = "!!!";
    lines[2] = JSON.stringify(env);
    const result = validateReceiptChain(lines.join("\n"));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("payload decode error"))).toBe(true);
  });

  it("accumulates multiple errors from multiple broken receipts", () => {
    const lines = buildChain(6);
    // Break lines 1 and 4
    lines[1] = "{broken json}";
    lines[4] = "{broken json}";
    const result = validateReceiptChain(lines.join("\n"));
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThanOrEqual(2);
  });
});

// ─── Tests: computeChainHead ─────────────────────────────────────────────────

describe("computeChainHead", () => {
  it("matches chain_head from validateReceiptChain on same input", () => {
    const lines = buildChain(8, new Set([0, 5]));
    const content = lines.join("\n");
    const fullResult = validateReceiptChain(content);
    const headResult = computeChainHead(content);
    expect(headResult.chain_head).toBe(fullResult.chain_head);
  });

  it("returns GENESIS for empty input", () => {
    const result = computeChainHead("");
    expect(result.chain_head).toBe("GENESIS");
    expect(result.n_lines).toBe(0);
  });

  it("returns correct n_lines count", () => {
    const lines = buildChain(7);
    const result = computeChainHead(lines.join("\n"));
    expect(result.n_lines).toBe(7);
  });
});

// ─── Tests: verifyReceiptLinkage ──────────────────────────────────────────────

describe("verifyReceiptLinkage", () => {
  it("passes for the first receipt (GENESIS prev_hash)", () => {
    const payload = makePayload(0, "GENESIS", true);
    const line = makeEnvelopeLine(payload);
    const result = verifyReceiptLinkage(line, "GENESIS", 0);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it("passes for a non-genesis receipt with correct prev_hash", () => {
    const lines = buildChain(3);
    const prevHash = computeLineHash(lines[1]);
    // Line 2 has prev_hash = SHA-256(lines[1])
    const result = verifyReceiptLinkage(lines[2], computeLineHash(lines[1]), 2);
    expect(result.valid).toBe(true);
  });

  it("fails for wrong expected prev_hash", () => {
    const lines = buildChain(2);
    const result = verifyReceiptLinkage(lines[1], "GENESIS", 1);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("prev_hash mismatch"))).toBe(true);
  });

  it("returns correct lineHash for use as next receipt's prev_hash", () => {
    const payload = makePayload(0, "GENESIS", false);
    const line = makeEnvelopeLine(payload);
    const result = verifyReceiptLinkage(line, "GENESIS", 0);
    expect(result.lineHash).toBe(computeLineHash(line));
  });
});

// ─── Tests: score_01 correctness ─────────────────────────────────────────────

describe("score_01 computation", () => {
  it("score_01 = 0 when no problems solved", () => {
    const lines = buildChain(12, new Set());
    const result = validateReceiptChain(lines.join("\n"));
    expect(result.n_solved).toBe(0);
    expect(result.score_01).toBe(0);
  });

  it("score_01 = 1 when all problems solved", () => {
    const lines = buildChain(12, new Set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]));
    const result = validateReceiptChain(lines.join("\n"));
    expect(result.n_solved).toBe(12);
    expect(result.score_01).toBe(1.0);
  });

  it("score_01 matches the recorded raw-score baseline (1/12 ≈ 0.0833)", () => {
    const lines = buildChain(12, new Set([0])); // Only problem 0 solved
    const result = validateReceiptChain(lines.join("\n"));
    expect(result.score_01).toBeCloseTo(0.0833, 3);
  });
});
