/**
 * @file runtime/src/rae1/validate.ts
 * @description RAE-1 schema validator gate.
 *
 * Validates a DSSE envelope + inner RAE1Payload against the full
 * RAE-1 v1.0 spec (RAE_1_PROTOCOL.md §2, §3, §5.1).
 *
 * Lean ref:  SZL.AGI.PACBayes.capability_improvement_rate_bound
 * Lean file: Lutar/PACBayes/CapabilityImprovementRate.lean
 * Lean commit: c4d1379568
 *
 * Doctrine v7 — sorry_undisclosed is a validation ERROR, not a warning.
 * Signed-off-by: SZL Engineering <eng@szl-holdings.com>
 */

import {
  RAE1_SCHEMA_VERSION,
  RAE1_PAYLOAD_TYPE,
  RAE1_MIN_JUDGES,
  CHAIN_GENESIS,
  type DSSEEnvelope,
  type RAE1Payload,
  type RAE1JudgeRecord,
} from "./schema.js";

// ─── Result Types ─────────────────────────────────────────────────────────────

export interface RAE1ValidationResult {
  /** True iff the envelope passes all RAE-1 v1.0 validation rules. */
  valid: boolean;

  /** Ordered list of validation errors. Empty when valid === true. */
  errors: string[];

  /** Decoded schema_version if payload was parseable, else "unknown". */
  schema_version: string;

  /** Decoded run_id if payload was parseable, else null. */
  run_id: string | null;

  /** Decoded payload if parsing succeeded, else null. */
  payload: RAE1Payload | null;
}

// ─── Valid literal sets ───────────────────────────────────────────────────────

const VALID_BUILD_STATUSES = new Set([
  "green",
  "sorry_disclosed",
  "sorry_undisclosed",
  "failed",
]);

const VALID_VERDICTS = new Set(["SOLVED", "UNCLEAR", "WRONG"]);
const VALID_PROMPT_VARIANTS = new Set(["rigorous", "creative", "verification"]);

// ─── Internal helpers ─────────────────────────────────────────────────────────

function isString(v: unknown): v is string {
  return typeof v === "string";
}

function isNumber(v: unknown): v is number {
  return typeof v === "number" && isFinite(v);
}

function isBoolean(v: unknown): v is boolean {
  return typeof v === "boolean";
}

/**
 * Validates a single RAE1JudgeRecord.
 *
 * @param record - Raw judge object from parsed payload
 * @param index  - Position in the judges array (for error messages)
 * @returns Array of error strings for this judge (empty = valid)
 */
function validateJudge(record: unknown, index: number): string[] {
  const errors: string[] = [];
  if (typeof record !== "object" || record === null) {
    return [`judges[${index}]: not an object`];
  }
  const j = record as Record<string, unknown>;

  if (!isString(j.judge_id) || j.judge_id.length === 0) {
    errors.push(`judges[${index}].judge_id: must be non-empty string`);
  }
  if (!isString(j.model_name) || j.model_name.length === 0) {
    errors.push(`judges[${index}].model_name: must be non-empty string`);
  }
  if (!isString(j.system_prompt_variant) || !VALID_PROMPT_VARIANTS.has(j.system_prompt_variant)) {
    errors.push(
      `judges[${index}].system_prompt_variant: must be one of ${[...VALID_PROMPT_VARIANTS].join(", ")}`
    );
  }
  if (!isString(j.verdict) || !VALID_VERDICTS.has(j.verdict)) {
    errors.push(`judges[${index}].verdict: must be SOLVED | UNCLEAR | WRONG`);
  }
  if (!isNumber(j.confidence_01) || (j.confidence_01 as number) < 0 || (j.confidence_01 as number) > 1) {
    errors.push(`judges[${index}].confidence_01: must be number in [0, 1]`);
  }
  if (!isNumber(j.latency_ms) || (j.latency_ms as number) < 0) {
    errors.push(`judges[${index}].latency_ms: must be non-negative number`);
  }
  if (typeof j.token_usage !== "object" || j.token_usage === null) {
    errors.push(`judges[${index}].token_usage: must be an object`);
  } else {
    const tu = j.token_usage as Record<string, unknown>;
    if (!isNumber(tu.input)) errors.push(`judges[${index}].token_usage.input: must be number`);
    if (!isNumber(tu.output)) errors.push(`judges[${index}].token_usage.output: must be number`);
    if (!isNumber(tu.total)) errors.push(`judges[${index}].token_usage.total: must be number`);
  }
  return errors;
}

/**
 * Validates the decoded RAE1Payload object.
 *
 * @param payload - Parsed inner payload object
 * @returns Array of validation errors (empty = valid)
 */
function validatePayload(payload: Record<string, unknown>): string[] {
  const errors: string[] = [];

  // ── Schema version ────────────────────────────────────────────────────────
  if (payload.schema_version !== RAE1_SCHEMA_VERSION) {
    errors.push(
      `schema_version must be "${RAE1_SCHEMA_VERSION}", got: ${payload.schema_version}`
    );
  }

  // ── Run-level metadata ────────────────────────────────────────────────────
  if (!isString(payload.run_id) || payload.run_id.length === 0) {
    errors.push("run_id: must be non-empty string (UUIDv4)");
  }
  if (!isString(payload.run_timestamp) || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(payload.run_timestamp as string)) {
    errors.push("run_timestamp: must be ISO 8601 UTC string e.g. 2026-05-27T18:34:00Z");
  }
  if (!isString(payload.benchmark_name) || payload.benchmark_name.length === 0) {
    errors.push("benchmark_name: must be non-empty string");
  }
  if (!isNumber(payload.benchmark_year) || (payload.benchmark_year as number) < 1990) {
    errors.push("benchmark_year: must be a number >= 1990");
  }
  if (!isString(payload.harness_version) || payload.harness_version.length === 0) {
    errors.push("harness_version: must be non-empty string");
  }
  if (!isString(payload.harness_commit_sha) || !/^[0-9a-f]{7,64}$/i.test(payload.harness_commit_sha as string)) {
    errors.push("harness_commit_sha: must be a hex git SHA (7–64 chars)");
  }

  // ── Problem fields ────────────────────────────────────────────────────────
  if (!isString(payload.problem_id) || payload.problem_id.length === 0) {
    errors.push("problem_id: must be non-empty string");
  }
  if (!isString(payload.problem_sha256) || !/^[0-9a-f]{64}$/i.test(payload.problem_sha256 as string)) {
    errors.push("problem_sha256: must be a 64-character hex SHA-256");
  }
  if (!isString(payload.domain) || payload.domain.length === 0) {
    errors.push("domain: must be non-empty string");
  }

  // ── Judges ────────────────────────────────────────────────────────────────
  if (!Array.isArray(payload.judges)) {
    errors.push(`judges: must be an array`);
  } else if ((payload.judges as unknown[]).length < RAE1_MIN_JUDGES) {
    errors.push(
      `judges: must have ≥ ${RAE1_MIN_JUDGES} entries (RAE-1 §3.1), got ${(payload.judges as unknown[]).length}`
    );
  } else {
    for (let i = 0; i < (payload.judges as unknown[]).length; i++) {
      errors.push(...validateJudge((payload.judges as unknown[])[i], i));
    }
  }

  // ── Ensemble decision ─────────────────────────────────────────────────────
  if (!isString(payload.ensemble_verdict) || !VALID_VERDICTS.has(payload.ensemble_verdict as string)) {
    errors.push("ensemble_verdict: must be SOLVED | UNCLEAR | WRONG");
  }
  if (!isNumber(payload.votes_solved) || (payload.votes_solved as number) < 0) {
    errors.push("votes_solved: must be non-negative number");
  }
  if (!isNumber(payload.votes_unclear) || (payload.votes_unclear as number) < 0) {
    errors.push("votes_unclear: must be non-negative number");
  }
  if (!isNumber(payload.votes_wrong) || (payload.votes_wrong as number) < 0) {
    errors.push("votes_wrong: must be non-negative number");
  }

  // ── Score contribution ────────────────────────────────────────────────────
  if (!isBoolean(payload.is_solved)) {
    errors.push("is_solved: must be boolean");
  }
  // is_solved MUST match ensemble_verdict
  if (isBoolean(payload.is_solved) && isString(payload.ensemble_verdict)) {
    const expectedSolved = payload.ensemble_verdict === "SOLVED";
    if (payload.is_solved !== expectedSolved) {
      errors.push(
        `is_solved (${payload.is_solved}) inconsistent with ensemble_verdict "${payload.ensemble_verdict}"`
      );
    }
  }

  // ── Chain linkage ─────────────────────────────────────────────────────────
  if (!isString(payload.prev_hash)) {
    errors.push("prev_hash: must be string (hex SHA-256 or 'GENESIS')");
  } else if (
    payload.prev_hash !== CHAIN_GENESIS &&
    !/^[0-9a-f]{64}$/i.test(payload.prev_hash as string)
  ) {
    errors.push(
      `prev_hash: must be "GENESIS" or a 64-character hex SHA-256, got: ${payload.prev_hash}`
    );
  }
  if (!isNumber(payload.receipt_index) || (payload.receipt_index as number) < 0 || !Number.isInteger(payload.receipt_index)) {
    errors.push("receipt_index: must be a non-negative integer");
  }

  // ── Lean theorem reference ────────────────────────────────────────────────
  if (!isString(payload.lean_theorem_name) || payload.lean_theorem_name.length === 0) {
    errors.push("lean_theorem_name: must be non-empty string (RAE-1 §2.2 requires this field)");
  }
  if (!isString(payload.lean_theorem_file) || payload.lean_theorem_file.length === 0) {
    errors.push("lean_theorem_file: must be non-empty string");
  }
  if (!isString(payload.lean_commit_sha) || !/^[0-9a-f]{7,64}$/i.test(payload.lean_commit_sha as string)) {
    errors.push("lean_commit_sha: must be a hex git SHA (7–64 chars)");
  }
  if (!isString(payload.lean_repo) || payload.lean_repo.length === 0) {
    errors.push("lean_repo: must be non-empty string e.g. szl-holdings/lutar-lean");
  }

  // ── Lean build status ─────────────────────────────────────────────────────
  if (!isString(payload.lean_build_status) || !VALID_BUILD_STATUSES.has(payload.lean_build_status as string)) {
    errors.push(
      `lean_build_status: must be one of ${[...VALID_BUILD_STATUSES].join(", ")}`
    );
  }

  // Doctrine v7: sorry_undisclosed is an explicit violation
  if (payload.lean_build_status === "sorry_undisclosed") {
    errors.push(
      "lean_build_status 'sorry_undisclosed' violates Doctrine v7 — all sorries must be named with discharge routes"
    );
  }

  if (!isNumber(payload.lean_sorry_count) || (payload.lean_sorry_count as number) < 0 || !Number.isInteger(payload.lean_sorry_count)) {
    errors.push("lean_sorry_count: must be a non-negative integer");
  }
  if (payload.lean_build_status === "green" && (payload.lean_sorry_count as number) !== 0) {
    errors.push(
      `lean_sorry_count must be 0 when lean_build_status is "green", got ${payload.lean_sorry_count}`
    );
  }

  // ── Staged advisory ───────────────────────────────────────────────────────
  if (!isBoolean(payload.staged_advisory)) {
    errors.push("staged_advisory: must be boolean");
  }
  if (payload.staged_notes !== undefined && !isString(payload.staged_notes)) {
    errors.push("staged_notes: must be string if present");
  }

  return errors;
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Validates a DSSE envelope and its inner RAE-1 payload.
 *
 * Does NOT verify the HMAC signature — use verifyHMAC() in hmac.ts for that.
 * This function validates structure and semantic constraints only.
 *
 * Lean ref: SZL.AGI.PACBayes.capability_improvement_rate_bound
 *           file: Lutar/PACBayes/CapabilityImprovementRate.lean
 *           commit: c4d1379568
 *
 * @param envelope - Raw unknown value to validate
 * @returns RAE1ValidationResult with valid flag + error list
 *
 * @example
 * ```typescript
 * const result = validateRAE1Schema(envelope);
 * if (!result.valid) {
 *   console.error("Validation failed:", result.errors);
 * }
 * ```
 */
export function validateRAE1Schema(envelope: unknown): RAE1ValidationResult {
  const errors: string[] = [];
  let schemaVersion = "unknown";
  let runId: string | null = null;
  let decodedPayload: RAE1Payload | null = null;

  // ── Outer envelope checks ─────────────────────────────────────────────────
  if (typeof envelope !== "object" || envelope === null) {
    return {
      valid: false,
      errors: ["envelope: must be a non-null object"],
      schema_version: schemaVersion,
      run_id: runId,
      payload: null,
    };
  }

  const e = envelope as Record<string, unknown>;

  if (e.payloadType !== RAE1_PAYLOAD_TYPE) {
    errors.push(
      `payloadType: must be "${RAE1_PAYLOAD_TYPE}", got: ${e.payloadType}`
    );
  }
  if (!isString(e.payload)) {
    errors.push("payload: must be a base64url string");
  }
  if (!Array.isArray(e.signatures) || (e.signatures as unknown[]).length === 0) {
    errors.push("signatures: must be a non-empty array");
  } else {
    for (let i = 0; i < (e.signatures as unknown[]).length; i++) {
      const sig = (e.signatures as unknown[])[i];
      if (typeof sig !== "object" || sig === null) {
        errors.push(`signatures[${i}]: must be an object`);
      } else {
        const s = sig as Record<string, unknown>;
        if (!isString(s.keyid)) errors.push(`signatures[${i}].keyid: must be string`);
        if (!isString(s.sig)) errors.push(`signatures[${i}].sig: must be string`);
      }
    }
  }

  // ── Decode and validate inner payload ────────────────────────────────────
  if (isString(e.payload)) {
    let rawPayload: Record<string, unknown>;
    try {
      const decoded = Buffer.from(e.payload, "base64url").toString("utf8");
      rawPayload = JSON.parse(decoded) as Record<string, unknown>;
    } catch {
      errors.push("payload: not valid base64url-encoded JSON");
      return { valid: false, errors, schema_version: schemaVersion, run_id: runId, payload: null };
    }

    schemaVersion = isString(rawPayload.schema_version)
      ? rawPayload.schema_version
      : "unknown";
    runId = isString(rawPayload.run_id) ? rawPayload.run_id : null;

    const payloadErrors = validatePayload(rawPayload);
    errors.push(...payloadErrors);

    if (payloadErrors.length === 0) {
      decodedPayload = rawPayload as unknown as RAE1Payload;
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    schema_version: schemaVersion,
    run_id: runId,
    payload: decodedPayload,
  };
}

/**
 * Encodes a RAE1Payload as base64url JSON for embedding in a DSSEEnvelope.
 *
 * @param payload - Fully populated RAE1Payload object
 * @returns base64url string ready for DSSEEnvelope.payload field
 */
export function encodePayload(payload: RAE1Payload): string {
  return Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
}

/**
 * Decodes a base64url payload string back to a RAE1Payload.
 *
 * @param encoded - base64url string from DSSEEnvelope.payload
 * @returns Parsed RAE1Payload (not validated — call validateRAE1Schema for full validation)
 * @throws If the string is not valid base64url JSON
 */
export function decodePayload(encoded: string): RAE1Payload {
  const json = Buffer.from(encoded, "base64url").toString("utf8");
  return JSON.parse(json) as RAE1Payload;
}
