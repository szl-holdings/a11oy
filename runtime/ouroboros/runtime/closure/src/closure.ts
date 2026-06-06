// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: ouroboros/closure  Thesis: TH3 (ρ-Closure Composition)
// Doctrine V6 preflight: ✓

import { createHash } from "node:crypto";
import { parseReceipt, type Receipt, type Axes } from "@szl/ouroboros-types";
import { evaluateAxes } from "@szl/ouroboros-lambda-gate";

// ---------------------------------------------------------------------------
// ρ-Closure: composing N valid receipts into a composite receipt
// ---------------------------------------------------------------------------

/**
 * Compose axes by taking the component-wise minimum (most conservative bound).
 * This ensures the composite Λ is bounded by the weakest link.
 */
export function composeAxes(a: Axes, b: Axes): Axes {
  return {
    moralGrounding:        Math.min(a.moralGrounding,        b.moralGrounding),
    measurabilityHonesty:  Math.min(a.measurabilityHonesty,  b.measurabilityHonesty),
    epistemicHumility:     Math.min(a.epistemicHumility,     b.epistemicHumility),
    harmAvoidance:         Math.min(a.harmAvoidance,         b.harmAvoidance),
    logicalCoherence:      Math.min(a.logicalCoherence,      b.logicalCoherence),
    citationIntegrity:     Math.min(a.citationIntegrity,     b.citationIntegrity),
    noveltyContribution:   Math.min(a.noveltyContribution,   b.noveltyContribution),
    reproducibility:       Math.min(a.reproducibility,       b.reproducibility),
    stakeholderAlignment:  Math.min(a.stakeholderAlignment,  b.stakeholderAlignment),
  };
}

/** Identity axes — neutral element for composeAxes (1.0 on all axes). */
export const IDENTITY_AXES: Axes = {
  moralGrounding:       1.0,
  measurabilityHonesty: 1.0,
  epistemicHumility:    1.0,
  harmAvoidance:        1.0,
  logicalCoherence:     1.0,
  citationIntegrity:    1.0,
  noveltyContribution:  1.0,
  reproducibility:      1.0,
  stakeholderAlignment: 1.0,
};

// ---------------------------------------------------------------------------
// Composite receipt builder
// ---------------------------------------------------------------------------

export interface CompositionResult {
  composite: Receipt;
  lambda:    number;
  pass:      boolean;
  sources:   string[]; // input receipt hashes
}

/**
 * Chain N valid receipts into a single composite receipt.
 * The composite hash is SHA-256 of the sorted source hashes.
 * Throws if fewer than 2 receipts are supplied or any receipt fails validation.
 */
/** Optional clock injection enables byte-identical replay. */
export interface ComposeOptions {
  now?: () => string;
}
const defaultNow = (): string => new Date().toISOString();

export function compose(receipts: Receipt[], opts: ComposeOptions = {}): CompositionResult {
  if (receipts.length < 2) {
    throw new Error("compose requires at least 2 receipts");
  }
  const now = opts.now ?? defaultNow;

  // Validate each receipt through gate evaluation
  for (const r of receipts) {
    const ev = evaluateAxes(r.axes);
    if (!ev.pass) {
      throw new Error(`Receipt ${r.hash.slice(0, 16)} fails gate: ${ev.reasons.join("; ")}`);
    }
  }

  // Fold axes with component-wise minimum
  const compositeAxes = receipts
    .map((r) => r.axes)
    .reduce(composeAxes, IDENTITY_AXES);

  const ev = evaluateAxes(compositeAxes);

  // Deterministic composite hash
  const sources = receipts.map((r) => r.hash).sort();
  const compositeHash = createHash("sha256")
    .update(sources.join("|"))
    .digest("hex");

  const composite = parseReceipt({
    hash:        compositeHash,
    timestamp:   now(),
    lambda:      ev.lambda,
    axes:        compositeAxes,
    payloadRef:  `closure:${sources[0]?.slice(0, 8)}..${sources[sources.length - 1]?.slice(0, 8)}`,
    parentHash:  sources[0],
    doctrineVer: "6",
    meta:        { sourceCount: receipts.length, sources },
  });

  return { composite, lambda: ev.lambda, pass: ev.pass, sources };
}

// ---------------------------------------------------------------------------
// Associativity check helper (for property tests)
// ---------------------------------------------------------------------------

/**
 * Returns true if compose([a,b,c]) produces the same hash as
 * compose([compose([a,b]).composite, c]).
 * Associativity holds for the AXES fold (component-wise min), not for the
 * composite hash, since the hash is a function of the sorted input-hash set
 * and bracketing changes that set. We assert what is mathematically true:
 * the axes of `compose([a,b,c])` equal the axes of `compose([compose([a,b]), c])`.
 */
export function checkAssociativity(a: Receipt, b: Receipt, c: Receipt): boolean {
  const abc  = compose([a, b, c]);
  const ab   = compose([a, b]);
  const abc2 = compose([ab.composite, c]);
  const keys = Object.keys(abc.composite.axes) as (keyof Axes)[];
  return keys.every((k) => abc.composite.axes[k] === abc2.composite.axes[k]);
}
