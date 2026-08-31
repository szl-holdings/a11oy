/**
 * th1_composition.test.ts
 *
 * Vitest tests for the Lutar.Composition.TH1_Composition gate.
 *
 * Tests:
 *   1. 1000-input random doctrine preservation test
 *   2. Lattice order (labelLE) edge cases
 *   3. Compatible / incompatible system pairs
 *   4. composeList across all label combinations
 *   5. Receipt emission with mock signer
 *
 * Lean commit: c4d13795689601324fce0236351bfe0ade990a43
 */

import { describe, it, expect } from "vitest";
import {
  labelLE,
  doctrinePredicate,
  isDoctrineLockedSystem,
  compatible,
  compose,
  composeList,
  verifyCompositionPreservesDoctrine,
  emitTH1CompositionReceipt,
  th1CompositionGate,
  type LutarSystem,
  type DoctrineLabel,
  type Signer,
} from "../../src/gates/th1_composition";

// ---------------------------------------------------------------------------
// Seeded LCG
// ---------------------------------------------------------------------------

function seedRandom(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0;
    return s / 0x100000000;
  };
}

const LABELS: DoctrineLabel[] = ["Bot", "L1", "L2", "Top"];

function pickLabel(rand: () => number): DoctrineLabel {
  return LABELS[Math.floor(rand() * 4)];
}

const mockSigner: Signer = (p: string) =>
  `mock-sig::${Buffer.from(p).slice(0, 16).toString("hex")}`;

// ---------------------------------------------------------------------------
// 1. 1000-input random doctrine preservation test
// ---------------------------------------------------------------------------

describe("th1_composition: 1000-input random composition_preserves_doctrine", () => {
  it("composed system is doctrine-locked for all valid compatible pairs", () => {
    const rand = seedRandom(0xabcdef12);
    let failures = 0;

    for (let i = 0; i < 1000; i++) {
      const th = pickLabel(rand);

      // Build valid S1: threshold ≤ inputLabel ≤ outputLabel, threshold ≤ outputLabel
      const thRank = ["Bot", "L1", "L2", "Top"].indexOf(th);
      const validLabels = LABELS.slice(thRank); // all labels ≥ th
      if (validLabels.length < 2) continue;

      const inLabel1 = validLabels[Math.floor(rand() * validLabels.length)];
      const inRank1 = LABELS.indexOf(inLabel1);
      const validOut1 = LABELS.slice(Math.max(inRank1, thRank));
      const outLabel1 = validOut1[Math.floor(rand() * validOut1.length)];

      // S2 must have inputLabel ≥ outLabel1
      const s2MinInRank = LABELS.indexOf(outLabel1);
      const validIn2 = LABELS.slice(Math.max(s2MinInRank, thRank));
      if (validIn2.length === 0) continue;
      const inLabel2 = validIn2[Math.floor(rand() * validIn2.length)];
      const inRank2 = LABELS.indexOf(inLabel2);
      const validOut2 = LABELS.slice(Math.max(inRank2, thRank));
      const outLabel2 = validOut2[Math.floor(rand() * validOut2.length)];

      const s1: LutarSystem = { threshold: th, inputLabel: inLabel1, outputLabel: outLabel1 };
      const s2: LutarSystem = { threshold: th, inputLabel: inLabel2, outputLabel: outLabel2 };

      if (!verifyCompositionPreservesDoctrine(s1, s2)) failures++;
    }

    expect(failures).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 2. Lattice order (labelLE) edge cases
// ---------------------------------------------------------------------------

describe("th1_composition: labelLE lattice order", () => {
  it("labelLE is reflexive", () => {
    for (const l of LABELS) {
      expect(labelLE(l, l)).toBe(true);
    }
  });

  it("labelLE is transitive", () => {
    const pairs: [DoctrineLabel, DoctrineLabel, DoctrineLabel][] = [
      ["Bot", "L1", "L2"],
      ["Bot", "L1", "Top"],
      ["Bot", "L2", "Top"],
      ["L1", "L2", "Top"],
    ];
    for (const [a, b, c] of pairs) {
      expect(labelLE(a, b) && labelLE(b, c) && labelLE(a, c)).toBe(true);
    }
  });

  it("Bot ≤ everything", () => {
    for (const l of LABELS) expect(labelLE("Bot", l)).toBe(true);
  });

  it("everything ≤ Top", () => {
    for (const l of LABELS) expect(labelLE(l, "Top")).toBe(true);
  });

  it("L2 > L1 (not L2 ≤ L1)", () => {
    expect(labelLE("L2", "L1")).toBe(false);
  });

  it("Top > L2 (not Top ≤ L2)", () => {
    expect(labelLE("Top", "L2")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 3. Compatible / incompatible system pairs
// ---------------------------------------------------------------------------

describe("th1_composition: compatible and compose", () => {
  it("compatible: L1 output → L1 input → true", () => {
    const s1: LutarSystem = { threshold: "Bot", inputLabel: "Bot", outputLabel: "L1" };
    const s2: LutarSystem = { threshold: "Bot", inputLabel: "L1", outputLabel: "L2" };
    expect(compatible(s1, s2)).toBe(true);
  });

  it("incompatible: L2 output → L1 input → false", () => {
    const s1: LutarSystem = { threshold: "Bot", inputLabel: "Bot", outputLabel: "L2" };
    const s2: LutarSystem = { threshold: "Bot", inputLabel: "L1", outputLabel: "L2" };
    expect(compatible(s1, s2)).toBe(false);
  });

  it("compose produces correct input/output labels", () => {
    const s1: LutarSystem = { threshold: "L1", inputLabel: "L1", outputLabel: "L2" };
    const s2: LutarSystem = { threshold: "L1", inputLabel: "L2", outputLabel: "Top" };
    const result = compose(s1, s2);
    expect(result.inputLabel).toBe("L1");
    expect(result.outputLabel).toBe("Top");
    expect(result.threshold).toBe("L1");
  });

  it("compose throws on threshold mismatch", () => {
    const s1: LutarSystem = { threshold: "L1", inputLabel: "L1", outputLabel: "L2" };
    const s2: LutarSystem = { threshold: "L2", inputLabel: "L2", outputLabel: "Top" };
    expect(() => compose(s1, s2)).toThrow("threshold mismatch");
  });

  it("compose throws when incompatible (output > input)", () => {
    const s1: LutarSystem = { threshold: "Bot", inputLabel: "Bot", outputLabel: "L2" };
    const s2: LutarSystem = { threshold: "Bot", inputLabel: "L1", outputLabel: "L2" };
    expect(() => compose(s1, s2)).toThrow("incompatible");
  });
});

// ---------------------------------------------------------------------------
// 4. composeList
// ---------------------------------------------------------------------------

describe("th1_composition: composeList", () => {
  it("composeList of single system returns it unchanged", () => {
    const s: LutarSystem = { threshold: "L1", inputLabel: "L1", outputLabel: "L2" };
    const result = composeList([s]);
    expect(result).toEqual(s);
  });

  it("composeList of chain [Bot→L1] → [L1→L2] → [L2→Top]", () => {
    const chain: LutarSystem[] = [
      { threshold: "Bot", inputLabel: "Bot", outputLabel: "L1" },
      { threshold: "Bot", inputLabel: "L1", outputLabel: "L2" },
      { threshold: "Bot", inputLabel: "L2", outputLabel: "Top" },
    ];
    const result = composeList(chain);
    expect(result.inputLabel).toBe("Bot");
    expect(result.outputLabel).toBe("Top");
    expect(isDoctrineLockedSystem(result)).toBe(true);
  });

  it("composeList throws on empty list", () => {
    expect(() => composeList([])).toThrow("empty list");
  });
});

// ---------------------------------------------------------------------------
// 5. Receipt emission
// ---------------------------------------------------------------------------

describe("th1_composition: DSSE receipt emission", () => {
  const s1: LutarSystem = { threshold: "L1", inputLabel: "L1", outputLabel: "L2" };
  const s2: LutarSystem = { threshold: "L1", inputLabel: "L2", outputLabel: "Top" };

  it("emits receipt with correct theorem and commit SHA", () => {
    const receipt = emitTH1CompositionReceipt(s1, s2, mockSigner);
    expect(receipt.theorem).toBe(
      "Lutar.Composition.composition_preserves_doctrine"
    );
    expect(receipt.lean_commit_sha).toBe("c4d13795689601324fce0236351bfe0ade990a43");
    expect(receipt.output).toBe(true);
    expect(receipt.inputs_hash).toMatch(/^[0-9a-f]{64}$/);
    expect(receipt.sig).toContain("mock-sig::");
  });

  it("receipt output = false for incompatible systems", () => {
    const bad: LutarSystem = { threshold: "L1", inputLabel: "L1", outputLabel: "L1" };
    const incompatible: LutarSystem = { threshold: "L1", inputLabel: "L2", outputLabel: "Top" };
    const receipt = emitTH1CompositionReceipt(bad, incompatible, mockSigner);
    expect(receipt.output).toBe(false);
  });

  it("gate returns composedSystem and doctrinePreserved=true", () => {
    const { composedSystem, doctrinePreserved, receipt } = th1CompositionGate(s1, s2, mockSigner);
    expect(composedSystem).not.toBeNull();
    expect(composedSystem?.inputLabel).toBe("L1");
    expect(composedSystem?.outputLabel).toBe("Top");
    expect(doctrinePreserved).toBe(true);
    expect(receipt.output).toBe(true);
  });

  it("deterministic inputs_hash", () => {
    const r1 = emitTH1CompositionReceipt(s1, s2, mockSigner);
    const r2 = emitTH1CompositionReceipt(s1, s2, mockSigner);
    expect(r1.inputs_hash).toBe(r2.inputs_hash);
  });
});
