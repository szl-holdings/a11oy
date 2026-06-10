# SZL Papers

**SZL Holdings academic corpus** — preprints, thesis lineage, bounty problems, and prior-art disclosures.

[![Doctrine v11 LOCKED](https://img.shields.io/badge/Doctrine-v11_LOCKED-d4a444.svg)](https://github.com/szl-holdings/lutar-lean)
[![Λ Conjecture 1](https://img.shields.io/badge/Λ-Conjecture_1_(conditional_Theorem_U)-B79BD6.svg)](https://github.com/szl-holdings/lutar-lean/blob/main/BOUNTY.md)
[![Khipu Conjecture 2](https://img.shields.io/badge/Khipu_BFT-Conjecture_2_(OPEN)-B79BD6.svg)](https://github.com/szl-holdings/lutar-lean)
[![SLSA L1](https://img.shields.io/badge/SLSA-L1_honest-green.svg)](https://slsa.dev)
[![DCO](https://img.shields.io/badge/DCO-required-orange.svg)](https://developercertificate.org)

Doctrine v11 LOCKED 749/14/163 · kernel commit `c7c0ba17`

---

## Contents

| Directory | Contents | Source |
|-----------|---------|--------|
| [`preprints/puriq/`](preprints/puriq/) | PURIQ preprint — Λ-aggregator formal spec | [puriq-preprint](https://github.com/szl-holdings/szl-papers/tree/main/preprints/puriq) |
| [`thesis/ouroboros/`](thesis/ouroboros/) | Ouroboros thesis — receipt DAG lineage | ouroboros-thesis |
| [`bounty/`](bounty/) | Lambda bounty problems — open mathematical challenges | [lambda-bounty](https://github.com/szl-holdings/lambda-bounty) |
| [`prior-art/`](prior-art/) | Prior-art disclosures for IP protection | prior-art-disclosures |

---

## Thesis Lineage (v1 → v22)

The **intellectual provenance of SZL Holdings** — every governance claim traces to a versioned,
DOI-pinned thesis. See the canonical timeline: **[`thesis/THESIS_LINEAGE.md`](thesis/THESIS_LINEAGE.md)**.

- **22 thesis versions** (v1 2026-04-28 → v22 2026-06-03; v19 intentionally skipped).
- **Latest:** [v22 — Convergence](thesis/ouroboros/papers/v22/) — A5 axiom merge, Cauchy_ND partial closure, VCG truthfulness, supply-chain hardening (SLSA L1 honest; L2 verified-provenance on the roadmap), Innovation Rounds 10–11, Sim-to-Real benchmark (α=0.10).
- **Concept DOI (always-latest):** [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926).
- **Λ uniqueness — honest taxonomy.** *Governance-safe* uniqueness is **Theorem U** (proven, conditional, axiom-free): Λ is unique *modulo* the audit-invariant equivalence `≈Λ` under the Identifiability Assumptions (IA), with strict `=` only under the `Anchored`/`Normalized` predicate — see [`Lutar/Uniqueness/TheoremU.lean`](https://github.com/szl-holdings/lutar-lean/blob/main/Lutar/Uniqueness/TheoremU.lean). *Unconditional* uniqueness under bare A1–A5 stays **Conjecture 1 — OPEN** (machine-checked false as stated; never a theorem).

---

## Doctrine

- **Doctrine v11 LOCKED** — 749 declarations / 14 unique axioms / 163 sorries
- **Kernel commit:** `c7c0ba17` (DO NOT BUMP)
- **Λ = Conjecture 1** — NEVER a theorem; all claims are honest per SLSA L1
- **Section 889 vendors:** Huawei, ZTE, Hytera, Hikvision, Dahua (exactly 5)
- **DCO required** on every commit: `Signed-off-by: Yachay <yachay@szlholdings.ai>`

## Honest proof status (two tiers — never conflated)

| Tier | What it is | Count |
|------|-----------|-------|
| **LOCKED-proven** | Kernel-verified, axiom-free PURIQ formulas — `Lutar.Wave8.AxiomDisclosure.locked_count_five` proves the count `= 5` by `decide` | **exactly 5** — F1, F11, F12, F18, F19 |
| **EXPERIMENTAL · CI-green** | Separate experimental `main` corpus (Waves 11–13, CUT-2, etc.) — CI-green but **never folded into the locked-5** | 1323 decls / 23 axioms (22 unique), CI-green |

- **Λ (F23) unconditional uniqueness = Conjecture 1 (OPEN)** — the *unconditional* uniqueness claim is machine-checked **FALSE** (`Round13.maxAgg_ne_Lambda` counterexample) and ships statement-only. *Governance-safe* uniqueness is captured by **Theorem U** (`TheoremU_LambdaUnique`): unique *modulo* `≈Λ` under the Identifiability Assumptions (IA), strict `=` only under `Anchored`/`Normalized`, with corollaries **U₁** `lambda_unique_of_separable` (Wave12 CUT-2 slice-multiplicativity) and **U₂** `lambda_unique_of_factors` — all **axiom-free, 0 sorry, CI-green**. See [`Lutar/Uniqueness/TheoremU.lean`](https://github.com/szl-holdings/lutar-lean/blob/main/Lutar/Uniqueness/TheoremU.lean).
- **Byzantine BFT optimality = Khipu Conjecture 2 (OPEN).**
- See [lutar-lean](https://github.com/szl-holdings/lutar-lean) for the kernel and [`bounty/`](bounty/) for the open Λ-uniqueness bounty.

---

## Consolidation Note

This repo was created 2026-06-03 by merging 4 previously separate repos:
- `puriq-preprint` → `preprints/puriq/`
- `ouroboros-thesis` → `thesis/ouroboros/`
- `lambda-bounty` → `bounty/`
- `prior-art-disclosures` → `prior-art/`

Original repos archived with redirect notices. Git history preserved in each source.

---

**[SZL Holdings](https://a11oy.net)** · Apache-2.0 code · CC-BY-4.0 papers · Concept DOI [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926)

> **Non-affiliation.** SZL Holdings' use of "UDS" references Defense Unicorns' Unified Defense Stack (USPTO Serial 99831122); SZL Holdings is not affiliated with Defense Unicorns. No production ATO is claimed. Papers note SLSA L1 honest (corpus); product images (a11oy, killinchu) are L2 build-attested — see [szl-uds-deployment](https://github.com/szl-holdings/szl-uds-deployment).

*Signed-off-by: Yachay <yachay@szlholdings.ai>*
