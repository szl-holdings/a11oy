/**
 * dual-use-detector.ts — Watcher arts dual-use filter
 * Organ: sentra (LIVER / TOXIN FILTER)
 * Canonical home: sentra/web/src/lib/dual-use/dual-use-detector.ts (this file)
 * Source: 1 Enoch 6–8 (Charles 1917, pp. 62–65)
 * Author: Stephen P. Lutar Jr., SZL Holdings
 *
 * Distribution note (2026-05-28): previously co-located only in
 * szl-cookbook/recipes/anatomy-evolved-v1/code/src/sentra-dual-use-detector.ts.
 * The cookbook file is now a tutorial fixture; this is the canonical
 * implementation that ch9 §9.1 names.
 *
 * Coverage caveat: CORE_WATCHER_ARTS is 5 entries. The thesis text's
 * "200-Watcher classifier" is aspirational — a full taxonomy JSON is not
 * yet shipped. The detector is extensible via the `artRegistry` argument.
 *
 * Structural note (2026-05-31 — Llamkachiq): artDomain fields now use the
 * ArtDomain branded type (see art-domain.ts). Any future art registered with
 * mixed-case (e.g. "Root_Cutting") will throw at ArtDomain.of() call time,
 * not silently fail at comparison time. This resolves the adjacent finding
 * flagged by Hampichiq in sentra#103.
 */

import { ArtDomain } from "./art-domain";
export type { ArtDomain } from "./art-domain";

export type GatePolicy = "ALLOW" | "DUAL_USE_HARD_GATE" | "HARD_BLOCK";

export interface WatcherArt {
  artDomain: ArtDomain;
  label: string;
  dualUseCoefficient: number;  // 0..1
  gatePolicy: GatePolicy;
  moralGrounding: string;
  permittedContexts: string[];
}

export interface DualUseDetectionResult {
  capability: string;
  isFlagged: boolean;
  gatePolicy: GatePolicy;
  dualUseCoefficient: number;
  matchedArt: string | null;
  reason: string;
}

/** Threshold: dual_use_coefficient > 0.7 → HARD_GATE or HARD_BLOCK */
const DUAL_USE_THRESHOLD = 0.7;

/** Core Watcher arts (1 Enoch 8 — abbreviated; full 200-entry JSON in watchers_taxonomy.json) */
export const CORE_WATCHER_ARTS: WatcherArt[] = [
  {
    artDomain: ArtDomain.fromTrusted("enchantments"),
    label: "Enchantments",
    dualUseCoefficient: 0.85,     gatePolicy: "DUAL_USE_HARD_GATE",
    moralGrounding: "1 En. 8:3 — Semjâzâ taught enchantments and root-cuttings",
    permittedContexts: ["research", "analysis"],
  },
  {
    artDomain: ArtDomain.fromTrusted("astrology"),
    label: "Astrology / Signs",
    dualUseCoefficient: 0.72,     gatePolicy: "DUAL_USE_HARD_GATE",
    moralGrounding: "1 En. 8:3 — Asarâdel taught the motion of the moon",
    permittedContexts: ["calendar", "scheduling"],
  },
  {
    artDomain: ArtDomain.fromTrusted("weapons_craft"),
    label: "Weapons Craft",
    dualUseCoefficient: 0.95,     gatePolicy: "HARD_BLOCK",
    moralGrounding: "1 En. 8:1 — Azâzêl taught men to make swords, knives, shields",
    permittedContexts: [],
  },
  {
    artDomain: ArtDomain.fromTrusted("divination"),
    label: "Divination",
    dualUseCoefficient: 0.80,     gatePolicy: "DUAL_USE_HARD_GATE",
    moralGrounding: "1 En. 8:3 — Pharmârôs taught resolutions of enchantments",
    permittedContexts: ["audit", "forecasting"],
  },
  {
    artDomain: ArtDomain.fromTrusted("root_cutting"),
    label: "Root-Cutting (Pharmaceuticals)",
    dualUseCoefficient: 0.88,     gatePolicy: "DUAL_USE_HARD_GATE",
    moralGrounding: "1 En. 8:3 — Penemüê taught root-cuttings",
    permittedContexts: ["medical_research"],
  },
];

export function detectDualUse(
  capability: string,
  artDomain: string,
  context: string = "general",
  artRegistry: WatcherArt[] = CORE_WATCHER_ARTS,
): DualUseDetectionResult {
  const matched = artRegistry.find(a => a.artDomain === artDomain);
  if (!matched) {
    return {
      capability, isFlagged: false, gatePolicy: "ALLOW",
      dualUseCoefficient: 0, matchedArt: null,
      reason: "No Watcher art match — allowed",
    };
  }
  const inPermittedContext = matched.permittedContexts.includes(context);

  // HARD_BLOCK arts (e.g. weapons_craft, permittedContexts=[]) can never be
  // downgraded by any context string. For all other arts, a permitted context
  // downgrades the gate to ALLOW even when the dual-use coefficient is high.
  const isHardBlock = matched.gatePolicy === "HARD_BLOCK";

  // isFlagged records the dual-use risk independently of gating: a high-coeff
  // art stays flagged for audit even when its gate is downgraded by context.
  const isFlagged = isHardBlock || matched.dualUseCoefficient > DUAL_USE_THRESHOLD;

  let policy: GatePolicy;
  if (isHardBlock) {
    policy = "HARD_BLOCK";
  } else if (inPermittedContext) {
    policy = "ALLOW";
  } else {
    policy = matched.dualUseCoefficient > DUAL_USE_THRESHOLD
      ? matched.gatePolicy
      : "ALLOW";
  }

  const downgraded = !isHardBlock && inPermittedContext && isFlagged;
  return {
    capability, isFlagged, gatePolicy: policy,
    dualUseCoefficient: matched.dualUseCoefficient,
    matchedArt: matched.artDomain,
    reason: downgraded
      ? `Watcher art "${matched.label}" (coeff=${matched.dualUseCoefficient}) flagged but permitted in context "${context}" — ${matched.moralGrounding}`
      : isFlagged
        ? `Watcher art "${matched.label}" (coeff=${matched.dualUseCoefficient}) — ${matched.moralGrounding}`
        : "Within permitted context",
  };
}

// ─── Usage Example ────────────────────────────────────────────────────────────
/*
const result = detectDualUse("generateBioWeapon", "weapons_craft", "general");
console.log(result.gatePolicy); // HARD_BLOCK
const allowed = detectDualUse("readSunspots", "astrology", "scheduling");
console.log(allowed.gatePolicy); // ALLOW (scheduling is permitted context)
*/
