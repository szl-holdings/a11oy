/**
 * @file runtime/src/rae1/validate.test.ts
 * @description Vitest unit tests for RAE-1 schema validation.
 *
 * Lean ref:  SZL.AGI.PACBayes.capability_improvement_rate_bound
 * Lean file: Lutar/PACBayes/CapabilityImprovementRate.lean
 * Lean commit: c4d1379568
 *
 * Acceptance criteria (per PR-1 spec):
 *   ✓ valid envelope passes
 *   ✓ missing lean_theorem_name fails
 *   ✓ sorry_undisclosed fails Doctrine v6 check
 *   ✓ < 3 judges fails
 */

import { describe, it, expect } from "vitest";
import {
  validateRAE1Schema,
  encodePayload,
  decodePayload,
} from "./validate.js";
import type { DSSEEnvelope, RAE1Payload } from "./schema.js";
import { RAE1_PAYLOAD_TYPE, RAE1_SCHEMA_VERSION } from "./schema.js";

// ─── Test fixture helpers ─────────────────────────────────────────────────────

function makeValidPayload(overrides: Partial<RAE1Payload> = {}): RAE1Payload {
  const base: RAE1Payload = {
    schema_version: "rae1.0",
    run_id: "f3a1b2c4-d5e6-7890-abcd-ef1234567890",
    run_timestamp: "2026-05-27T18:34:00Z",
    benchmark_name: "bench-2024",
    benchmark_year: 2024,
    harness_version: "v2.0.0",
    harness_commit_sha: "3672670ee8be63aa5f116ca6124f3f3a4545b4e0",
    problem_id: "bench-2024-A1",
    problem_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    domain: "combinatorics",
    judges: [
      {
        judge_id: "judge-0-rigorous",
        model_name: "claude-3-5-sonnet-20241022",
        system_prompt_variant: "rigorous",
        verdict: "SOLVED",
        confidence_01: 0.91,
        latency_ms: 1243,
        token_usage: { input: 512, output: 384, total: 896 },
      },
      {
        judge_id: "judge-1-creative",
        model_name: "claude-3-5-sonnet-20241022",
        system_prompt_variant: "creative",
        verdict: "SOLVED",
        confidence_01: 0.87,
        latency_ms: 1109,
        token_usage: { input: 512, output: 311, total: 823 },
      },
      {
        judge_id: "judge-2-verification",
        model_name: "gpt-4o-2024-11-20",
        system_prompt_variant: "verification",
        verdict: "UNCLEAR",
        confidence_01: 0.55,
        latency_ms: 987,
        token_usage: { input: 512, output: 201, total: 713 },
      },
    ],
    ensemble_verdict: "SOLVED",
    votes_solved: 2,
    votes_unclear: 1,
    votes_wrong: 0,
    is_solved: true,
    prev_hash: "GENESIS",
    receipt_index: 0,
    lean_theorem_name: "SZL.AGI.PACBayes.capability_improvement_rate_bound",
    lean_theorem_file: "Lutar/PACBayes/CapabilityImprovementRate.lean",
    lean_commit_sha: "c4d1379568abcdef1234567890abcdef12345678",
    lean_repo: "szl-holdings/lutar-lean",
    lean_build_status: "sorry_disclosed",
    lean_sorry_count: 2,
    staged_advisory: false,
  };
  return { ...base, ...overrides };
}

function makeValidEnvelope(payloadOverrides: Partial<RAE1Payload> = {}): DSSEEnvelope {
  const payload = makeValidPayload(payloadOverrides);
  return {
    payloadType: RAE1_PAYLOAD_TYPE,
    payload: encodePayload(payload),
    signatures: [
      {
        keyid: "hmac-sha256:abc123",
        sig: "dGVzdHNpZ25hdHVyZQ",
      },
    ],
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("validateRAE1Schema — valid envelopes", () => {
  it("accepts a fully valid envelope with sorry_disclosed", () => {
    const result = validateRAE1Schema(makeValidEnvelope());
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
    expect(result.schema_version).toBe("rae1.0");
    expect(result.run_id).toBe("f3a1b2c4-d5e6-7890-abcd-ef1234567890");
  });

  it("accepts a green build (sorry_count=0)", () => {
    const result = validateRAE1Schema(
      makeValidEnvelope({ lean_build_status: "green", lean_sorry_count: 0 })
    );
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it("accepts staged_advisory=true with notes", () => {
    const result = validateRAE1Schema(
      makeValidEnvelope({
        staged_advisory: true,
        staged_notes: "Mock judges — no real API keys",
      })
    );
    expect(result.valid).toBe(true);
  });

  it("accepts non-GENESIS prev_hash for chained receipts", () => {
    const prevHash = "a".repeat(64);
    const result = validateRAE1Schema(
      makeValidEnvelope({ prev_hash: prevHash, receipt_index: 1 })
    );
    expect(result.valid).toBe(true);
  });

  it("returns decoded payload object on success", () => {
    const result = validateRAE1Schema(makeValidEnvelope());
    expect(result.payload).not.toBeNull();
    expect(result.payload?.benchmark_name).toBe("bench-2024");
  });
});

describe("validateRAE1Schema — Lean theorem violations", () => {
  it("fails when lean_theorem_name is missing", () => {
    const payload = makeValidPayload();
    // Cast to any to force deletion of required field
    delete (payload as Record<string, unknown>)["lean_theorem_name"];
    const envelope: DSSEEnvelope = {
      payloadType: RAE1_PAYLOAD_TYPE,
      payload: Buffer.from(JSON.stringify(payload), "utf8").toString("base64url"),
      signatures: [{ keyid: "k1", sig: "s1" }],
    };
    const result = validateRAE1Schema(envelope);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("lean_theorem_name"))).toBe(true);
  });

  it("fails when lean_commit_sha is not a valid hex SHA", () => {
    const result = validateRAE1Schema(
      makeValidEnvelope({ lean_commit_sha: "not-a-sha" })
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("lean_commit_sha"))).toBe(true);
  });

  it("fails when lean_build_status is 'sorry_undisclosed' (Doctrine v6)", () => {
    const result = validateRAE1Schema(
      makeValidEnvelope({
        lean_build_status: "sorry_undisclosed",
        lean_sorry_count: 3,
      })
    );
    expect(result.valid).toBe(false);
    const hasDoctrineError = result.errors.some(
      (e) => e.includes("sorry_undisclosed") && e.includes("Doctrine v6")
    );
    expect(hasDoctrineError).toBe(true);
  });

  it("fails when lean_build_status is 'green' but lean_sorry_count > 0", () => {
    const result = validateRAE1Schema(
      makeValidEnvelope({ lean_build_status: "green", lean_sorry_count: 1 })
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("lean_sorry_count"))).toBe(true);
  });

  it("fails when lean_build_status is an invalid value", () => {
    const result = validateRAE1Schema(
      makeValidEnvelope({ lean_build_status: "unknown_status" as never })
    );
    expect(result.valid).toBe(false);
  });
});

describe("validateRAE1Schema — judge ensemble violations", () => {
  it("fails with fewer than 3 judges", () => {
    const twoJudges = makeValidPayload().judges.slice(0, 2);
    const result = validateRAE1Schema(makeValidEnvelope({ judges: twoJudges }));
    expect(result.valid).toBe(false);
    const hasJudgeError = result.errors.some(
      (e) => e.includes("judges") && e.includes("≥ 3")
    );
    expect(hasJudgeError).toBe(true);
  });

  it("fails with empty judges array", () => {
    const result = validateRAE1Schema(makeValidEnvelope({ judges: [] }));
    expect(result.valid).toBe(false);
  });

  it("fails when a judge has an invalid system_prompt_variant", () => {
    const judges = makeValidPayload().judges.map((j, i) =>
      i === 0 ? { ...j, system_prompt_variant: "adversarial" as never } : j
    );
    const result = validateRAE1Schema(makeValidEnvelope({ judges }));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("system_prompt_variant"))).toBe(true);
  });

  it("fails when confidence_01 is out of [0,1]", () => {
    const judges = makeValidPayload().judges.map((j, i) =>
      i === 0 ? { ...j, confidence_01: 1.5 } : j
    );
    const result = validateRAE1Schema(makeValidEnvelope({ judges }));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("confidence_01"))).toBe(true);
  });
});

describe("validateRAE1Schema — envelope structure violations", () => {
  it("fails when payloadType is wrong", () => {
    const env = makeValidEnvelope();
    const result = validateRAE1Schema({ ...env, payloadType: "application/json" });
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("payloadType"))).toBe(true);
  });

  it("fails when payload is not a string", () => {
    const env = makeValidEnvelope();
    const result = validateRAE1Schema({ ...env, payload: 42 });
    expect(result.valid).toBe(false);
  });

  it("fails when payload is corrupt base64url", () => {
    const env = makeValidEnvelope();
    const result = validateRAE1Schema({ ...env, payload: "!!!not-base64url!!!" });
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("payload"))).toBe(true);
  });

  it("fails when signatures is empty array", () => {
    const env = makeValidEnvelope();
    const result = validateRAE1Schema({ ...env, signatures: [] });
    expect(result.valid).toBe(false);
  });

  it("fails when envelope is null", () => {
    const result = validateRAE1Schema(null);
    expect(result.valid).toBe(false);
    expect(result.schema_version).toBe("unknown");
  });

  it("fails when envelope is a string", () => {
    const result = validateRAE1Schema("not-an-object");
    expect(result.valid).toBe(false);
  });
});

describe("validateRAE1Schema — chain linkage violations", () => {
  it("fails when prev_hash is not GENESIS and not 64 hex chars", () => {
    const result = validateRAE1Schema(
      makeValidEnvelope({ prev_hash: "short", receipt_index: 1 })
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("prev_hash"))).toBe(true);
  });

  it("fails when receipt_index is negative", () => {
    const result = validateRAE1Schema(
      makeValidEnvelope({ receipt_index: -1 })
    );
    expect(result.valid).toBe(false);
  });

  it("fails when is_solved is inconsistent with ensemble_verdict", () => {
    const result = validateRAE1Schema(
      makeValidEnvelope({ ensemble_verdict: "WRONG", is_solved: true })
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("is_solved") && e.includes("inconsistent"))).toBe(true);
  });
});

describe("encodePayload / decodePayload round-trip", () => {
  it("round-trips a valid payload", () => {
    const original = makeValidPayload();
    const encoded = encodePayload(original);
    const decoded = decodePayload(encoded);
    expect(decoded).toEqual(original);
  });

  it("encodes to valid base64url (no + or / chars)", () => {
    const encoded = encodePayload(makeValidPayload());
    expect(encoded).not.toMatch(/[+/=]/);
  });
});
