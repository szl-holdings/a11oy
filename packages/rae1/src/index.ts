/**
 * @file packages/rae1/src/index.ts
 * @description @szl-holdings/rae1 — RAE-1 Protocol Implementation
 *
 * RAE-1 (Receipt-Attested Evaluation) is SZL Holdings' cryptographically
 * verifiable AI benchmark attestation protocol. This package provides the
 * TypeScript reference implementation of the RAE-1 v1.0 specification.
 *
 * ## Protocol Overview
 *
 * Every RAE-1 evaluation run emits one DSSE-signed receipt per problem,
 * chained by SHA-256, such that an outside reviewer can verify the run
 * in under 5 minutes using only this package and the public receipts.jsonl.
 *
 * ## Key Exports
 *
 * - **schema**: TypeScript types for DSSEEnvelope, RAE1Payload, RAE1JudgeRecord
 * - **validate**: validateRAE1Schema(), encodePayload(), decodePayload()
 * - **chain**: validateReceiptChain(), computeChainHead(), computeLineHash()
 * - **hmac**: pae(), verifyHMAC(), signEnvelope()
 *
 * ## Lean Theorem Reference
 *
 * This package embeds references to:
 * - Theorem: `SZL.AGI.PACBayes.capability_improvement_rate_bound`
 * - File: `Lutar/PACBayes/CapabilityImprovementRate.lean`
 * - Commit: c4d1379568 (szl-holdings/lutar-lean)
 * - Build: sorry_disclosed (2 named sorries: AsymptoticTightness, KLMonotonicity)
 *
 * ## Verification Example
 *
 * ```typescript
 * import { validateReceiptChain, validateRAE1Schema } from "@szl-holdings/rae1";
 * import { readFileSync } from "fs";
 *
 * // Verify a complete receipt chain
 * const content = readFileSync("receipts.jsonl", "utf8");
 * const result = validateReceiptChain(content);
 * console.log("Valid:", result.valid, "Score:", result.score_01, "Head:", result.chain_head);
 *
 * // Validate a single envelope
 * const envelope = JSON.parse(line);
 * const validation = validateRAE1Schema(envelope);
 * if (!validation.valid) console.error(validation.errors);
 * ```
 *
 * ## References
 *
 * - Protocol spec: RAE_1_PROTOCOL.md (SZL Holdings, 2026-05-29)
 * - DSSE spec: github.com/secure-systems-lab/dsse
 * - PAC-Bayes: arXiv:2407.20122, arXiv:2510.25569
 * - competition-math benchmark suite: arXiv:2407.11214
 *
 * Doctrine v6 — no fake lake-green, no new axioms.
 * Signed-off-by: SZL Engineering <eng@szl-holdings.com>
 */

// ─── Schema Types ─────────────────────────────────────────────────────────────

export type {
  RAE1JudgeRecord,
  RAE1Payload,
  DSSEEnvelope,
  ChainSummary,
  JudgePromptVariant,
  Verdict,
} from "./schema.js";

export {
  RAE1_SCHEMA_VERSION,
  RAE1_PAYLOAD_TYPE,
  RAE1_MIN_JUDGES,
  LEAN_THEOREM_NAME,
  LEAN_THEOREM_FILE,
  CHAIN_GENESIS,
} from "./schema.js";

// ─── Validation ───────────────────────────────────────────────────────────────

export type { RAE1ValidationResult } from "./validate.js";

export {
  validateRAE1Schema,
  encodePayload,
  decodePayload,
} from "./validate.js";

// ─── Chain Integrity ─────────────────────────────────────────────────────────

export type {
  ChainValidationResult,
  ChainHeadResult,
} from "./chain.js";

export {
  computeLineHash,
  validateReceiptChain,
  computeChainHead,
  verifyReceiptLinkage,
  serializeEnvelope,
  decodeEnvelopePayload,
} from "./chain.js";

// ─── HMAC Verification ───────────────────────────────────────────────────────

export { pae, paeRaw, verifyHMAC, signEnvelope, makeKeyId } from "./hmac.js";
export {
  dsseV1Pae,
  dsseV1PaeFromBase64Body,
  base64ToBytes,
} from "./dsse-pae.js";

// ─── Package Metadata ────────────────────────────────────────────────────────

/** Package version, synchronized with package.json. */
export const RAE1_PACKAGE_VERSION = "1.0.0" as const;

/** Protocol version implemented by this package. */
export const RAE1_PROTOCOL_VERSION = "rae1.0" as const;

/** Lean theorem name attested by this package version. */
export const LEAN_THEOREM_CANONICAL =
  "SZL.AGI.PACBayes.capability_improvement_rate_bound" as const;

/** Lean commit SHA pinned at this package release. */
export const LEAN_COMMIT_SHA_PINNED = "c4d1379568" as const;
