/**
 * dual-use-context-remediation.test.ts
 * Watunakuy supplemental tests — Hampichiq remediation 2026-05-31
 *
 * Covers the two bugs fixed in dual-use-detector.ts:
 *   Fix 1 — permittedContexts downgrade: high-coeff arts now gate to ALLOW
 *            when invoked in a permitted context (isFlagged preserved for audit).
 *   Fix 2 — case-insensitive matching (PhD-CS pass 4): callers may pass
 *            "Medical_Research" or "ROOT_CUTTING" and still match.
 *
 * Minimum 6 new tests (Watunakuy Strike 1):
 *   2 ALLOW-path probes (root_cutting / other high-coeff arts in permitted ctx)
 *   2 DENY-path probes  (high-coeff arts outside permitted ctx)
 *   2 case-insensitive probes (artDomain and context)
 *
 * Plus:
 *   Boundary edge-case: context that is a prefix of a permitted context
 *   Boundary edge-case: empty context string
 *   isFlagged audit invariant: downgraded gates still set isFlagged=true
 *   Reason string: downgraded result carries "permitted in context" message
 *
 * Strike 2 (integration) — documented below. The full container integration
 * test (booting immune_server.py from PR #96/102 + dual-use HTTP endpoint)
 * is scoped to post-merge of those PRs into this branch. This file provides
 * the in-process integration test: multiple detectDualUse calls in sequence
 * simulating a policy gateway processing a batch of actions.
 *
 * Doctrine v7 clean — 0 banned tokens.
 * Test framework: vitest
 */

import { describe, expect, it } from "vitest";
import { CORE_WATCHER_ARTS, detectDualUse, type DualUseDetectionResult } from "../dual-use-detector";

// ═══════════════════════════════════════════════════════════════════════════
// ALLOW-PATH PROBES — permittedContexts downgrade
// ═══════════════════════════════════════════════════════════════════════════

describe("dual-use remediation: permittedContexts ALLOW-path", () => {
  // DP-ALLOW-1: The failing Tarpuq test case, re-stated as an edge-case probe.
  // root_cutting has coeff 0.88 > 0.7 threshold AND is in permittedContexts
  // for "medical_research". Gate must be ALLOW; isFlagged must be true.
  it("DP-ALLOW-1: root_cutting + medical_research → ALLOW with isFlagged=true (audit preserved)", () => {
    const r = detectDualUse("synthesizeCompound", "root_cutting", "medical_research");
    expect(r.gatePolicy).toBe("ALLOW");
    expect(r.isFlagged).toBe(true);  // audit trail must survive the downgrade
    expect(r.matchedArt).toBe("root_cutting");
    expect(r.dualUseCoefficient).toBe(0.88);
  });

  // DP-ALLOW-2: enchantments (coeff 0.85) in permitted context "research".
  // Same pattern as root_cutting — a different art in its permitted context.
  it("DP-ALLOW-2: enchantments + research → ALLOW with isFlagged=true", () => {
    const r = detectDualUse("castSpell", "enchantments", "research");
    expect(r.gatePolicy).toBe("ALLOW");
    expect(r.isFlagged).toBe(true);
    expect(r.matchedArt).toBe("enchantments");
  });

  // DP-ALLOW-3: astrology (coeff 0.72) in permitted context "scheduling".
  // Lowest threshold-exceeding art — confirms the fix is not art-specific.
  it("DP-ALLOW-3: astrology + scheduling → ALLOW with isFlagged=true", () => {
    const r = detectDualUse("computeMoonPhase", "astrology", "scheduling");
    expect(r.gatePolicy).toBe("ALLOW");
    expect(r.isFlagged).toBe(true);
    expect(r.matchedArt).toBe("astrology");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DENY-PATH PROBES — high-coeff arts OUTSIDE permitted context
// ═══════════════════════════════════════════════════════════════════════════

describe("dual-use remediation: DENY-path (non-permitted context)", () => {
  // DP-DENY-1: root_cutting called in "general" context — not in permittedContexts.
  // Must remain DUAL_USE_HARD_GATE (not ALLOW).
  it("DP-DENY-1: root_cutting + general context → DUAL_USE_HARD_GATE (not permitted)", () => {
    const r = detectDualUse("synthesizeCompound", "root_cutting", "general");
    expect(r.gatePolicy).toBe("DUAL_USE_HARD_GATE");
    expect(r.isFlagged).toBe(true);
  });

  // DP-DENY-2: root_cutting in "audit" context — permitted for divination but NOT
  // for root_cutting. Confirms context matching is per-art, not global.
  it("DP-DENY-2: root_cutting + audit context → DUAL_USE_HARD_GATE (wrong art's context)", () => {
    const r = detectDualUse("synthesizeCompound", "root_cutting", "audit");
    expect(r.gatePolicy).toBe("DUAL_USE_HARD_GATE");
    expect(r.isFlagged).toBe(true);
  });

  // DP-DENY-3: enchantments in "medical_research" — not in enchantments' permitted
  // list ["research", "analysis"]. Confirms the context must match THIS art's list.
  it("DP-DENY-3: enchantments + medical_research → DUAL_USE_HARD_GATE (not in enchantments contexts)", () => {
    const r = detectDualUse("castSpell", "enchantments", "medical_research");
    expect(r.gatePolicy).toBe("DUAL_USE_HARD_GATE");
    expect(r.isFlagged).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// CASE-INSENSITIVE MATCHING — PhD-CS pass 4 finding
// ═══════════════════════════════════════════════════════════════════════════

describe("dual-use remediation: case-insensitive artDomain and context (PhD-CS pass 4)", () => {
  // CI-1: artDomain passed as uppercase "ROOT_CUTTING" — must match "root_cutting"
  it("CI-1: artDomain 'ROOT_CUTTING' (uppercase) matches 'root_cutting' in registry", () => {
    const r = detectDualUse("synthesizeCompound", "ROOT_CUTTING", "medical_research");
    expect(r.gatePolicy).toBe("ALLOW");
    expect(r.matchedArt).toBe("root_cutting");
  });

  // CI-2: context passed as "Medical_Research" (mixed case) — must match
  // "medical_research" in root_cutting's permittedContexts.
  it("CI-2: context 'Medical_Research' (mixed case) matches 'medical_research' permitted context", () => {
    const r = detectDualUse("synthesizeCompound", "root_cutting", "Medical_Research");
    expect(r.gatePolicy).toBe("ALLOW");
    expect(r.isFlagged).toBe(true);  // still flagged for audit
  });

  // CI-3: Both artDomain and context in uppercase — full case-insensitive round-trip.
  it("CI-3: 'WEAPONS_CRAFT' + 'MEDICAL_RESEARCH' (all uppercase) → HARD_BLOCK (weapons cannot be downgraded)", () => {
    const r = detectDualUse("forge", "WEAPONS_CRAFT", "MEDICAL_RESEARCH");
    expect(r.gatePolicy).toBe("HARD_BLOCK");
    expect(r.isFlagged).toBe(true);
  });

  // CI-4: artDomain passed as partial-case "Astrology" — must still match "astrology".
  it("CI-4: artDomain 'Astrology' (title case) matches 'astrology' in registry", () => {
    const r = detectDualUse("readStars", "Astrology", "scheduling");
    expect(r.gatePolicy).toBe("ALLOW");
    expect(r.matchedArt).toBe("astrology");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// BOUNDARY EDGE CASES
// ═══════════════════════════════════════════════════════════════════════════

describe("dual-use remediation: boundary edge cases", () => {
  // BE-1: Context that is a prefix of a permitted context must NOT match.
  // "medical" is not "medical_research" — exact match (case-insensitive) required.
  it("BE-1: context 'medical' (prefix of 'medical_research') does NOT grant permit", () => {
    const r = detectDualUse("synthesizeCompound", "root_cutting", "medical");
    expect(r.gatePolicy).toBe("DUAL_USE_HARD_GATE");
    expect(r.isFlagged).toBe(true);
  });

  // BE-2: Empty context string — must not match any permittedContext.
  it("BE-2: empty context string does not match any permittedContext", () => {
    const r = detectDualUse("synthesizeCompound", "root_cutting", "");
    expect(r.gatePolicy).toBe("DUAL_USE_HARD_GATE");
    expect(r.isFlagged).toBe(true);
  });

  // BE-3: Unknown art domain returns ALLOW (open-world default is preserved).
  it("BE-3: unknown artDomain (not in registry) → ALLOW with isFlagged=false", () => {
    const r = detectDualUse("doSomething", "alchemy_unknown_art", "general");
    expect(r.gatePolicy).toBe("ALLOW");
    expect(r.isFlagged).toBe(false);
    expect(r.matchedArt).toBeNull();
  });

  // BE-4: weapons_craft with empty permittedContexts — no context can downgrade it.
  // This is the invariant that the context-coercion test already verifies, but
  // stated as a boundary: even "medical_research" (which permits root_cutting)
  // cannot downgrade weapons_craft.
  it("BE-4: weapons_craft + medical_research (a legitimate context for another art) → HARD_BLOCK", () => {
    const r = detectDualUse("forge", "weapons_craft", "medical_research");
    expect(r.gatePolicy).toBe("HARD_BLOCK");
    expect(r.isFlagged).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// AUDIT INVARIANT — isFlagged survives gate downgrade
// ═══════════════════════════════════════════════════════════════════════════

describe("dual-use remediation: isFlagged audit invariant", () => {
  // AI-1: For EVERY art with dualUseCoefficient > 0.7, isFlagged must be true
  // even when gatePolicy is downgraded to ALLOW by a permitted context.
  // Tests all 4 non-HARD_BLOCK arts in their respective permitted contexts.
  it("AI-1: all high-coeff non-HARD_BLOCK arts in permitted context have isFlagged=true", () => {
    const cases: [string, string, string][] = [
      ["synthesizeCompound", "root_cutting",  "medical_research"],
      ["castSpell",          "enchantments",  "research"],
      ["castSpell",          "enchantments",  "analysis"],
      ["computeMoon",        "astrology",     "calendar"],
      ["computeMoon",        "astrology",     "scheduling"],
      ["forecastEvent",      "divination",    "audit"],
      ["forecastEvent",      "divination",    "forecasting"],
    ];
    for (const [cap, art, ctx] of cases) {
      const r = detectDualUse(cap, art, ctx);
      expect(r.gatePolicy).toBe("ALLOW");
      expect(r.isFlagged).toBe(true);
      // Reason string must mention "permitted in context" for downgraded results
      expect(r.reason).toContain("permitted in context");
    }
  });

  // AI-2: CORE_WATCHER_ARTS table still has exactly 5 entries (regression guard
  // against unintended expansion during this remediation).
  it("AI-2: CORE_WATCHER_ARTS still has 5 entries (coverage gap explicitly acknowledged)", () => {
    expect(CORE_WATCHER_ARTS.length).toBe(5);
    const domains = CORE_WATCHER_ARTS.map(a => a.artDomain).sort();
    expect(domains).toEqual([
      "astrology",
      "divination",
      "enchantments",
      "root_cutting",
      "weapons_craft",
    ]);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// STRIKE 2 — In-process integration test (batch policy gateway simulation)
//
// NOTE: The full container integration test (immune_server.py from PR #96/102
// exercised over HTTP with testcontainers) is scoped to post-merge of those
// PRs into this branch. That PR added the HTTP surface (POST /v1/inspect) to
// the Python immune server. This test is the in-process equivalent: it
// simulates a batch of 10 actions coming through a policy gateway, calls
// detectDualUse for each, and asserts the complete end-to-end decision set.
// It is NOT a mock — it calls the real detector with real art registry.
// ═══════════════════════════════════════════════════════════════════════════

describe("dual-use integration: batch policy gateway simulation (Strike 2 in-process)", () => {
  it("INTEG-1: 10-action batch produces correct gates across ALLOW, DUAL_USE_HARD_GATE, HARD_BLOCK", () => {
    type Action = { capability: string; artDomain: string; context: string };
    const batch: Action[] = [
      // Should ALLOW — permitted context
      { capability: "synthesizeCompound",  artDomain: "root_cutting", context: "medical_research" },
      { capability: "readStars",           artDomain: "astrology",    context: "scheduling" },
      { capability: "analyzeMoonCycle",    artDomain: "astrology",    context: "calendar" },
      { capability: "runAuditForecast",    artDomain: "divination",   context: "forecasting" },
      // Should ALLOW — unknown art (open world)
      { capability: "doArithmetic",        artDomain: "mathematics",  context: "general" },
      // Should DUAL_USE_HARD_GATE — high coeff, not in permitted context
      { capability: "synthesizeCompound",  artDomain: "root_cutting", context: "general" },
      { capability: "castSpell",           artDomain: "enchantments", context: "production" },
      { capability: "forecastEvent",       artDomain: "divination",   context: "general" },
      // Should HARD_BLOCK — weapons_craft regardless of context
      { capability: "forgeSword",          artDomain: "weapons_craft", context: "general" },
      { capability: "forgeSword",          artDomain: "weapons_craft", context: "medical_research" },
    ];

    const expectedPolicies: DualUseDetectionResult["gatePolicy"][] = [
      "ALLOW",
      "ALLOW",
      "ALLOW",
      "ALLOW",
      "ALLOW",
      "DUAL_USE_HARD_GATE",
      "DUAL_USE_HARD_GATE",
      "DUAL_USE_HARD_GATE",
      "HARD_BLOCK",
      "HARD_BLOCK",
    ];

    const results = batch.map(a => detectDualUse(a.capability, a.artDomain, a.context));

    for (let i = 0; i < batch.length; i++) {
      expect(results[i].gatePolicy).toBe(expectedPolicies[i]);
    }

    // Summary invariants across the batch
    const allowCount = results.filter(r => r.gatePolicy === "ALLOW").length;
    const gateCount  = results.filter(r => r.gatePolicy === "DUAL_USE_HARD_GATE").length;
    const blockCount = results.filter(r => r.gatePolicy === "HARD_BLOCK").length;
    expect(allowCount).toBe(5);
    expect(gateCount).toBe(3);
    expect(blockCount).toBe(2);
  });
});
