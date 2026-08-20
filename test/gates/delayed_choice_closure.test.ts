/**
 * delayed_choice_closure.test.ts
 *
 * Vitest tests for the Lutar.Wheeler.DelayedChoiceClosure gate.
 *
 * Tests:
 *   1. 1000-input random admissibility parity test
 *   2. Edge cases: exact window, late, early, wrong span
 *   3. closeLabel semantics
 *   4. Receipt emission with mock signer
 *
 * Lean commit: c4d13795689601324fce0236351bfe0ade990a43
 */

import { describe, it, expect } from "vitest";
import {
  admissible,
  closeLabel,
  emitDelayedChoiceReceipt,
  delayedChoiceClosureGate,
  WHEELER_WINDOW,
  type Span,
  type WheelerReceipt,
  type DoctrineLabel,
  type Signer,
} from "../../src/gates/delayed_choice_closure";

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

const mockSigner: Signer = (p: string) =>
  `mock-sig::${Buffer.from(p).slice(0, 16).toString("hex")}`;

const LABELS: DoctrineLabel[] = ["Bot", "L1", "L2", "Top"];

// ---------------------------------------------------------------------------
// 1. 1000-input random admissibility test
// ---------------------------------------------------------------------------

describe("delayed_choice_closure: 1000-input admissibility parity test", () => {
  it("late receipts (closeAt > endAt + W) always inadmissible", () => {
    const rand = seedRandom(0xcafe0001);
    let violations = 0;

    for (let i = 0; i < 1000; i++) {
      const endAt = Math.floor(rand() * 10000);
      const span: Span = { id: 1, start: 0, endAt };
      const closeAt = endAt + WHEELER_WINDOW + Math.floor(rand() * 5000) + 1;
      const receipt: WheelerReceipt = { span: 1, closeAt, label: "L1" };
      if (admissible(span, receipt)) violations++;
    }

    expect(violations).toBe(0);
  });

  it("receipts inside window always admissible (same span)", () => {
    const rand = seedRandom(0xcafe0002);
    let violations = 0;

    for (let i = 0; i < 1000; i++) {
      const endAt = Math.floor(rand() * 10000);
      const span: Span = { id: 42, start: 0, endAt };
      const offset = Math.floor(rand() * WHEELER_WINDOW); // [0, W-1]
      const receipt: WheelerReceipt = { span: 42, closeAt: endAt + offset, label: "Top" };
      if (!admissible(span, receipt)) violations++;
    }

    expect(violations).toBe(0);
  });

  it("wrong-span receipts always inadmissible", () => {
    const rand = seedRandom(0xcafe0003);
    let violations = 0;

    for (let i = 0; i < 1000; i++) {
      const endAt = Math.floor(rand() * 10000);
      const span: Span = { id: 1, start: 0, endAt };
      const wrongId = Math.floor(rand() * 1000) + 2; // never 1
      const receipt: WheelerReceipt = { span: wrongId, closeAt: endAt + 1, label: "L2" };
      if (admissible(span, receipt)) violations++;
    }

    expect(violations).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 2. Edge cases
// ---------------------------------------------------------------------------

describe("delayed_choice_closure: edge cases", () => {
  const span: Span = { id: 7, start: 100, endAt: 200 };

  it("receipt at exact endAt → admissible (wheeler_window_admits_zero_offset)", () => {
    const r: WheelerReceipt = { span: 7, closeAt: 200, label: "L1" };
    expect(admissible(span, r)).toBe(true);
  });

  it("receipt at endAt + W → admissible (wheeler_window_admits_max_offset)", () => {
    const r: WheelerReceipt = { span: 7, closeAt: 200 + WHEELER_WINDOW, label: "L2" };
    expect(admissible(span, r)).toBe(true);
  });

  it("receipt at endAt + W + 1 → inadmissible (wheeler_window_safety)", () => {
    const r: WheelerReceipt = { span: 7, closeAt: 200 + WHEELER_WINDOW + 1, label: "L2" };
    expect(admissible(span, r)).toBe(false);
  });

  it("early receipt (closeAt < endAt) → inadmissible (early_receipt_rejected)", () => {
    const r: WheelerReceipt = { span: 7, closeAt: 150, label: "Top" };
    expect(admissible(span, r)).toBe(false);
  });

  it("closeAt = 0, endAt = 200 → inadmissible", () => {
    const r: WheelerReceipt = { span: 7, closeAt: 0, label: "Bot" };
    expect(admissible(span, r)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 3. closeLabel semantics
// ---------------------------------------------------------------------------

describe("delayed_choice_closure: closeLabel semantics", () => {
  const span: Span = { id: 7, start: 100, endAt: 200 };

  it("admissible receipt → closeLabel = receipt.label", () => {
    for (const label of LABELS) {
      const r: WheelerReceipt = { span: 7, closeAt: 250, label };
      expect(closeLabel(span, r)).toBe(label);
    }
  });

  it("inadmissible (late) receipt → closeLabel = Bot (wheeler_window_safety)", () => {
    const r: WheelerReceipt = { span: 7, closeAt: 200 + WHEELER_WINDOW + 1, label: "Top" };
    expect(closeLabel(span, r)).toBe("Bot");
  });

  it("wrong span → closeLabel = Bot (wrong_span_rejected)", () => {
    const r: WheelerReceipt = { span: 99, closeAt: 250, label: "L2" };
    expect(closeLabel(span, r)).toBe("Bot");
  });

  it("delayed_choice_idempotent: closeLabel is referentially stable", () => {
    const r: WheelerReceipt = { span: 7, closeAt: 210, label: "L1" };
    expect(closeLabel(span, r)).toBe(closeLabel(span, r));
  });
});

// ---------------------------------------------------------------------------
// 4. Receipt emission
// ---------------------------------------------------------------------------

describe("delayed_choice_closure: DSSE receipt emission", () => {
  const span: Span = { id: 1, start: 0, endAt: 500 };

  it("admissible receipt emits correct DSSE receipt", () => {
    const r: WheelerReceipt = { span: 1, closeAt: 700, label: "L2" };
    const { label, dsse } = emitDelayedChoiceReceipt(span, r, mockSigner);
    expect(label).toBe("L2");
    expect(dsse.output).toBe("L2");
    expect(dsse.theorem).toBe("Lutar.Wheeler.delayed_choice_idempotent");
    expect(dsse.lean_commit_sha).toBe("c4d13795689601324fce0236351bfe0ade990a43");
    expect(dsse.inputs_hash).toMatch(/^[0-9a-f]{64}$/);
    expect(dsse.sig).toContain("mock-sig::");
  });

  it("late receipt → output = Bot in DSSE receipt", () => {
    const r: WheelerReceipt = { span: 1, closeAt: 500 + WHEELER_WINDOW + 1, label: "Top" };
    const { label, dsse } = emitDelayedChoiceReceipt(span, r, mockSigner);
    expect(label).toBe("Bot");
    expect(dsse.output).toBe("Bot");
  });

  it("gate returns admissible + label correctly", () => {
    const r: WheelerReceipt = { span: 1, closeAt: 600, label: "Top" };
    const { label, admissible: adm, dsse } = delayedChoiceClosureGate(span, r, mockSigner);
    expect(label).toBe("Top");
    expect(adm).toBe(true);
    expect(dsse.output).toBe("Top");
  });

  it("inputs_hash is deterministic", () => {
    const r: WheelerReceipt = { span: 1, closeAt: 600, label: "Top" };
    const r1 = emitDelayedChoiceReceipt(span, r, mockSigner);
    const r2 = emitDelayedChoiceReceipt(span, r, mockSigner);
    expect(r1.dsse.inputs_hash).toBe(r2.dsse.inputs_hash);
  });
});
