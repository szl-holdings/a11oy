// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Tests for ouroboros/types — TH7

import { describe, it, expect } from "vitest";
import {
  parseReceipt,
  safeParseReceipt,
  receiptToProposition,
  type Receipt,
} from "./receipt.js";

const VALID_HASH = "a".repeat(64);
const VALID_AXES = {
  moralGrounding:       0.95,
  measurabilityHonesty: 0.95,
  epistemicHumility:    0.92,
  harmAvoidance:        0.91,
  logicalCoherence:     0.93,
  citationIntegrity:    0.91,
  noveltyContribution:  0.90,
  reproducibility:      0.92,
  stakeholderAlignment: 0.90,
};

const VALID_RECEIPT: unknown = {
  hash:        VALID_HASH,
  timestamp:   "2026-05-16T00:00:00.000Z",
  lambda:      0.92,
  axes:        VALID_AXES,
  payloadRef:  "ipfs://bafytest",
  doctrineVer: "6",
};

describe("parseReceipt", () => {
  it("accepts a fully valid receipt", () => {
    const r = parseReceipt(VALID_RECEIPT);
    expect(r.lambda).toBe(0.92);
    expect(r.hash).toBe(VALID_HASH);
  });

  it("rejects receipt with malformed hash", () => {
    expect(() => parseReceipt({ ...VALID_RECEIPT as object, hash: "short" })).toThrow();
  });

  it("rejects axes out of [0,1] range", () => {
    const bad = { ...VALID_RECEIPT as object, axes: { ...VALID_AXES, moralGrounding: 1.5 } };
    expect(() => parseReceipt(bad)).toThrow();
  });

  it("rejects missing payloadRef", () => {
    const bad = { ...VALID_RECEIPT as object };
    delete (bad as Record<string, unknown>)["payloadRef"];
    expect(() => parseReceipt(bad)).toThrow();
  });

  it("defaults doctrineVer to '6' when omitted", () => {
    const raw = { ...VALID_RECEIPT as object };
    delete (raw as Record<string, unknown>)["doctrineVer"];
    const r = parseReceipt(raw);
    expect(r.doctrineVer).toBe("6");
  });
});

describe("safeParseReceipt", () => {
  it("returns success=true for valid input", () => {
    const result = safeParseReceipt(VALID_RECEIPT);
    expect(result.success).toBe(true);
  });

  it("returns success=false without throwing for invalid input", () => {
    const result = safeParseReceipt({ not: "a receipt" });
    expect(result.success).toBe(false);
  });
});

describe("receiptToProposition", () => {
  it("holds=true when lambda ≥ 0.90", () => {
    const r = parseReceipt(VALID_RECEIPT) as Receipt;
    const p = receiptToProposition(r);
    expect(p.holds).toBe(true);
    expect(p.witness).toBe(VALID_HASH);
  });

  it("holds=false when lambda < 0.90", () => {
    const raw = { ...VALID_RECEIPT as object, lambda: 0.88 };
    const r = parseReceipt(raw) as Receipt;
    const p = receiptToProposition(r);
    expect(p.holds).toBe(false);
  });
});
