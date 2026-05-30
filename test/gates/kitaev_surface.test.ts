/**
 * kitaev_surface.test.ts
 *
 * Vitest tests for the Lutar.QEC.Kitaev (KitaevSurface) gate.
 *
 * Tests:
 *   1. 1000-input random parity check — single-site error always produces odd parity
 *   2. No-error and all-error edge cases (zero parity)
 *   3. Weight-2 / weight-4 error patterns
 *   4. Receipt emission with mock signer
 *
 * Lean commit: c4d13795689601324fce0236351bfe0ade990a43
 */

import { describe, it, expect } from "vitest";
import {
  vertexParity,
  detectSyndromes,
  singleSiteError,
  emitKitaevSurfaceReceipt,
  kitaevSurfaceGate,
  siteKey,
  type Site,
  type VertexCheck,
  type ErrorMap,
  type Signer,
} from "../../src/gates/kitaev_surface";

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
// Helper: build a vertex check from 4 sites
// ---------------------------------------------------------------------------

function makeVertex(
  na: number, ns: number,
  sa: number, ss: number,
  ea: number, es: number,
  wa: number, ws: number
): VertexCheck {
  return {
    n: { agent: na, slice: ns },
    s: { agent: sa, slice: ss },
    e: { agent: ea, slice: es },
    w: { agent: wa, slice: ws },
  };
}

const V0 = makeVertex(0, 0, 0, 1, 1, 0, 0, 2);

// ---------------------------------------------------------------------------
// 1. 1000-input random: single-site error flips parity
// ---------------------------------------------------------------------------

describe("kitaev_surface: 1000-input single-site error parity test", () => {
  it("single north-site error yields parity = true for 1000 random vertices", () => {
    const rand = seedRandom(0x11223344);
    let failures = 0;

    for (let i = 0; i < 1000; i++) {
      const na = Math.floor(rand() * 100);
      const ns = Math.floor(rand() * 100);
      const v = makeVertex(
        na, ns,
        na, ns + 1,
        na + 1, ns,
        na, ns + 2
      );
      const errors = singleSiteError(v.n);
      const parity = vertexParity(errors, v);
      if (!parity) failures++;
    }

    expect(failures).toBe(0);
  });

  it("single south-site error yields parity = true for 1000 random vertices", () => {
    const rand = seedRandom(0xaabbccdd);
    let failures = 0;

    for (let i = 0; i < 1000; i++) {
      const a = Math.floor(rand() * 100);
      const s = Math.floor(rand() * 100);
      const v = makeVertex(a, s, a + 1, s, a, s + 1, a, s + 2);
      const errors = singleSiteError(v.s);
      if (!vertexParity(errors, v)) failures++;
    }

    expect(failures).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 2. Edge cases: no-error, all-error
// ---------------------------------------------------------------------------

describe("kitaev_surface: edge cases", () => {
  it("no errors → parity = false (kitaev_no_errors_zero_parity)", () => {
    expect(vertexParity(new Map(), V0)).toBe(false);
  });

  it("all 4 sites corrupted → parity = false (kitaev_all_errors_zero_parity)", () => {
    const errors: ErrorMap = new Map();
    errors.set(siteKey(V0.n), true);
    errors.set(siteKey(V0.s), true);
    errors.set(siteKey(V0.e), true);
    errors.set(siteKey(V0.w), true);
    expect(vertexParity(errors, V0)).toBe(false);
  });

  it("weight-2 error (n and s) → parity = false", () => {
    const errors: ErrorMap = new Map();
    errors.set(siteKey(V0.n), true);
    errors.set(siteKey(V0.s), true);
    expect(vertexParity(errors, V0)).toBe(false);
  });

  it("weight-3 error (n, s, e) → parity = true", () => {
    const errors: ErrorMap = new Map();
    errors.set(siteKey(V0.n), true);
    errors.set(siteKey(V0.s), true);
    errors.set(siteKey(V0.e), true);
    expect(vertexParity(errors, V0)).toBe(true);
  });

  it("single east-site error → parity = true", () => {
    const errors = singleSiteError(V0.e);
    expect(vertexParity(errors, V0)).toBe(true);
  });

  it("single west-site error → parity = true", () => {
    const errors = singleSiteError(V0.w);
    expect(vertexParity(errors, V0)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 3. detectSyndromes
// ---------------------------------------------------------------------------

describe("kitaev_surface: detectSyndromes", () => {
  const V1 = makeVertex(5, 0, 5, 1, 6, 0, 5, 2);
  const V2 = makeVertex(10, 0, 10, 1, 11, 0, 10, 2);

  it("no errors → no syndromes detected", () => {
    const syndromes = detectSyndromes([V0, V1, V2], new Map());
    expect(syndromes.length).toBe(0);
  });

  it("single error on V0.n → exactly one syndrome at V0", () => {
    const errors = singleSiteError(V0.n);
    const syndromes = detectSyndromes([V0, V1, V2], errors);
    expect(syndromes.length).toBe(1);
    expect(syndromes[0]).toEqual(V0);
  });
});

// ---------------------------------------------------------------------------
// 4. Receipt emission
// ---------------------------------------------------------------------------

describe("kitaev_surface: DSSE receipt emission", () => {
  it("single-site error emits receipt with output = true (syndrome detected)", () => {
    const { parity, receipt } = emitKitaevSurfaceReceipt(V0, [V0.n], mockSigner);
    expect(parity).toBe(true);
    expect(receipt.output).toBe(true);
    expect(receipt.theorem).toBe(
      "Lutar.QEC.Kitaev.kitaev_single_site_flips_parity_n"
    );
    expect(receipt.lean_commit_sha).toBe("c4d13795689601324fce0236351bfe0ade990a43");
    expect(receipt.inputs_hash).toMatch(/^[0-9a-f]{64}$/);
  });

  it("no errors emits receipt with output = false (no syndrome)", () => {
    const { parity, receipt } = emitKitaevSurfaceReceipt(V0, [], mockSigner);
    expect(parity).toBe(false);
    expect(receipt.output).toBe(false);
  });

  it("gate returns hasSyndrome correctly", () => {
    const { hasSyndrome, receipt } = kitaevSurfaceGate(V0, [V0.s], mockSigner);
    expect(hasSyndrome).toBe(true);
    expect(receipt.output).toBe(true);
  });

  it("deterministic inputs_hash for same vertex + error sites", () => {
    const r1 = emitKitaevSurfaceReceipt(V0, [V0.n], mockSigner);
    const r2 = emitKitaevSurfaceReceipt(V0, [V0.n], mockSigner);
    expect(r1.receipt.inputs_hash).toBe(r2.receipt.inputs_hash);
  });

  it("different error patterns yield different inputs_hash", () => {
    const r1 = emitKitaevSurfaceReceipt(V0, [V0.n], mockSigner);
    const r2 = emitKitaevSurfaceReceipt(V0, [V0.s], mockSigner);
    expect(r1.receipt.inputs_hash).not.toBe(r2.receipt.inputs_hash);
  });
});
