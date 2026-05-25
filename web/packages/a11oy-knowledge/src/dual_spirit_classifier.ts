/**
 * Dual-Spirit Classifier — DSS 1QS 3:13-4:26 "Two Spirits Treatise".
 *
 * Sources:
 *   - 1QS (Community Rule, Cave 1), cols. 3:13-4:26
 *   - Charlesworth, J. H. (1995). The Dead Sea Scrolls vol. 1 (Mohr Siebeck), pp. 13-19.
 *   - DJD XXVI (4Q255-264 parallels)
 *
 * The treatise asserts every agent is governed by two competing spirits
 * (truth vs. perversity / light vs. darkness), each with 7 attributes.
 * We compute a `lightShare ∈ [0,1]` from observed signals and emit a
 * verdict consistent with the 4Q186 9-part physiognomy gating bands.
 */

import attributes from "./dual_spirit_attributes.json";

export type SpiritSignal = {
  attributeId: string; // e.g. "L1" | "D3"
  weight: number;      // [0,1], evidentiary strength
};

export type DualSpiritVerdict = {
  lightShare: number;            // [0,1]
  band: "aligned" | "mixed" | "misaligned";
  citation: string;
  attributeScores: Record<string, number>;
};

const LIGHT_IDS = new Set(attributes.lightSpirit.map((a) => a.id));
const DARK_IDS = new Set(attributes.darknessSpirit.map((a) => a.id));

export function classifyDualSpirit(signals: SpiritSignal[]): DualSpiritVerdict {
  const scores: Record<string, number> = {};
  let lightAcc = 0;
  let darkAcc = 0;

  for (const s of signals) {
    const w = Math.max(0, Math.min(1, s.weight));
    scores[s.attributeId] = (scores[s.attributeId] ?? 0) + w;
    if (LIGHT_IDS.has(s.attributeId)) lightAcc += w;
    else if (DARK_IDS.has(s.attributeId)) darkAcc += w;
  }

  const total = lightAcc + darkAcc;
  const lightShare = total === 0 ? 0.5 : lightAcc / total;

  // 4Q186 9-part bands → mapped to [0,1]:
  //   light >= 7/9 ≈ 0.778 → aligned
  //   light in [4/9, 7/9)   → mixed
  //   light < 4/9 ≈ 0.444   → misaligned
  let band: DualSpiritVerdict["band"];
  if (lightShare >= 7 / 9) band = "aligned";
  else if (lightShare >= 4 / 9) band = "mixed";
  else band = "misaligned";

  return {
    lightShare,
    band,
    citation: attributes.source,
    attributeScores: scores,
  };
}
