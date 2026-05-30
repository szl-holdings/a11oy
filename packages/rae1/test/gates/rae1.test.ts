/**
 * @file packages/rae1/test/gates/rae1.test.ts
 * @description Integration tests for the @szl-holdings/rae1 package (20 vitest cases).
 *
 * Tests the full gate surface: schema validation, chain integrity, HMAC verification,
 * and the Lean theorem reference fields in receipts.
 *
 * Lean ref:  SZL.AGI.PACBayes.capability_improvement_rate_bound
 * Lean file: Lutar/PACBayes/CapabilityImprovementRate.lean
 * Lean commit: c4d1379568
 *
 * Acceptance criteria (per PR-5 spec): ≥ 18/20 tests pass
 */

import { describe, it, expect } from "vitest";
import { createHmac, createHash } from "crypto";

// Import from the package root (as a user would)
import {
  RAE1_SCHEMA_VERSION,
  RAE1_PAYLOAD_TYPE,
  RAE1_MIN_JUDGES,
  LEAN_THEOREM_NAME,
  LEAN_THEOREM_FILE,
  CHAIN_GENESIS,
  RAE1_PACKAGE_VERSION,
  RAE1_PROTOCOL_VERSION,
  LEAN_COMMIT_SHA_PINNED,
} from "../../src/index.js";

import {
  validateRAE1Schema,
  encodePayload,
  decodePayload,
} from "../../src/validate.js";

import {
  computeLineHash,
  validateReceiptChain,
  computeChainHead,
  verifyReceiptLinkage,
  serializeEnvelope,
} from "../../src/chain.js";

import { pae, verifyHMAC, signEnvelope } from "../../src/hmac.js";

import type { DSSEEnvelope, RAE1Payload } from "../../src/schema.js";

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const TEST_HMAC_KEY = Buffer.from("szl-rae1-test-key-do-not-use-in-production", "utf8");

function makePayload(
  index: number = 0,
  prevHash: string = "GENESIS",
  isSolved: boolean = false
): RAE1Payload {
  return {
    schema_version: "rae1.0",
    run_id: "test-run-00000000-0000-0000-0000-000000000001",
    run_timestamp: "2026-05-27T18:34:00Z",
    benchmark_name: "putnam-2024",
    benchmark_year: 2024,
    harness_version: "v2.0.0",
    harness_commit_sha: "3672670ee8be63aa5f116ca6124f3f3a4545b4e0",
    problem_id: `putnam-2024-A${index + 1}`,
    problem_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    domain: "combinatorics",
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
  };
}

function makeEnvelope(payload: RAE1Payload, signed = true): DSSEEnvelope {
  const encodedPayload = encodePayload(payload);
  const base: DSSEEnvelope = {
    payloadType: RAE1_PAYLOAD_TYPE,
    payload: encodedPayload,
    signatures: [],
  };
  if (signed) {
    return signEnvelope(base, TEST_HMAC_KEY, "hmac-sha256:test-key-id");
  }
  return base;
}

function buildChain(n: number, solvedIndices: Set<number> = new Set()): string[] {
  const lines: string[] = [];
  let prevHash = "GENESIS";
  for (let i = 0; i < n; i++) {
    const payload = makePayload(i, prevHash, solvedIndices.has(i));
    const envelope = makeEnvelope(payload);
    const line = serializeEnvelope(envelope);
    lines.push(line);
    prevHash = computeLineHash(line);
  }
  return lines;
}

// ─── Test Suite ───────────────────────────────────────────────────────────────

describe("Package constants and metadata", () => {
  it("[T-1] Package exports correct Lean theorem name", () => {
    expect(LEAN_THEOREM_NAME).toBe(
      "SZL.AGI.PACBayes.capability_improvement_rate_bound"
    );
  });

  it("[T-2] Package exports correct Lean theorem file path", () => {
    expect(LEAN_THEOREM_FILE).toBe("Lutar/PACBayes/CapabilityImprovementRate.lean");
  });

  it("[T-3] Package version is 1.0.0", () => {
    expect(RAE1_PACKAGE_VERSION).toBe("1.0.0");
  });

  it("[T-4] Protocol version is rae1.0", () => {
    expect(RAE1_PROTOCOL_VERSION).toBe("rae1.0");
    expect(RAE1_SCHEMA_VERSION).toBe("rae1.0");
  });

  it("[T-5] LEAN_COMMIT_SHA_PINNED is c4d1379568", () => {
    expect(LEAN_COMMIT_SHA_PINNED).toBe("c4d1379568");
  });
});

describe("Schema validation gate (RAE-1 §2, §5.1)", () => {
  it("[T-6] Accepts valid envelope (sorry_disclosed, 3 judges)", () => {
    const result = validateRAE1Schema(makeEnvelope(makePayload(0)));
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it("[T-7] Rejects sorry_undisclosed (Doctrine v6 gate)", () => {
    const payload = makePayload(0);
    payload.lean_build_status = "sorry_undisclosed";
    payload.lean_sorry_count = 5;
    const result = validateRAE1Schema(makeEnvelope(payload));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("Doctrine v6"))).toBe(true);
  });

  it("[T-8] Rejects < 3 judges", () => {
    const payload = makePayload(0);
    payload.judges = payload.judges.slice(0, 2);
    const result = validateRAE1Schema(makeEnvelope(payload));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("≥ 3"))).toBe(true);
  });

  it("[T-9] Rejects missing lean_theorem_name", () => {
    const payload = makePayload(0);
    delete (payload as Record<string, unknown>)["lean_theorem_name"];
    const env: DSSEEnvelope = {
      payloadType: RAE1_PAYLOAD_TYPE,
      payload: Buffer.from(JSON.stringify(payload), "utf8").toString("base64url"),
      signatures: [{ keyid: "k", sig: "s" }],
    };
    const result = validateRAE1Schema(env);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("lean_theorem_name"))).toBe(true);
  });

  it("[T-10] Returns decoded payload on success", () => {
    const payload = makePayload(0);
    const result = validateRAE1Schema(makeEnvelope(payload));
    expect(result.payload?.benchmark_name).toBe("putnam-2024");
    expect(result.payload?.lean_sorry_count).toBe(2);
  });
});

describe("Chain integrity gate (RAE-1 §4)", () => {
  it("[T-11] Validates 12-receipt chain (Putnam-sized)", () => {
    const lines = buildChain(12, new Set([0]));
    const result = validateReceiptChain(lines.join("\n"));
    expect(result.valid).toBe(true);
    expect(result.n_receipts).toBe(12);
    expect(result.n_solved).toBe(1);
    expect(result.score_01).toBeCloseTo(1 / 12, 6);
  });

  it("[T-12] chain_head matches manual SHA-256 of last line", () => {
    const lines = buildChain(12, new Set([0]));
    const result = validateReceiptChain(lines.join("\n"));
    const expected = createHash("sha256")
      .update(lines[11]!, "utf8")
      .digest("hex");
    expect(result.chain_head).toBe(expected);
  });

  it("[T-13] Detects tampered receipt (prev_hash mismatch)", () => {
    const lines = buildChain(5);
    // Replace line 2 with a different payload (breaks the chain at line 3)
    const badPayload = makePayload(2, "GENESIS", false); // Wrong prev_hash
    const badLine = serializeEnvelope(makeEnvelope(badPayload));
    lines[2] = badLine;
    const result = validateReceiptChain(lines.join("\n"));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("prev_hash mismatch"))).toBe(true);
  });

  it("[T-14] score_01 matches n_solved / n_receipts exactly", () => {
    const solvedSet = new Set([0, 5, 9]);
    const lines = buildChain(12, solvedSet);
    const result = validateReceiptChain(lines.join("\n"));
    expect(result.score_01).toBeCloseTo(3 / 12, 10);
    expect(result.n_solved).toBe(3);
  });

  it("[T-15] Empty JSONL has score_01 = 0 and is valid", () => {
    const result = validateReceiptChain("");
    expect(result.valid).toBe(true);
    expect(result.score_01).toBe(0);
    expect(result.chain_head).toBe("GENESIS");
  });
});

describe("HMAC signature gate (RAE-1 §5.3)", () => {
  it("[T-16] verifyHMAC returns true for correctly signed envelope", () => {
    const payload = makePayload(0);
    const envelope = makeEnvelope(payload, true); // signed with TEST_HMAC_KEY
    expect(verifyHMAC(envelope, TEST_HMAC_KEY)).toBe(true);
  });

  it("[T-17] verifyHMAC returns false for wrong key", () => {
    const payload = makePayload(0);
    const envelope = makeEnvelope(payload, true);
    const wrongKey = Buffer.from("wrong-key", "utf8");
    expect(verifyHMAC(envelope, wrongKey)).toBe(false);
  });

  it("[T-18] pae() output length is correct (8 + 8 + len(type) + 8 + len(payload))", () => {
    const type = "application/vnd.szl.rae1+json";
    const payload = "abc123";
    const result = pae([type, payload]);
    const expected = 8 + 8 + type.length + 8 + payload.length;
    expect(result.length).toBe(expected);
  });

  it("[T-19] signEnvelope then verifyHMAC round-trips", () => {
    const base: DSSEEnvelope = {
      payloadType: RAE1_PAYLOAD_TYPE,
      payload: encodePayload(makePayload(0)),
      signatures: [],
    };
    const signed = signEnvelope(base, TEST_HMAC_KEY, "hmac-sha256:testkey");
    expect(signed.signatures).toHaveLength(1);
    expect(verifyHMAC(signed, TEST_HMAC_KEY)).toBe(true);
  });

  it("[T-20] Tampered payload breaks HMAC signature", () => {
    const payload = makePayload(0);
    const envelope = makeEnvelope(payload, true);
    // Corrupt the payload
    const corrupted = { ...envelope, payload: envelope.payload + "x" };
    expect(verifyHMAC(corrupted, TEST_HMAC_KEY)).toBe(false);
  });
});
