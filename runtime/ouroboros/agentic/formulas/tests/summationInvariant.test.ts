// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 3 — Parity test for SummationInvariant
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/Khipu/SummationInvariant.lean
//   Commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// Property tests:
//   1. khipuReceipt_checksum_invariant: computedTotal === primaryCord
//      when receipt is built via buildKhipuReceipt (trivially valid)
//   2. invariant fails exactly when primaryCord is tampered
//   3. invariant holds for any organ count ≥ 0
//   4. lambdaScore = 1 iff invariantHolds, else 0
//   5. pendantValues.length = organs.length

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import {
  summationInvariant,
  buildKhipuReceipt,
  type KhipuReceipt,
  type OrganReceipt,
} from "./summationInvariant.js";

const FC_RUNS = 1000;

// Arbitrary organ receipt generator
const arbDecision = () =>
  fc.record({
    decisionId: fc.string({ minLength: 1, maxLength: 16 }),
    value: fc.integer({ min: 0, max: 1_000_000 }),
  });

const arbOrgan = () =>
  fc.record({
    organId: fc.string({ minLength: 1, maxLength: 16 }),
    decisions: fc.array(arbDecision(), { minLength: 0, maxLength: 10 }),
  });

const arbOrgans = () => fc.array(arbOrgan(), { minLength: 0, maxLength: 8 });

describe("SummationInvariant — Layer 3 parity test", () => {
  // Property 1 (Lean: khipuReceipt_checksum_invariant):
  // buildKhipuReceipt always produces a receipt where invariantHolds = true
  it("P1: invariant holds for any validly-built receipt", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 8 }),
        arbOrgans(),
        (id, organs) => {
          const receipt = buildKhipuReceipt(id, organs);
          const result = summationInvariant(receipt);
          return result.invariantHolds === true;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 2: tampering with primaryCord breaks the invariant
  it("P2: invariant fails exactly when primaryCord is tampered (delta ≠ 0)", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 8 }),
        arbOrgans(),
        fc.integer({ min: 1, max: 999 }),  // non-zero tamper delta
        (id, organs, delta) => {
          const receipt = buildKhipuReceipt(id, organs);
          const tampered: KhipuReceipt = {
            ...receipt,
            primaryCord: receipt.primaryCord + delta,
          };
          const result = summationInvariant(tampered);
          return result.invariantHolds === false;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 3: computedTotal = sum of all leaf values across all organs
  it("P3: computedTotal = sum of all leaf values", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 8 }),
        arbOrgans(),
        (id, organs) => {
          const receipt = buildKhipuReceipt(id, organs);
          const allLeafSum = organs
            .flatMap((o) => o.decisions)
            .reduce((s, d) => s + d.value, 0);
          const result = summationInvariant(receipt);
          return result.computedTotal === allLeafSum;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 4: lambdaScore = 1 iff invariantHolds, else 0
  it("P4: lambdaScore = 1 iff invariantHolds, else 0", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 8 }),
        arbOrgans(),
        fc.integer({ min: 0, max: 999 }),
        fc.boolean(),
        (id, organs, delta, tamper) => {
          const receipt = buildKhipuReceipt(id, organs);
          const r = tamper && delta > 0
            ? { ...receipt, primaryCord: receipt.primaryCord + delta }
            : receipt;
          const result = summationInvariant(r);
          return result.lambdaScore === (result.invariantHolds ? 1 : 0);
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 5: pendantValues.length = organs.length
  it("P5: pendantValues.length = organs.length", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 8 }),
        arbOrgans(),
        (id, organs) => {
          const receipt = buildKhipuReceipt(id, organs);
          const result = summationInvariant(receipt);
          return result.pendantValues.length === organs.length;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 6: pendantValues[i] = sum of decisions in organ i
  it("P6: pendantValues[i] = sum of leaf values in organ i", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 8 }),
        arbOrgans(),
        (id, organs) => {
          const receipt = buildKhipuReceipt(id, organs);
          const result = summationInvariant(receipt);
          return result.pendantValues.every(
            (pv, i) => pv === organs[i].decisions.reduce((s, d) => s + d.value, 0)
          );
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Deterministic spot checks
  describe("spot checks", () => {
    it("empty khipu: primaryCord=0, invariantHolds=true", () => {
      const r = buildKhipuReceipt("k0", []);
      const result = summationInvariant(r);
      expect(result.invariantHolds).toBe(true);
      expect(result.computedTotal).toBe(0);
    });

    it("single organ, single decision: total = value", () => {
      const organs: OrganReceipt[] = [
        { organId: "o1", decisions: [{ decisionId: "d1", value: 42 }] },
      ];
      const r = buildKhipuReceipt("k1", organs);
      const result = summationInvariant(r);
      expect(result.computedTotal).toBe(42);
      expect(result.invariantHolds).toBe(true);
    });

    it("two organs: pendant and root sums correct", () => {
      const organs: OrganReceipt[] = [
        { organId: "o1", decisions: [{ decisionId: "d1", value: 10 }, { decisionId: "d2", value: 20 }] },
        { organId: "o2", decisions: [{ decisionId: "d3", value: 5 }] },
      ];
      const r = buildKhipuReceipt("k2", organs);
      const result = summationInvariant(r);
      expect(result.pendantValues).toEqual([30, 5]);
      expect(result.computedTotal).toBe(35);
      expect(result.invariantHolds).toBe(true);
    });

    it("tampered primaryCord breaks invariant", () => {
      const r = buildKhipuReceipt("k3", [
        { organId: "o1", decisions: [{ decisionId: "d1", value: 100 }] },
      ]);
      const tampered = { ...r, primaryCord: r.primaryCord + 1 };
      expect(summationInvariant(tampered).invariantHolds).toBe(false);
    });
  });
});
