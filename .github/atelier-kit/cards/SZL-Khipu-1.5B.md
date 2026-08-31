---
license: apache-2.0
library_name: transformers
tags:
  - governed-ai
  - szl-holdings
  - doctrine-v11
  - navigator
  - signed
---

# SZL-Khipu-1.5B

A 1.5B brain navigator that plans over handles, never over document text. NAVIGATE or ABSTAIN in khipu.schema.json.

**Family.** navigator · **Evidence.** SIGNED · **Weights.** full · **Params.** 1.5B · **Base.** Qwen/Qwen2.5-1.5B-Instruct

Hub: [SZLHOLDINGS/SZL-Khipu-1.5B](https://huggingface.co/SZLHOLDINGS/SZL-Khipu-1.5B)

## The cut

The model is blind to content. Citations cannot be invented from memory because memory never saw the nodes. That is a capability nobody else wants, and we trained it.

Retrieval that cannot hallucinate a citation. Grounding is structural.

### Silhouette → leave → SZL

| Leader | Take, then tweak |
|---|---|
| Anthropic | Claude abstains in prose. Khipu abstains in a schema with citedNodeIds: []. |
| NVIDIA | NeMo retriever sees passages. Khipu sees handles only. |
| Unsloth | QLoRA SFT, 7 modules, packing=auto, adamw_8bit, receipted. Not retrained here. |

Nobody else ships this combination. That is the point of a one-of-one.

## Intended use

Controller-bound retrieval planner. Proposal only.

## Limitations

- Abstain 2/6 — do not deploy autonomous.
- Eval is owner synthetic, not third-party.
- Curriculum files not published.

## Honesty

| Claim | Label |
|---|---|
| This card's numbers | SIGNED |
| Energy / joules | UNAVAILABLE unless a signed meter says MEASURED |
| Λ uniqueness | Conjecture 1 OPEN — not a theorem |
| GGUF as the signed object | FALSE |

Doctrine v11 LOCKED · 749 declarations · 14 axioms · 163 sorries · locked-proven 8.

Apache-2.0. Copyright 2026 SZL Holdings · Stephen P. Lutar Jr. · ORCID [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173).
