/**
 * single-witness-exclusion.ts
 * SZL Holdings — Formula Uplift E-02
 * SPDX-License-Identifier: Apache-2.0
 *
 * Pepr Admission Policy: rejects gate results where a single evaluator
 * contributes 100% weight (enforces ≥ 2-of-N witness requirement).
 * Source: UDS_PAYLOAD_UPLIFTS.md E-02 / v5 Theorem 5.2 /
 *   Lutar.Gate.SingleWitnessExclusion (PHANTOM — absent at HEAD c7c0ba17)
 * Lean status: AXIOM (adversarial resilience invariant; Lean file phantom)
 * Proof label: AXIOM
 * Warhacker flag: YES — a11oy gate integrity is Warhacker central claim
 *
 * Signed-off-by: Yachay <yachay@szlholdings.ai>
 * Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
 */

import { Capability, a } from "pepr";

export const SingleWitnessExclusion = new Capability({
  name: "single-witness-exclusion",
  description:
    "SZL E-02: Rejects gate result ConfigMaps where a single witness contributes 100% weight. " +
    "Doctrine v11. Proof label: AXIOM (Lean file phantom at HEAD c7c0ba17).",
  namespaces: ["szl-a11oy", "szl-khipu", "a11oy"],
});

const { When } = SingleWitnessExclusion;

When(a.ConfigMap)
  .IsCreatedOrUpdated()
  .WithLabel("szl.io/gate-result", "true")
  .Validate((cm) => {
    const witnessesRaw = cm.Raw?.data?.["witnesses"];
    if (!witnessesRaw) {
      return cm.Deny(
        "SZL E-02 SingleWitnessExclusion: gate result missing 'witnesses' field. " +
        "Requires ≥2 witnesses. Doctrine v11. Proof label: AXIOM."
      );
    }

    let witnesses: Array<{ id: string; weight: number }>;
    try {
      witnesses = JSON.parse(witnessesRaw);
    } catch {
      return cm.Deny("SZL E-02 SingleWitnessExclusion: witnesses field is not valid JSON.");
    }

    if (witnesses.length < 2) {
      return cm.Deny(
        `SZL E-02 SingleWitnessExclusion: only ${witnesses.length} witness(es) declared. ` +
        `Requires ≥2. Doctrine v11.`
      );
    }

    const totalWeight = witnesses.reduce((s, w) => s + w.weight, 0);
    const maxWeight = Math.max(...witnesses.map((w) => w.weight));
    if (totalWeight > 0 && maxWeight / totalWeight >= 1.0) {
      return cm.Deny(
        "SZL E-02 SingleWitnessExclusion: single witness contributes 100% weight. " +
        "Adversarial single-point violation. Doctrine v11."
      );
    }

    return cm.Approve();
  });
