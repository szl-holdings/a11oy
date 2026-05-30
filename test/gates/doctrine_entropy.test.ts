/**
 * doctrine_entropy.test.ts
 *
 * Vitest tests for the Lutar.Shannon.DoctrineEntropy gate.
 *
 * Tests:
 *   1. 1000-input random channel-rate bound test
 *   2. Encoder/decoder round-trip for all labels
 *   3. Kraft inequality at equality
 *   4. Receipt emission with mock signer
 *
 * Lean commit: c4d13795689601324fce0236351bfe0ade990a43
 */

import { describe, it, expect } from "vitest";
import {
  shannonCode,
  shannonDecode,
  verifyRoundtrip,
  verifyCodeIn2Bits,
  verifyKraftEquality,
  channelRateBound,
  emitDoctrineEntropyReceipt,
  doctrineEntropyGate,
  ALL_LABELS,
  DOCTRINE_ALPHABET_SIZE,
  DOCTRINE_CODEWORD_LENGTH,
  type DoctrineLabel,
  type Signer,
} from "../../src/gates/doctrine_entropy";

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

// ---------------------------------------------------------------------------
// 1. 1000-input random channel-rate bound test
// ---------------------------------------------------------------------------

describe("doctrine_entropy: 1000-input channel rate bound test", () => {
  it("channelRateBound(B, rate) = true iff rate * 2 ≤ B for 1000 random pairs", () => {
    const rand = seedRandom(0x55667788);
    let failures = 0;

    for (let i = 0; i < 1000; i++) {
      const B = Math.floor(rand() * 10000);
      const rate = Math.floor(rand() * 10000);
      const expected = rate * DOCTRINE_CODEWORD_LENGTH <= B;
      if (channelRateBound(B, rate) !== expected) failures++;
    }

    expect(failures).toBe(0);
  });

  it("channelRateBound: rate = 0 is always admissible", () => {
    const rand = seedRandom(0x11111111);
    for (let i = 0; i < 1000; i++) {
      const B = Math.floor(rand() * 10000);
      expect(channelRateBound(B, 0)).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// 2. Encoder/decoder round-trip
// ---------------------------------------------------------------------------

describe("doctrine_entropy: encoder/decoder round-trip", () => {
  it("verifyRoundtrip() is true", () => {
    expect(verifyRoundtrip()).toBe(true);
  });

  it("shannonDecode(shannonCode(l)) = l for all labels", () => {
    for (const label of ALL_LABELS) {
      expect(shannonDecode(shannonCode(label))).toBe(label);
    }
  });

  it("shannonCode produces distinct values for distinct labels", () => {
    const codes = new Set(ALL_LABELS.map(shannonCode));
    expect(codes.size).toBe(DOCTRINE_ALPHABET_SIZE);
  });

  it("shannonDecode returns null for codewords ≥ 4", () => {
    expect(shannonDecode(4)).toBeNull();
    expect(shannonDecode(99)).toBeNull();
    expect(shannonDecode(-1)).toBeNull();
  });

  it("shannonCode(Bot)=0, L1=1, L2=2, Top=3", () => {
    expect(shannonCode("Bot")).toBe(0);
    expect(shannonCode("L1")).toBe(1);
    expect(shannonCode("L2")).toBe(2);
    expect(shannonCode("Top")).toBe(3);
  });
});

// ---------------------------------------------------------------------------
// 3. Kraft inequality at equality
// ---------------------------------------------------------------------------

describe("doctrine_entropy: Kraft inequality (kraft_inequality_doctrine)", () => {
  it("verifyKraftEquality() is true", () => {
    expect(verifyKraftEquality()).toBe(true);
  });

  it("alphabet has exactly 4 elements (doctrine_alphabet_size_4)", () => {
    expect(ALL_LABELS.length).toBe(DOCTRINE_ALPHABET_SIZE);
  });

  it("all codewords fit in 2 bits (shannon_code_in_2_bits)", () => {
    expect(verifyCodeIn2Bits()).toBe(true);
    for (const label of ALL_LABELS) {
      expect(shannonCode(label)).toBeGreaterThanOrEqual(0);
      expect(shannonCode(label)).toBeLessThan(4);
    }
  });

  it("codeword length is uniformly 2 (doctrine_uniform_code_length_2_bits)", () => {
    // All labels map to codewords fitting in 2 bits
    for (const label of ALL_LABELS) {
      expect(shannonCode(label) < 4).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// 4. Receipt emission
// ---------------------------------------------------------------------------

describe("doctrine_entropy: DSSE receipt emission", () => {
  it("emits receipt with correct theorem and commit SHA", () => {
    const receipt = emitDoctrineEntropyReceipt(mockSigner);
    expect(receipt.theorem).toBe(
      "Lutar.Shannon.doctrine_uniform_code_length_2_bits"
    );
    expect(receipt.lean_commit_sha).toBe("c4d13795689601324fce0236351bfe0ade990a43");
    expect(receipt.output).toBe(true);
    expect(receipt.inputs_hash).toMatch(/^[0-9a-f]{64}$/);
    expect(receipt.sig).toContain("mock-sig::");
  });

  it("receipt is deterministic (same inputs_hash across calls)", () => {
    const r1 = emitDoctrineEntropyReceipt(mockSigner);
    const r2 = emitDoctrineEntropyReceipt(mockSigner);
    expect(r1.inputs_hash).toBe(r2.inputs_hash);
    expect(r1.output).toBe(r2.output);
  });

  it("gate returns alphabetSize=4, codewordLength=2, kraftEqualityHolds=true", () => {
    const result = doctrineEntropyGate(mockSigner);
    expect(result.alphabetSize).toBe(4);
    expect(result.codewordLength).toBe(2);
    expect(result.kraftEqualityHolds).toBe(true);
    expect(result.receipt.output).toBe(true);
  });
});
