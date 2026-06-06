# knot-calculus-v1 — SZL Holdings Cookbook Recipe

**Tag:** `knot-calculus-v1`
**Date sealed:** May 28, 2026
**Frame:** Knot calculus for governed-decision receipts (Ouroboros Thesis v15 Ch.10)

## What this recipe contains

| File | Purpose |
|---|---|
| `code/src/khipu-receipt.ts` | Self-contained khipu-indexed receipt DAG (mirrors `rosie/src/khipu-receipt.ts`) |
| `code/src/pac-bayes-bound.ts` | McAllester-1999 PAC-Bayes bound (mirrors `a11oy-core/governance/pac-bayes-bound.ts`) |
| `code/src/knot-tag.ts` | Audit-Reidemeister knot-invariant tag emitter |
| `code/tests/demo.ts` | Walks the full pipeline: build receipts → verify TH11 → emit knot tag → compute PAC-Bayes bound |
| `code/package.json` | `npx tsx tests/demo.ts` |

## What the demo prints

1. A 3-organ × 5-decision khipu root receipt with the sum-of-sums invariant verified
   (TH11 pass).
2. The 16-hex knot-invariant tag of that root.
3. A McAllester-1999 PAC-Bayes upper bound on the governance head's risk for a worked
   example (n = 100 000, KL = 0.5, δ = 0.05, R̂ = 0.05).
4. A failure-mode demonstration: a tampered pendant value is rejected by
   `verifySumInvariant` (TH11 failure).

## Lean obligations referenced

| Theorem | File | Status |
|---|---|---|
| TH11 `khipuReceipt_checksum_invariant` | `lutar-lean/Lutar/Khipu/SummationInvariant.lean` | two routine `sorry`s |
| TH12 `ΛGateLID_DPO_stability` | `lutar-lean/Lutar/DPOFeasibility.lean` | three tagged `sorry`s |
| TH13 `governanceHead_PACBayes_bound` | `lutar-lean/Lutar/PACBayes.lean` | closed-form proved; Pr-quantifier open |
| Conjecture R1/R2/R3 | `lutar-lean/Lutar/Knot/ReidemeisterConjecture.lean` | all `sorry`-tagged, target v16 |

## Citations

- Ascher & Ascher 1981, *Code of the Quipu* (U. Michigan Press)
- Urton 2003, *Signs of the Inka Khipu* (UT Press, pp. 41–62)
- Medrano & Khosla 2024, *Latin American Antiquity* (≥74% of 650 corpus khipu)
- McAllester 1999, COLT — PAC-Bayesian model averaging
- McAllester 2003, *Machine Learning* 51:5–21
- Lotfi et al. 2023, arXiv:2312.17173 (NeurIPS) — non-vacuous LLM bounds
- Reidemeister 1927, *Abh. Math. Sem. Univ. Hamburg* 5:24–32
- Bar-Natan 1995, *Topology* 34:423–472 — Vassiliev chord diagrams
- Vassiliev 1990, *Adv. Sov. Math.* 1:23–69
- Amari 1985 (Springer LNS 28), 2016 (Springer) — information geometry
- Bai et al. 2025, arXiv:2512.01899 (SaTML 2026) — DPO LID stability
- Rafailov et al. 2023, arXiv:2305.18290 (NeurIPS 2023) — DPO
- Pinsker 1964; Tsybakov 2009 — KL ↔ TV inequalities
- Hyland, Bennison & Hyland 2021, *LARR* DOI 10.25222/LARR.1032 — khipu-board ceremony
- IETF draft-ietf-scitt-architecture-22, 2025 — multi-receipt transparent statements

## Doctrine v6

Recipe is doctrine-v6 clean (no banned tokens: "revolutionary", "groundbreaking",
"magical", "world-class", "best-in-class", "game-changing", "first-ever",
"unprecedented", "frontier-defining"). See
[doctrine v6 DOI](https://doi.org/10.5281/zenodo.20174600).
