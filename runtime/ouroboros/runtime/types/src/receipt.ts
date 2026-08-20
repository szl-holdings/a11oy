// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: ouroboros/types  Thesis: TH7 (Typed Receipts as Propositions)
// Doctrine V6 preflight: ✓ (no forbidden patterns)

import { z } from "zod";

// ---------------------------------------------------------------------------
// 9-axis Lambda score schema
// ---------------------------------------------------------------------------

export const AxesSchema = z.object({
  moralGrounding:        z.number().min(0).max(1),
  measurabilityHonesty:  z.number().min(0).max(1),
  epistemicHumility:     z.number().min(0).max(1),
  harmAvoidance:         z.number().min(0).max(1),
  logicalCoherence:      z.number().min(0).max(1),
  citationIntegrity:     z.number().min(0).max(1),
  noveltyContribution:   z.number().min(0).max(1),
  reproducibility:       z.number().min(0).max(1),
  stakeholderAlignment:  z.number().min(0).max(1),
});

export type Axes = z.infer<typeof AxesSchema>;

// ---------------------------------------------------------------------------
// Receipt schema — TH7: receipt-as-proposition
// ---------------------------------------------------------------------------

export const ReceiptSchema = z.object({
  /** SHA-256 hex hash of canonical payload */
  hash:        z.string().regex(/^[0-9a-f]{64}$/),
  /** ISO-8601 timestamp */
  timestamp:   z.string().datetime(),
  /** Composite Λ score (conjunctive AND, threshold ≥ 0.90) */
  lambda:      z.number().min(0).max(1),
  axes:        AxesSchema,
  /** Opaque payload reference (URI or content-id) */
  payloadRef:  z.string().min(1),
  /** Optional parent hash for chain/closure linkage */
  parentHash:  z.string().regex(/^[0-9a-f]{64}$/).optional(),
  /** Semantic version of the Doctrine in force when receipt was issued */
  doctrineVer: z.string().default("6"),
  /** Arbitrary metadata for downstream modules */
  meta:        z.record(z.unknown()).optional(),
});

export type Receipt = z.infer<typeof ReceiptSchema>;

// ---------------------------------------------------------------------------
// Proposition mapping — every Receipt IS a logical proposition
// ---------------------------------------------------------------------------

export type Proposition = {
  /** Abbreviated propositional label, e.g. "Λ(h) ≥ 0.90" */
  label: string;
  /** Truth value derived from the receipt */
  holds: boolean;
  /** Supporting receipt hash */
  witness: string;
};

/**
 * Map a parsed Receipt to its canonical Proposition.
 * The proposition holds iff lambda ≥ 0.90 AND all axes parse cleanly.
 */
export function receiptToProposition(r: Receipt): Proposition {
  const holds = r.lambda >= 0.90;
  return {
    label:   `Λ(${r.hash.slice(0, 8)}…) ≥ 0.90`,
    holds,
    witness: r.hash,
  };
}

// ---------------------------------------------------------------------------
// Parse helpers — REJECT malformed receipts at parse time
// ---------------------------------------------------------------------------

/** Throws ZodError if receipt is malformed. */
export function parseReceipt(raw: unknown): Receipt {
  return ReceiptSchema.parse(raw);
}

/** Returns { success, data } without throwing. */
export function safeParseReceipt(raw: unknown) {
  return ReceiptSchema.safeParse(raw);
}
