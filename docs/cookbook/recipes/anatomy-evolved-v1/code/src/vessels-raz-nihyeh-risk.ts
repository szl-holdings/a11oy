/**
 * vessels-raz-nihyeh-risk.ts — shell-depth opacity scorer
 * Organ: vessels (LIMBS / EXTERNAL REACH)
 *
 * STATUS: TUTORIAL FIXTURE — runnable copy for the recipe smoke tests.
 *   The CANONICAL implementation is:
 *     vessels/web/src/lib/raz-nihyeh/raz-nihyeh-risk.ts
 *
 * Source: 4QInstruction (4Q416 fr.2 ii–iii); Woogen, Macalester Classics 6:1 (2022)
 * Author: Stephen P. Lutar Jr., SZL Holdings
 * Invariant: score ∈ [0,1]; monotone non-decreasing in shellDepth WITH
 *   ALL OTHER FIELDS HELD CONSTANT (ceteris paribus). The universal claim
 *   is documented in the canonical file as restricted to that scope.
 */

export interface OwnershipNode {
  entityId: string;
  entityType: "PERSON" | "COMPANY" | "TRUST" | "FOUNDATION" | "UNKNOWN";
  jurisdiction: string;
  shellDepth: number;    // number of intermediate holding layers
  isUBO: boolean;        // true = ultimate beneficial owner identified
  registeredCapital?: number;
}

export interface RazNihyehScore {
  entityId: string;
  rawScore: number;          // ∈ [0,1]
  shellDepth: number;
  anomalyFlags: string[];
  triggersA11oyInvestigation: boolean;
  razNihyehRating: "CLEAR" | "ELEVATED" | "OBSCURED" | "DARK";
}

const INVESTIGATION_THRESHOLD = 0.70;

/** clamp to [0,1] */
function clamp01(x: number): number { return Math.max(0, Math.min(1, x)); }

/**
 * Raz Nihyeh opacity score — monotone non-decreasing in shellDepth
 * Lean proved: ∀ d₁ ≤ d₂. score(d₁) ≤ score(d₂)
 * 
 * Base formula: score = clamp01(shellDepth / MAX_DEPTH + jurisdictionPenalty)
 */
export function razNihyehScore(node: OwnershipNode): RazNihyehScore {
  const MAX_DEPTH = 8;
  const HIGH_RISK_JURISDICTIONS = ["BVI", "Cayman Islands", "Panama", "Vanuatu", "Marshall Islands"];

  const depthComponent = node.shellDepth / MAX_DEPTH;
  const jurisdictionPenalty = HIGH_RISK_JURISDICTIONS.includes(node.jurisdiction) ? 0.2 : 0;
  const uboBonus = node.isUBO ? -0.15 : 0;
  const unknownPenalty = node.entityType === "UNKNOWN" ? 0.25 : 0;

  const rawScore = clamp01(depthComponent + jurisdictionPenalty + uboBonus + unknownPenalty);

  const anomalyFlags: string[] = [];
  if (node.shellDepth >= 5) anomalyFlags.push("DEEP_SHELL_STRUCTURE");
  if (HIGH_RISK_JURISDICTIONS.includes(node.jurisdiction)) anomalyFlags.push("HIGH_RISK_JURISDICTION");
  if (!node.isUBO && node.shellDepth > 3) anomalyFlags.push("UBO_NOT_IDENTIFIED");
  if (node.entityType === "UNKNOWN") anomalyFlags.push("UNKNOWN_ENTITY_TYPE");

  const rating: RazNihyehScore["razNihyehRating"] =
    rawScore < 0.3 ? "CLEAR"
    : rawScore < 0.5 ? "ELEVATED"
    : rawScore < 0.7 ? "OBSCURED"
    : "DARK";

  return {
    entityId: node.entityId,
    rawScore,
    shellDepth: node.shellDepth,
    anomalyFlags,
    triggersA11oyInvestigation: rawScore >= INVESTIGATION_THRESHOLD,
    razNihyehRating: rating,
  };
}

export function runBatchRazNihyehScan(nodes: OwnershipNode[]): RazNihyehScore[] {
  return nodes.map(razNihyehScore);
}

// ─── Usage Example ────────────────────────────────────────────────────────────
/*
const node: OwnershipNode = {
  entityId: "vessel_dark_001", entityType: "COMPANY",
  jurisdiction: "Marshall Islands", shellDepth: 6,
  isUBO: false,
};
const score = razNihyehScore(node);
console.log("Raz Nihyeh score:", score.rawScore.toFixed(3)); // 0.95
console.log("Triggers a11oy investigation:", score.triggersA11oyInvestigation); // true
*/