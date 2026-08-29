---
license: apache-2.0
library_name: transformers
tags:
  - governed-ai
  - szl-holdings
  - doctrine-v11
  - receipt
  - signed
---

# SZL-Forge-1.5B-ReceiptAgent

Proposal-only agent. Every completion is meant to become a receipt, not an action.

**Family.** receipt · **Evidence.** SIGNED · **Weights.** full · **Params.** 1.5B BF16 · **Base.** Qwen/Qwen2.5-1.5B-Instruct

Hub: [SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent](https://huggingface.co/SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent)

## The cut

Agents that 'use tools' skip the envelope. This model cannot act. It proposes. The controller signs. That split is the product.

An agent whose weights are physically incapable of being the actor. Authority lives outside the tensor.

### Silhouette → leave → SZL

| Leader | Take, then tweak |
|---|---|
| Anthropic | Claude tool-use, but the tool is always 'emit a proposal'. |
| NVIDIA | NIM agent runtime, minus the runtime — we refuse to let the weights call. |
| Unsloth | receiptagent profile: packing=false so receipt-token loss is the point. |

Nobody else ships this combination. That is the point of a one-of-one.

## Intended use

Alloy controller inbound. Never a naked chatbot.

## Limitations

- Proposal-only. Ungoverned decode is misuse.
- Owner eval, not a public leaderboard.

## Honesty

| Claim | Label |
|---|---|
| This card's numbers | SIGNED |
| Energy / joules | UNAVAILABLE unless a signed meter says MEASURED |
| Λ uniqueness | Conjecture 1 OPEN — not a theorem |
| GGUF as the signed object | FALSE |

Doctrine v11 LOCKED · 749 declarations · 14 axioms · 163 sorries · locked-proven 8.

Apache-2.0. Copyright 2026 SZL Holdings · Stephen P. Lutar Jr. · ORCID [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173).
