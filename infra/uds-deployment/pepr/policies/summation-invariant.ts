/**
 * summation-invariant.ts
 * SZL Holdings — Formula Uplift E-01
 * SPDX-License-Identifier: Apache-2.0
 *
 * Pepr Admission Policy: blocks EvaluationResult objects where ∑ wᵢ(aᵢ) falls
 * outside [0,1].
 * Source: UDS_PAYLOAD_UPLIFTS.md E-01 / v4 Theorem 4.1 /
 *   Lutar.Gate.SummationInvariant (PHANTOM — absent at HEAD c7c0ba17)
 * Lean status: AXIOM (functional invariant; Lean file phantom at HEAD)
 * Proof label: AXIOM (enforced by policy, not proof)
 * Warhacker flag: YES — partial enforcement testable without full proof
 *
 * Signed-off-by: Yachay <yachay@szlholdings.ai>
 * Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
 */

import { Capability, a } from "pepr";

export const SummationInvariant = new Capability({
  name: "summation-invariant",
  description:
    "SZL E-01: Blocks EvaluationResult ConfigMaps where ∑ wᵢ(aᵢ) is outside [0,1]. " +
    "Doctrine v11 §4.1. Proof label: AXIOM (Lean file phantom at HEAD c7c0ba17).",
  namespaces: ["szl-a11oy", "a11oy"],
});

const { When } = SummationInvariant;

When(a.ConfigMap)
  .IsCreatedOrUpdated()
  .WithLabel("szl.io/evaluation-result", "true")
  .Mutate((cm) => {
    // Label for downstream consumers and audit trail
    cm.SetLabel("szl.io/invariant-checked", "pepr-summation-v1");
  })
  .Validate((cm) => {
    const raw = cm.Raw?.data?.["weighted_sum"];
    if (raw === undefined) {
      return cm.Deny(
        "SZL E-01 SummationInvariant: EvaluationResult missing 'weighted_sum' field. " +
        "Doctrine v11 §4.1 requires ∑ wᵢ(aᵢ) declared. Proof label: AXIOM."
      );
    }
    const val = parseFloat(raw);
    if (isNaN(val) || val < 0 || val > 1.0001) {
      return cm.Deny(
        `SZL E-01 SummationInvariant: weighted_sum=${raw} outside [0,1]. ` +
        `Summation invariant violated. Doctrine v11 §4.1.`
      );
    }
    return cm.Approve();
  });
