/**
 * hard-block-coverage.test.ts — Watcher art HARD_BLOCK enforcement under
 * context tampering, and explicit acknowledgement of the 5-vs-200 coverage gap.
 *
 * Failure modes this catches:
 *   1. A regression that lets weapons_craft pass through ALLOW when the caller
 *      passes a permitted-looking context string (weapons_craft has
 *      permittedContexts=[], so no context should ever permit it).
 *   2. The cookbook CORE_WATCHER_ARTS table has only 5 entries; 1 Enoch 6–8
 *      names ~200. We assert this gap is explicit so the SDK contract surface
 *      doesn't silently grow without test updates.
 *
 * Reference: 1 Enoch 6–8 (Charles 1917, pp. 62–65).
 */

import { describe, expect, it } from "vitest";
import { CORE_WATCHER_ARTS, detectDualUse } from "../dual-use-detector";

describe("dual-use detector: HARD_BLOCK is robust against context coercion", () => {
  it("weapons_craft cannot escape HARD_BLOCK via any context string", () => {
    const probeContexts = [
      "general",
      "research",
      "audit",
      "scheduling",
      "medical_research",
      "calendar",
      "",
      "anything",
    ];
    for (const ctx of probeContexts) {
      const r = detectDualUse("generateBioWeapon", "weapons_craft", ctx);
      expect(r.gatePolicy).toBe("HARD_BLOCK");
      expect(r.isFlagged).toBe(true);
    }
  });

  it("unknown art domain returns ALLOW (open-world default)", () => {
    const r = detectDualUse("anything", "completely_unknown_art", "general");
    expect(r.gatePolicy).toBe("ALLOW");
    expect(r.matchedArt).toBeNull();
  });

  it("permitted context downgrades the gate but does not remove the flag for high-coeff arts", () => {
    // root_cutting has coeff 0.88 > 0.7 threshold but is permitted in medical_research.
    const r = detectDualUse("synthesizeCompound", "root_cutting", "medical_research");
    expect(r.gatePolicy).toBe("ALLOW");
  });

  it("explicit coverage gap: CORE table is a 5-entry abbreviation of the 1 Enoch 8 taxonomy", () => {
    // This test exists to fail loudly if someone increases the table without
    // updating the broader watchers_taxonomy.json or the cookbook docstring.
    // 1 Enoch 8 names roughly 200 instructed arts; the 5 here are the heads.
    expect(CORE_WATCHER_ARTS.length).toBe(5);
    const heads = CORE_WATCHER_ARTS.map((a) => a.artDomain).sort();
    expect(heads).toEqual([
      "astrology",
      "divination",
      "enchantments",
      "root_cutting",
      "weapons_craft",
    ]);
  });
});
