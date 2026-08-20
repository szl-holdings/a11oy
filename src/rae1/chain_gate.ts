/**
 * @file runtime/src/rae1/chain_gate.ts
 * @description RAE-1 SHA-256 hash chain verification and integrity enforcement.
 *
 * Validates JSONL receipt chains for RAE-1 protocol compliance.
 * Each line is a DSSE-signed envelope; the payload's prev_hash field
 * must equal the SHA-256 of the prior line (exact bytes, compact JSON).
 *
 * Lean ref:  SZL.AGI.PACBayes.capability_improvement_rate_bound
 * Lean file: Lutar/PACBayes/CapabilityImprovementRate.lean
 * Lean commit: c4d1379568
 *
 * Protocol spec: RAE_1_PROTOCOL.md §4
 *
 * Chain linkage formula:
 *   hash(R_i) = SHA-256(raw_json_line_i)         (UTF-8, compact, no trailing newline)
 *   R_{i+1}.payload.prev_hash = hex(hash(R_i))
 *   R_0.payload.prev_hash = "GENESIS"
 *
 * Doctrine v11 — real code, no fake green.
 * Signed-off-by: SZL Engineering <eng@szl-holdings.com>
 */

import { createHash } from "crypto";
import { CHAIN_GENESIS } from "./schema.js";
import type { DSSEEnvelope, RAE1Payload } from "./schema.js";

// ─── Types ────────────────────────────────────────────────────────────────────

/**
 * Result of validating a complete JSONL receipt chain.
 *
 * Lean ref: SZL.AGI.PACBayes.capability_improvement_rate_bound
 *           commit: c4d1379568
 */
export interface ChainValidationResult {
  /** True iff all receipts form a valid, unbroken SHA-256 chain. */
  valid: boolean;

  /** Number of receipts processed. */
  n_receipts: number;

  /**
   * The genesis sentinel for this chain. Always "GENESIS" for RAE-1 v1.0
   * (a future extension may support run_id-keyed genesis hashes).
   */
  chain_root: string;

  /** SHA-256 hex of the last receipt line — the published verification handle. */
  chain_head: string;

  /** Number of receipts where is_solved === true. */
  n_solved: number;

  /**
   * Score as a fraction in [0, 1].
   * Equals n_solved / n_receipts if n_receipts > 0, else 0.
   */
  score_01: number;

  /** List of validation errors in order. Empty when valid === true. */
  errors: string[];
}

/**
 * Lightweight result for computing only the chain head without full validation.
 */
export interface ChainHeadResult {
  /** SHA-256 hex of the final receipt line. */
  chain_head: string;

  /** Number of lines processed. */
  n_lines: number;
}

// ─── Core Primitives ─────────────────────────────────────────────────────────

/**
 * Computes the SHA-256 hex digest of a single receipt line (raw UTF-8 bytes).
 *
 * This is the canonical hash used in the `prev_hash` field of the next receipt.
 *
 * IMPORTANT: The input MUST be the exact raw JSON line as it appears in the JSONL file
 * (compact, no trailing newline or extra whitespace). Any whitespace difference will
 * produce a different hash and break the chain.
 *
 * Lean ref: SZL.AGI.PACBayes.capability_improvement_rate_bound
 *           commit: c4d1379568
 *
 * @param line - Raw JSON line string (UTF-8, compact, no trailing newline)
 * @returns 64-character lowercase hex SHA-256 digest
 */
export function computeLineHash(line: string): string {
  return createHash("sha256").update(line, "utf8").digest("hex");
}

/**
 * Decodes a base64url payload string from a DSSE envelope into a RAE1Payload.
 *
 * Does not validate the payload — use validateRAE1Schema() for full validation.
 *
 * @param envelope - DSSE envelope containing base64url-encoded payload
 * @returns Parsed RAE1Payload
 * @throws If the payload is not valid base64url JSON
 */
export function decodeEnvelopePayload(envelope: DSSEEnvelope): RAE1Payload {
  const raw = Buffer.from(envelope.payload, "base64url").toString("utf8");
  return JSON.parse(raw) as RAE1Payload;
}

// ─── Chain Validation ─────────────────────────────────────────────────────────

/**
 * Validates the SHA-256 hash chain over a complete JSONL receipt file.
 *
 * Algorithm (per RAE_1_PROTOCOL.md §4.1):
 * 1. Split content by newlines, filter blank lines.
 * 2. For each line i:
 *    a. Parse as JSON → DSSEEnvelope
 *    b. Base64url-decode payload → RAE1Payload
 *    c. Assert payload.prev_hash === expectedPrevHash
 *    d. Assert payload.receipt_index === i
 *    e. Update expectedPrevHash = SHA-256(line_i)
 * 3. Return chain_head = expectedPrevHash after final receipt.
 *
 * Lean ref: SZL.AGI.PACBayes.capability_improvement_rate_bound
 *           file: Lutar/PACBayes/CapabilityImprovementRate.lean
 *           commit: c4d1379568
 *
 * @param jsonlContent - Full content of a receipts.jsonl file as a string
 * @returns ChainValidationResult with validity flag, head hash, score, and errors
 *
 * @example
 * ```typescript
 * import { readFileSync } from "fs";
 * const content = readFileSync("receipts.jsonl", "utf8");
 * const result = validateReceiptChain(content);
 * if (result.valid) {
 *   console.log("Chain valid. Head:", result.chain_head, "Score:", result.score_01);
 * } else {
 *   console.error("Chain broken:", result.errors);
 * }
 * ```
 */
export function validateReceiptChain(jsonlContent: string): ChainValidationResult {
  const lines = jsonlContent.split("\n").filter((l) => l.trim().length > 0);
  const errors: string[] = [];
  let prevHash = CHAIN_GENESIS;
  let chainRoot = CHAIN_GENESIS;
  let nSolved = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Step 1: Parse outer DSSE envelope
    let envelope: Record<string, unknown>;
    try {
      envelope = JSON.parse(line) as Record<string, unknown>;
    } catch (e) {
      errors.push(`Line ${i}: JSON parse error — ${(e as Error).message}`);
      // Can't compute chain hash without valid JSON; advance with synthetic hash to continue checking
      prevHash = computeLineHash(line);
      continue;
    }

    // Step 2: Decode inner payload
    let payload: Record<string, unknown>;
    try {
      if (typeof envelope.payload !== "string") {
        throw new Error("envelope.payload is not a string");
      }
      const raw = Buffer.from(envelope.payload, "base64url").toString("utf8");
      payload = JSON.parse(raw) as Record<string, unknown>;
    } catch (e) {
      errors.push(`Line ${i}: payload decode error — ${(e as Error).message}`);
      prevHash = computeLineHash(line);
      continue;
    }

    // Step 3: Track chain root (for first receipt, prev_hash should be GENESIS)
    if (i === 0) {
      chainRoot = typeof payload.prev_hash === "string" ? payload.prev_hash : CHAIN_GENESIS;
    }

    // Step 4: Verify prev_hash linkage
    const claimedPrevHash = payload.prev_hash as string;
    if (claimedPrevHash !== prevHash) {
      errors.push(
        `Line ${i} (receipt_index=${payload.receipt_index}): ` +
          `prev_hash mismatch — expected "${prevHash}", got "${claimedPrevHash}"`
      );
    }

    // Step 5: Verify receipt_index
    if (payload.receipt_index !== i) {
      errors.push(
        `Line ${i}: receipt_index ${payload.receipt_index} !== expected ${i}`
      );
    }

    // Step 6: Count solved receipts
    if (payload.is_solved === true) {
      nSolved++;
    }

    // Step 7: Compute hash of THIS line for next iteration
    prevHash = computeLineHash(line);
  }

  return {
    valid: errors.length === 0,
    n_receipts: lines.length,
    chain_root: chainRoot,
    chain_head: prevHash,
    n_solved: nSolved,
    score_01: lines.length > 0 ? nSolved / lines.length : 0,
    errors,
  };
}

// ─── Chain Head Computation ───────────────────────────────────────────────────

/**
 * Computes only the chain head from a JSONL file without full validation.
 *
 * Faster than validateReceiptChain() when only the head hash is needed
 * (e.g., for publication to latest.json).
 *
 * Lean ref: SZL.AGI.PACBayes.capability_improvement_rate_bound
 *           commit: c4d1379568
 *
 * @param jsonlContent - Full content of a receipts.jsonl file
 * @returns ChainHeadResult with chain_head and n_lines
 */
export function computeChainHead(jsonlContent: string): ChainHeadResult {
  const lines = jsonlContent.split("\n").filter((l) => l.trim().length > 0);
  let head = CHAIN_GENESIS;
  for (const line of lines) {
    head = computeLineHash(line);
  }
  return { chain_head: head, n_lines: lines.length };
}

// ─── Single Receipt Verification ─────────────────────────────────────────────

/**
 * Verifies that a single receipt line correctly links to the expected previous hash.
 *
 * Used by auditors to spot-check specific receipts without replaying the full chain.
 *
 * @param line           - Raw JSON line of the DSSE envelope (compact, UTF-8)
 * @param expectedPrevHash - Expected value of prev_hash (previous line's SHA-256 or "GENESIS")
 * @param expectedIndex  - Expected receipt_index value
 * @returns Object with valid flag and errors array
 */
export function verifyReceiptLinkage(
  line: string,
  expectedPrevHash: string,
  expectedIndex: number
): { valid: boolean; errors: string[]; lineHash: string } {
  const errors: string[] = [];

  let payload: Record<string, unknown>;
  try {
    const envelope = JSON.parse(line) as Record<string, unknown>;
    const raw = Buffer.from(envelope.payload as string, "base64url").toString("utf8");
    payload = JSON.parse(raw) as Record<string, unknown>;
  } catch (e) {
    const lineHash = computeLineHash(line);
    return { valid: false, errors: [`Parse error: ${(e as Error).message}`], lineHash };
  }

  if (payload.prev_hash !== expectedPrevHash) {
    errors.push(
      `prev_hash mismatch — expected "${expectedPrevHash}", got "${payload.prev_hash}"`
    );
  }
  if (payload.receipt_index !== expectedIndex) {
    errors.push(`receipt_index ${payload.receipt_index} !== expected ${expectedIndex}`);
  }

  const lineHash = computeLineHash(line);
  return { valid: errors.length === 0, errors, lineHash };
}

// ─── JSONL Line Builder ───────────────────────────────────────────────────────

/**
 * Builds a compact JSONL line from a DSSEEnvelope, suitable for appending to receipts.jsonl.
 *
 * IMPORTANT: Uses JSON.stringify without any whitespace to ensure hash consistency.
 * The SHA-256 of this string becomes the next receipt's prev_hash.
 *
 * @param envelope - Fully signed DSSEEnvelope
 * @returns Compact JSON string (no trailing newline)
 */
export function serializeEnvelope(envelope: DSSEEnvelope): string {
  return JSON.stringify(envelope);
}
