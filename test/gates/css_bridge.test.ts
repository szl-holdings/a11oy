/**
 * css_bridge.test.ts
 *
 * Vitest tests for the Lutar.QEC.CSS (CSSBridge) gate.
 *
 * Tests:
 *   1. 1000-input random consistency check — verifies X ⊕ Z = 0xFF for all codewords
 *   2. Injectivity: 1000-pair random tests
 *   3. Edge cases: 0x00, 0xFF, 0x55, 0xAA
 *   4. Receipt emission with mock signer
 *
 * Lean commit: c4d13795689601324fce0236351bfe0ade990a43
 */

import { describe, it, expect } from "vitest";
import {
  classicalToCSS,
  consistent,
  verifyBridgeInjective,
  emitCSSBridgeReceipt,
  cssBridgeGate,
  type Signer,
} from "../../src/gates/css_bridge";

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
// 1. 1000-input random consistency test
// ---------------------------------------------------------------------------

describe("css_bridge: 1000-input random consistency (css_bridge_consistent)", () => {
  it("consistent(classicalToCSS(c)) = true for 1000 random codewords", () => {
    const rand = seedRandom(0xfeedface);
    let inconsistencies = 0;

    for (let i = 0; i < 1000; i++) {
      const codeword = Math.floor(rand() * 256);
      const pair = classicalToCSS(codeword);
      if (!consistent(pair)) inconsistencies++;
    }

    expect(inconsistencies).toBe(0);
  });

  it("X ⊕ Z = 0xFF for every codeword in [0, 255] (exhaustive)", () => {
    let failures = 0;
    for (let c = 0; c <= 255; c++) {
      const pair = classicalToCSS(c);
      if ((pair.xParity ^ pair.zParity) !== 0xff) failures++;
    }
    expect(failures).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 2. Injectivity tests
// ---------------------------------------------------------------------------

describe("css_bridge: injectivity (css_bridge_injective)", () => {
  it("distinct codewords yield distinct pairs for 1000 random pairs", () => {
    const rand = seedRandom(0x01234567);
    let colisions = 0;

    for (let i = 0; i < 1000; i++) {
      const a = Math.floor(rand() * 256);
      let b = Math.floor(rand() * 256);
      if (b === a) b = (b + 1) % 256;
      if (!verifyBridgeInjective(a, b)) colisions++;
    }

    expect(colisions).toBe(0);
  });

  it("verifyBridgeInjective(a, a) is trivially true", () => {
    expect(verifyBridgeInjective(0x42, 0x42)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 3. Edge cases
// ---------------------------------------------------------------------------

describe("css_bridge: edge cases", () => {
  it("classicalToCSS(0x00) = { xParity: 0x00, zParity: 0xFF }", () => {
    const pair = classicalToCSS(0x00);
    expect(pair.xParity).toBe(0x00);
    expect(pair.zParity).toBe(0xff);
    expect(consistent(pair)).toBe(true);
  });

  it("classicalToCSS(0xFF) = { xParity: 0xFF, zParity: 0x00 }", () => {
    const pair = classicalToCSS(0xff);
    expect(pair.xParity).toBe(0xff);
    expect(pair.zParity).toBe(0x00);
    expect(consistent(pair)).toBe(true);
  });

  it("classicalToCSS(0x55) is consistent", () => {
    const pair = classicalToCSS(0x55);
    expect(pair.zParity).toBe(0xaa);
    expect(consistent(pair)).toBe(true);
  });

  it("inconsistent pair: { xParity: 0, zParity: 0 } → consistent = false", () => {
    expect(consistent({ xParity: 0, zParity: 0 })).toBe(false);
  });

  it("throws on codeword out of [0,255] range", () => {
    expect(() => classicalToCSS(-1)).toThrow();
    expect(() => classicalToCSS(256)).toThrow();
    expect(() => classicalToCSS(1.5)).toThrow();
  });
});

// ---------------------------------------------------------------------------
// 4. Receipt emission
// ---------------------------------------------------------------------------

describe("css_bridge: DSSE receipt emission", () => {
  it("emits receipt with correct theorem and commit SHA", () => {
    const { pair, receipt } = emitCSSBridgeReceipt(0xab, mockSigner);
    expect(receipt.theorem).toBe("Lutar.QEC.CSS.css_bridge_consistent");
    expect(receipt.lean_commit_sha).toBe("c4d13795689601324fce0236351bfe0ade990a43");
    expect(receipt.output).toBe(true);
    expect(pair.xParity).toBe(0xab);
    expect(pair.zParity).toBe(0x54);
  });

  it("receipt output matches consistent(classicalToCSS(c)) for 50 random codewords", () => {
    const rand = seedRandom(0x99aabbcc);
    for (let i = 0; i < 50; i++) {
      const c = Math.floor(rand() * 256);
      const { receipt } = emitCSSBridgeReceipt(c, mockSigner);
      expect(receipt.output).toBe(true); // Lean theorem: always consistent
    }
  });

  it("gate returns pair, consistent=true, and receipt", () => {
    const { pair, consistent: cons, receipt } = cssBridgeGate(0x42, mockSigner);
    expect(cons).toBe(true);
    expect(pair.xParity).toBe(0x42);
    expect(receipt.output).toBe(true);
  });

  it("inputs_hash is deterministic for the same codeword", () => {
    const r1 = emitCSSBridgeReceipt(0x77, mockSigner);
    const r2 = emitCSSBridgeReceipt(0x77, mockSigner);
    expect(r1.receipt.inputs_hash).toBe(r2.receipt.inputs_hash);
  });

  it("inputs_hash differs for different codewords", () => {
    const r1 = emitCSSBridgeReceipt(0x10, mockSigner);
    const r2 = emitCSSBridgeReceipt(0x20, mockSigner);
    expect(r1.receipt.inputs_hash).not.toBe(r2.receipt.inputs_hash);
  });
});
