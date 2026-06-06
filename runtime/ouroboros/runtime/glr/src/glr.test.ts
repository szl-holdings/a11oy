// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Tests: ouroboros/glr — TH8

import { describe, it, expect, beforeEach } from "vitest";
import {
  ConsumptionLedger,
  LinearityError,
  gradeFromLambda,
  composeGrades,
  gradeWeight,
} from "./glr.js";
import { parseReceipt, type Axes } from "@szl/ouroboros-types";

const AXES: Axes = {
  moralGrounding:       0.96,
  measurabilityHonesty: 0.96,
  epistemicHumility:    0.92,
  harmAvoidance:        0.91,
  logicalCoherence:     0.93,
  citationIntegrity:    0.91,
  noveltyContribution:  0.91,
  reproducibility:      0.92,
  stakeholderAlignment: 0.91,
};

function makeReceipt(seed: string, lambda: number) {
  return parseReceipt({
    hash:        seed.repeat(64).slice(0, 64),
    timestamp:   "2026-05-16T00:00:00.000Z",
    lambda,
    axes:        AXES,
    payloadRef:  `test:${seed}`,
    doctrineVer: "6",
  });
}

const R_A = makeReceipt("aa", 0.96); // Grade A
const R_B = makeReceipt("bb", 0.93); // Grade B
const R_D = makeReceipt("dd", 0.85); // Grade D

describe("gradeFromLambda", () => {
  it("returns A for lambda ≥ 0.95", () => expect(gradeFromLambda(0.95)).toBe("A"));
  it("returns B for lambda ≥ 0.92", () => expect(gradeFromLambda(0.92)).toBe("B"));
  it("returns C for lambda ≥ 0.90", () => expect(gradeFromLambda(0.90)).toBe("C"));
  it("returns D for lambda < 0.90",  () => expect(gradeFromLambda(0.85)).toBe("D"));
});

describe("composeGrades", () => {
  it("returns lower grade (weakest link)", () => {
    expect(composeGrades("A", "B")).toBe("B");
    expect(composeGrades("B", "A")).toBe("B");
    expect(composeGrades("A", "D")).toBe("D");
  });

  it("same grade returns same", () => {
    expect(composeGrades("B", "B")).toBe("B");
  });
});

describe("ConsumptionLedger", () => {
  let ledger: ConsumptionLedger;

  beforeEach(() => { ledger = new ConsumptionLedger(); });

  it("registers and peeks without consuming", () => {
    ledger.register(R_A);
    const gr = ledger.peek(R_A.hash);
    expect(gr).toBeDefined();
    expect(gr?.consumed).toBe(false);
    expect(gr?.grade).toBe("A");
  });

  it("consumes a receipt exactly once", () => {
    ledger.register(R_B);
    const gr = ledger.consume(R_B.hash);
    expect(gr.consumed).toBe(true);
  });

  it("throws LinearityError on double-consume", () => {
    ledger.register(R_A);
    ledger.consume(R_A.hash);
    expect(() => ledger.consume(R_A.hash)).toThrow(LinearityError);
  });

  it("throws when consuming an unregistered hash", () => {
    expect(() => ledger.consume("f".repeat(64))).toThrow(LinearityError);
  });

  it("throws on duplicate registration", () => {
    ledger.register(R_A);
    expect(() => ledger.register(R_A)).toThrow(/already registered/);
  });

  it("listAvailable excludes consumed and below-grade", () => {
    ledger.register(R_A);
    ledger.register(R_B);
    ledger.register(R_D);
    ledger.consume(R_A.hash);
    const available = ledger.listAvailable("B");
    expect(available.some((gr) => gr.receipt.hash === R_B.hash)).toBe(true);
    expect(available.some((gr) => gr.receipt.hash === R_A.hash)).toBe(false); // consumed
    expect(available.some((gr) => gr.receipt.hash === R_D.hash)).toBe(false); // grade D < B
  });
});
