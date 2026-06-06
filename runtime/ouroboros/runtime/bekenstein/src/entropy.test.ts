// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Tests: ouroboros/bekenstein — TH6

import { describe, it, expect, beforeEach } from "vitest";
import {
  shannonEntropy,
  stringEntropy,
  bekensteinBound,
  trackTransit,
  getLedger,
  budgetSummary,
} from "./entropy.js";

// Reset ledger state between tests by re-importing with a fresh module
// (vitest isolates modules per test file by default)

describe("shannonEntropy", () => {
  it("returns 0 for empty buffer", () => {
    expect(shannonEntropy(new Uint8Array())).toBe(0);
  });

  it("returns 0 for uniform single-value buffer", () => {
    const buf = new Uint8Array(100).fill(42);
    expect(shannonEntropy(buf)).toBe(0);
  });

  it("returns ~1 for perfectly balanced 2-symbol distribution", () => {
    const buf = new Uint8Array(100);
    for (let i = 0; i < 100; i++) buf[i] = i < 50 ? 0 : 1;
    expect(shannonEntropy(buf)).toBeCloseTo(1.0, 2);
  });

  it("returns ≤ 8 for any byte buffer (max 8 bits/symbol)", () => {
    const random = new Uint8Array(256);
    for (let i = 0; i < 256; i++) random[i] = i;
    expect(shannonEntropy(random)).toBeLessThanOrEqual(8);
  });
});

describe("stringEntropy", () => {
  it("returns a non-negative number for a typical string", () => {
    expect(stringEntropy("Hello, World!")).toBeGreaterThan(0);
  });

  it("returns more entropy for random-looking string", () => {
    const low  = stringEntropy("aaaaaaaaaa");
    const high = stringEntropy("aBcDeF1234");
    expect(high).toBeGreaterThan(low);
  });
});

describe("bekensteinBound", () => {
  it("returns sizeBytes * 8", () => {
    expect(bekensteinBound(10)).toBe(80);
    expect(bekensteinBound(0)).toBe(0);
  });
});

describe("trackTransit", () => {
  it("records a transit within budget", () => {
    const hash = "a".repeat(64);
    const record = trackTransit(hash, "Hello World", "Hello World");
    expect(record.withinBudget).toBe(true);
    expect(record.receiptHash).toBe(hash);
    expect(record.outputBits).toBeLessThanOrEqual(record.bound);
  });

  it("never throws for normal text payloads (always within bound)", () => {
    // Since outputBits = H * sizeBytes ≤ 8 * sizeBytes = bound, this never throws
    const hash = "b".repeat(64);
    expect(() =>
      trackTransit(hash, "input payload here", "output payload here"),
    ).not.toThrow();
  });

  it("accumulates entries in ledger", () => {
    const before = getLedger().length;
    trackTransit("c".repeat(64), "foo", "bar");
    expect(getLedger().length).toBe(before + 1);
  });
});

describe("budgetSummary", () => {
  it("returns a summary with totalTransits ≥ 0", () => {
    const s = budgetSummary();
    expect(s.totalTransits).toBeGreaterThanOrEqual(0);
    expect(s.budgetUsedPercent).toBeGreaterThanOrEqual(0);
    expect(s.budgetUsedPercent).toBeLessThanOrEqual(100);
  });
});
