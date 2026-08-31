/**
 * sentra-dual-use-detector.ts — Watcher arts dual-use filter
 * Organ: sentra (LIVER / TOXIN FILTER)
 *
 * STATUS: TUTORIAL FIXTURE — runnable copy for the recipe smoke tests.
 *   The CANONICAL implementation is:
 *     sentra/web/src/lib/dual-use/dual-use-detector.ts
 *
 * Source: 1 Enoch 6–8 (Charles 1917, pp. 62–65)
 * Author: Stephen P. Lutar Jr., SZL Holdings
 */

export type GatePolicy = "ALLOW" | "DUAL_USE_HARD_GATE" | "HARD_BLOCK";

export interface WatcherArt {
  artDomain: string;
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
    artDomain: "enchantments",    label: "Enchantments",
    dualUseCoefficient: 0.85,     gatePolicy: "DUAL_USE_HARD_GATE",
    moralGrounding: "1 En. 8:3 — Semjâzâ taught enchantments and root-cuttings",
    permittedContexts: ["research", "analysis"],
  },
  {
    artDomain: "astrology",       label: "Astrology / Signs",
    dualUseCoefficient: 0.72,     gatePolicy: "DUAL_USE_HARD_GATE",
    moralGrounding: "1 En. 8:3 — Asarâdel taught the motion of the moon",
    permittedContexts: ["calendar", "scheduling"],
  },
  {
    artDomain: "weapons_craft",   label: "Weapons Craft",
    dualUseCoefficient: 0.95,     gatePolicy: "HARD_BLOCK",
    moralGrounding: "1 En. 8:1 — Azâzêl taught men to make swords, knives, shields",
    permittedContexts: [],
  },
  {
    artDomain: "divination",      label: "Divination",
    dualUseCoefficient: 0.80,     gatePolicy: "DUAL_USE_HARD_GATE",
    moralGrounding: "1 En. 8:3 — Pharmârôs taught resolutions of enchantments",
    permittedContexts: ["audit", "forecasting"],
  },
  {
    artDomain: "root_cutting",    label: "Root-Cutting (Pharmaceuticals)",
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
  const isFlagged = matched.dualUseCoefficient > DUAL_USE_THRESHOLD || !inPermittedContext;
  const policy = !inPermittedContext && matched.gatePolicy === "HARD_BLOCK"
    ? "HARD_BLOCK"
    : isFlagged ? matched.gatePolicy : "ALLOW";
  return {
    capability, isFlagged, gatePolicy: policy,
    dualUseCoefficient: matched.dualUseCoefficient,
    matchedArt: matched.artDomain,
    reason: isFlagged
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