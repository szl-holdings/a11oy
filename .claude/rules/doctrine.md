<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Rule: doctrine (v11 LOCKED)

The non-negotiable rules every diff must satisfy. Enforced by the doctrine-grep CI gate and
the honest-status review. A breach is a **doctrine failure**, not a style nit.

## Rules

1. **Honest labels.** MEASURED requires a real, fresh exporter delta. Unverified = SAMPLE;
   future = ROADMAP; design-only = MODELED. Never fabricate joules, proofs, signatures, or status.
2. **No banned tokens.** No marketing-hype words; no retired codenames. The doctrine-grep gate
   regex is authoritative; `.doctrine-allowlist` lists files that may legitimately enumerate
   banned tokens.
3. **Locked count is 5.** The canonical formula registry admits five locked formulas
   `{F1,F11,F12,F18,F19}`; F4/F7/F22 remain experimental. Never inflate it.
   Λ-uniqueness = **Conjecture 1**; Khipu BFT safety =
   **Conjecture 2**. Never call a conjecture a theorem.
4. **Cite prior art.** External ideas (e.g. Ponytail restraint) are cited, never claimed as ours.
5. **Honest BLOCKED beats fake green.** A truthful denial/blocked is better than a fabricated pass.
6. **Never weaken a CI gate** to make a diff pass.

## Passing vs failing diff

```diff
- Our <hype-superlative> energy system delivers <hype> joules.   # FAIL: banned hype, no label
+ Energy joules are MEASURED when a GPU lung is reachable;        # PASS: honest label + caveat
+ otherwise honest SAMPLE/DEGRADED. Carbon is ROADMAP.

- We have proven 12 locked formulas and Λ-uniqueness.           # FAIL: inflates count; Λ is a conjecture
+ 5 locked-proven {F1,F11,F12,F18,F19}; F4/F7/F22 experimental; Λ = Conjecture 1.   # PASS
```

When unsure: **prefer the honest label and ask before claiming.**
</content>
