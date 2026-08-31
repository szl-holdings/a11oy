/**
 * art-domain.test.ts — Watunakuy compliance tests for ArtDomain branded type
 * Organ: sentra (LIVER / TOXIN FILTER)
 *
 * Watunakuy Four Strikes:
 *   Strike 1 (unit): 6 named tests covering happy path, rejection paths, edge cases
 *   Strike 3 (doctrine-grep): enforced in CI — 0 banned tokens in diff
 *   Strike 4 (property): N=100 deterministic LCG — validator matches spec exactly
 *
 * Strike 2 (integration) is N/A for a pure type-system / validation module
 * with no wire contracts. The existing INTEG-1 batch test in
 * dual-use-context-remediation.test.ts covers the end-to-end path; those
 * tests continue to pass because artDomain comparison in detectDualUse()
 * is string equality (ArtDomain extends string, no runtime difference).
 *
 * Doctrine v7 strict. Watunakuy active.
 * © 2026 SZL Holdings, Inc. — Apache-2.0
 */

import { describe, expect, it } from "vitest";
import { ArtDomain } from "../art-domain";

// ─── Strike 1 — Unit tests (6 minimum per Watunakuy) ─────────────────────────

describe("ArtDomain branded type — Strike 1: unit tests", () => {
  // ── Happy path ──────────────────────────────────────────────────────────────

  it("S1-01: ArtDomain.of('root_cutting') returns a branded value equal to 'root_cutting'", () => {
    const result = ArtDomain.of("root_cutting");
    expect(result).toBe("root_cutting");
    // The branded value is still a string at runtime.
    expect(typeof result).toBe("string");
  });

  // ── Rejection paths ─────────────────────────────────────────────────────────

  it("S1-02: ArtDomain.of('Root_Cutting') throws — uppercase letters not allowed", () => {
    expect(() => ArtDomain.of("Root_Cutting")).toThrow(
      /Invalid artDomain.*Root_Cutting/,
    );
  });

  it("S1-03: ArtDomain.of('rootcutting!') throws — special characters not allowed", () => {
    expect(() => ArtDomain.of("rootcutting!")).toThrow(
      /Invalid artDomain.*rootcutting!/,
    );
  });

  it("S1-04: ArtDomain.of('') throws — empty string is not a valid identifier", () => {
    expect(() => ArtDomain.of("")).toThrow(/Invalid artDomain/);
  });

  // ── Edge cases ───────────────────────────────────────────────────────────────

  it("S1-05: ArtDomain.of('  root_cutting  ') trims whitespace and accepts", () => {
    // Leading/trailing whitespace is stripped before the pattern check.
    const result = ArtDomain.of("  root_cutting  ");
    expect(result).toBe("root_cutting");
  });

  it("S1-06: ArtDomain.fromTrusted('root_cutting') bypasses validation and returns the value", () => {
    // fromTrusted is for registry hydration — it must not throw.
    const result = ArtDomain.fromTrusted("root_cutting");
    expect(result).toBe("root_cutting");
    expect(typeof result).toBe("string");
  });
});

// ─── Additional unit coverage (beyond Strike 1 minimum) ──────────────────────

describe("ArtDomain branded type — additional unit coverage", () => {
  it("digit-led identifier throws", () => {
    expect(() => ArtDomain.of("1root")).toThrow(/Invalid artDomain/);
  });

  it("single lowercase letter is accepted", () => {
    expect(ArtDomain.of("a")).toBe("a");
  });

  it("identifier with digits in non-leading position is accepted", () => {
    expect(ArtDomain.of("art2d2")).toBe("art2d2");
  });

  it("whitespace-only string throws after trimming", () => {
    expect(() => ArtDomain.of("   ")).toThrow(/Invalid artDomain/);
  });

  it("identifier with embedded uppercase throws", () => {
    expect(() => ArtDomain.of("rootCutting")).toThrow(/Invalid artDomain/);
  });

  it("hyphen character throws — only underscore is allowed as separator", () => {
    expect(() => ArtDomain.of("root-cutting")).toThrow(/Invalid artDomain/);
  });
});

// ─── Strike 4 — Property test (N=100, deterministic LCG) ─────────────────────
//
// Knuth LCG parameters (same as used in a11oy PR #181 PROP-RC007):
//   multiplier a = 1664525, increment c = 1013904223, modulus m = 2^32
//
// For each of 100 seeds we generate a random ASCII string and verify that
// ArtDomain.of() accepts it IFF the spec predicate holds:
//   accepted ≡ trimmed.length > 0
//              ∧ trimmed[0] ∈ [a-z]
//              ∧ every char in trimmed ∈ [a-z0-9_]
//
// The alphabet is printable ASCII (codepoints 33–126) to exercise a wide
// range of valid and invalid characters.

describe("ArtDomain branded type — Strike 4: property test N=100", () => {
  /** Deterministic LCG — Knuth (a=1664525, c=1013904223, m=2^32) */
  function lcg(seed: number): number {
    return ((seed * 1664525 + 1013904223) >>> 0);
  }

  /** Build a printable-ASCII string of `len` chars from `seed` */
  function randomString(seed: number, len: number): string {
    let s = "";
    let state = seed;
    for (let i = 0; i < len; i++) {
      state = lcg(state);
      // Printable ASCII: codepoints 33..126 (94 chars)
      const cp = 33 + (state % 94);
      s += String.fromCharCode(cp);
    }
    return s;
  }

  /** Spec predicate: true iff trimmed matches /^[a-z][a-z0-9_]*$/ */
  function specAccepts(raw: string): boolean {
    const t = raw.trim();
    return /^[a-z][a-z0-9_]*$/.test(t);
  }

  it("PROP-ARTDOMAIN: ArtDomain.of() accepts iff spec predicate holds (N=100)", () => {
    let seed = 0xdeadbeef; // deterministic starting state
    let failures = 0;
    const failLog: string[] = [];

    for (let i = 0; i < 100; i++) {
      seed = lcg(seed);
      // Length 1..8 (seed % 8 + 1)
      const len = (seed % 8) + 1;
      const raw = randomString(seed, len);
      const expected = specAccepts(raw);

      let actual: boolean;
      try {
        ArtDomain.of(raw);
        actual = true;
      } catch {
        actual = false;
      }

      if (actual !== expected) {
        failures++;
        failLog.push(`i=${i} raw="${raw}" expected=${expected} actual=${actual}`);
      }
    }

    if (failures > 0) {
      throw new Error(
        `PROP-ARTDOMAIN: ${failures}/100 mismatches:\n${failLog.join("\n")}`,
      );
    }

    // Verified 100 inputs, 0 failures.
    expect(failures).toBe(0);
  });
});
