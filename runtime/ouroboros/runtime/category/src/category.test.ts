// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Tests: ouroboros/category — TH4

import { describe, it, expect } from "vitest";
import {
  morphism,
  identityMorphism,
  composeMorphisms,
  assertFunctorLaws,
  validateMorphismEndpoint,
  type FunctorMap,
} from "./category.js";
import { parseReceipt, type Receipt, type Axes } from "@szl/ouroboros-types";

const H1 = "a".repeat(64);
const H2 = "b".repeat(64);
const H3 = "c".repeat(64);

const GOOD_AXES: Axes = {
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

const makeReceipt = (hash: string): Receipt =>
  parseReceipt({
    hash,
    timestamp:   "2026-05-16T00:00:00.000Z",
    lambda:      0.92,
    axes:        GOOD_AXES,
    payloadRef:  `test:${hash.slice(0, 4)}`,
    doctrineVer: "6",
  });

const R1 = makeReceipt(H1);

describe("identityMorphism", () => {
  it("domain == codomain", () => {
    const id = identityMorphism(R1);
    expect(id.domain).toBe(id.codomain);
    expect(id.label).toBe("id");
  });

  it("id morphism has stable hash", () => {
    const a = identityMorphism(R1);
    const b = identityMorphism(R1);
    expect(a.id).toBe(b.id);
  });
});

describe("composeMorphisms", () => {
  const f = morphism(H1, H2, "f");
  const g = morphism(H2, H3, "g");

  it("composes f then g to produce A→C", () => {
    const result = composeMorphisms(f, g);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.morphism.domain).toBe(H1);
      expect(result.morphism.codomain).toBe(H3);
    }
  });

  it("fails on boundary mismatch", () => {
    const mismatched = morphism(H3, H1, "h");
    const result = composeMorphisms(f, mismatched);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.kind).toBe("boundary_mismatch");
    }
  });

  it("composition is associative: (h∘g)∘f == h∘(g∘f)", () => {
    const h = morphism(H3, "d".repeat(64), "h");
    const gf  = composeMorphisms(f, g);
    const hg  = composeMorphisms(g, h);
    expect(gf.ok).toBe(true);
    expect(hg.ok).toBe(true);
    if (gf.ok && hg.ok) {
      const left  = composeMorphisms(gf.morphism, h);
      const right = composeMorphisms(f, hg.morphism);
      expect(left.ok).toBe(true);
      expect(right.ok).toBe(true);
      if (left.ok && right.ok) {
        // Domain and codomain must agree
        expect(left.morphism.domain).toBe(right.morphism.domain);
        expect(left.morphism.codomain).toBe(right.morphism.codomain);
      }
    }
  });
});

describe("functor laws", () => {
  // Identity functor (trivial) satisfies all laws
  const F: FunctorMap = {
    mapObject: (h) => h,
    mapMorphism: (m) => m,
  };

  it("identity law holds for identity functor", () => {
    const f = morphism(H1, H2, "f");
    const g = morphism(H2, H3, "g");
    const result = assertFunctorLaws(F, R1, f, g);
    expect(result.identityLaw).toBe(true);
  });

  it("composition law holds for identity functor", () => {
    const f = morphism(H1, H2, "f");
    const g = morphism(H2, H3, "g");
    const result = assertFunctorLaws(F, R1, f, g);
    expect(result.compositionLaw).toBe(true);
  });
});

describe("validateMorphismEndpoint", () => {
  it("passes for receipt with good axes", () => {
    expect(validateMorphismEndpoint(R1)).toBe(true);
  });

  it("fails for receipt with bad axes", () => {
    const bad = makeReceipt(H2.replace(/b/g, "e"));
    // Override axes via fresh parse with bad values
    const badR = parseReceipt({
      hash:        "e".repeat(64),
      timestamp:   "2026-05-16T00:00:00.000Z",
      lambda:      0.50,
      axes:        { ...GOOD_AXES, moralGrounding: 0.50 },
      payloadRef:  "test:bad",
      doctrineVer: "6",
    });
    expect(validateMorphismEndpoint(badR)).toBe(false);
  });
});
