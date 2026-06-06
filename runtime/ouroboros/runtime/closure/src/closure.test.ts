// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Tests: ouroboros/closure — TH3

import { describe, it, expect } from "vitest";
import { compose, composeAxes, IDENTITY_AXES, checkAssociativity } from "./closure.js";
import { parseReceipt, type Receipt, type Axes } from "@szl/ouroboros-types";

const GOOD_AXES: Axes = {
  moralGrounding:       0.96,
  measurabilityHonesty: 0.96,
  epistemicHumility:    0.92,
  harmAvoidance:        0.91,
  logicalCoherence:     0.93,
  citationIntegrity:    0.91,
  noveltyContribution:  0.90,
  reproducibility:      0.92,
  stakeholderAlignment: 0.91,
};

function makeReceipt(seed: string, axes: Axes = GOOD_AXES): Receipt {
  return parseReceipt({
    hash:        seed.repeat(64).slice(0, 64),
    timestamp:   "2026-05-16T00:00:00.000Z",
    lambda:      0.92,
    axes,
    payloadRef:  `test:${seed}`,
    doctrineVer: "6",
  });
}

const R1 = makeReceipt("aa");
const R2 = makeReceipt("bb");
const R3 = makeReceipt("cc");

describe("composeAxes", () => {
  it("component-wise minimum", () => {
    const a: Axes = { ...GOOD_AXES, epistemicHumility: 0.95 };
    const b: Axes = { ...GOOD_AXES, epistemicHumility: 0.91 };
    const c = composeAxes(a, b);
    expect(c.epistemicHumility).toBe(0.91);
  });

  it("identity element: composeAxes(a, IDENTITY) == a", () => {
    const result = composeAxes(GOOD_AXES, IDENTITY_AXES);
    for (const [k, v] of Object.entries(GOOD_AXES) as [keyof Axes, number][]) {
      expect(result[k]).toBe(v);
    }
  });

  it("commutativity: composeAxes(a,b) == composeAxes(b,a)", () => {
    const ab = composeAxes(GOOD_AXES, IDENTITY_AXES);
    const ba = composeAxes(IDENTITY_AXES, GOOD_AXES);
    for (const k of Object.keys(ab) as (keyof Axes)[]) {
      expect(ab[k]).toBe(ba[k]);
    }
  });
});

describe("compose", () => {
  it("produces a valid composite receipt from 2 receipts", () => {
    const result = compose([R1, R2]);
    expect(result.pass).toBe(true);
    expect(result.composite.hash).toHaveLength(64);
    expect(result.sources).toHaveLength(2);
  });

  it("throws when fewer than 2 receipts supplied", () => {
    expect(() => compose([R1])).toThrow(/at least 2/);
  });

  it("throws when a receipt fails the gate", () => {
    const badAxes: Axes = { ...GOOD_AXES, moralGrounding: 0.50 };
    const bad = makeReceipt("dd", badAxes);
    expect(() => compose([R1, bad])).toThrow(/fails gate/);
  });

  it("composite hash is deterministic", () => {
    const a = compose([R1, R2]);
    const b = compose([R2, R1]); // order shouldn't matter (sorted)
    expect(a.composite.hash).toBe(b.composite.hash);
  });

  it("composite lambda ≤ min input lambda", () => {
    const lower: Axes = { ...GOOD_AXES, epistemicHumility: 0.90 };
    const rLow = makeReceipt("ee", lower);
    const result = compose([R1, rLow]);
    expect(result.lambda).toBeLessThanOrEqual(0.92);
  });
});

describe("associativity property (axes-only)", () => {
  it("axes of compose([a,b,c]) == axes of compose([compose([a,b]), c])", () => {
    // Hashes diverge by design (set of inputs differs across bracketings);
    // the axes fold (component-wise min) is genuinely associative.
    expect(checkAssociativity(R1, R2, R3)).toBe(true);
  });
});
