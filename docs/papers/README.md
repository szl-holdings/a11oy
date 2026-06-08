# SZL Papers

**SZL Holdings academic corpus** — preprints, thesis lineage, bounty problems, and prior-art disclosures.

[![Doctrine v11 LOCKED](https://img.shields.io/badge/Doctrine-v11_LOCKED-d4a444.svg)](https://github.com/szl-holdings/lutar-lean)
[![Λ Conjecture 1](https://img.shields.io/badge/Λ-Conjecture_1_(NOT_theorem)-blue.svg)](https://github.com/szl-holdings/lutar-lean)
[![SLSA L1](https://img.shields.io/badge/SLSA-L1_honest-green.svg)](https://slsa.dev)
[![DCO](https://img.shields.io/badge/DCO-required-orange.svg)](https://developercertificate.org)

Doctrine v11 LOCKED 749/14/163 · kernel commit `c7c0ba17`

---

## Contents

| Directory | Contents | Source |
|-----------|---------|--------|
| [`preprints/puriq/`](preprints/puriq/) | PURIQ preprint — Λ-aggregator formal spec | puriq-preprint |
| [`thesis/ouroboros/`](thesis/ouroboros/) | Ouroboros thesis — receipt DAG lineage | ouroboros-thesis |
| [`bounty/`](bounty/) | Lambda bounty problems — open mathematical challenges | [lambda-bounty](https://github.com/szl-holdings/lambda-bounty) |
| [`prior-art/`](prior-art/) | Prior-art disclosures for IP protection | prior-art-disclosures |

---

## Thesis Lineage (v1 → v22)

The **intellectual provenance of SZL Holdings** — every governance claim traces to a versioned,
DOI-pinned thesis. See the canonical timeline: **[`thesis/THESIS_LINEAGE.md`](thesis/THESIS_LINEAGE.md)**.

- **22 thesis versions** (v1 2026-04-28 → v22 2026-06-03; v19 intentionally skipped).
- **Latest:** [v22 — Convergence](thesis/ouroboros/papers/v22/) — A5 axiom merge, Cauchy_ND partial closure, VCG truthfulness, SLSA L2, Innovation Rounds 10–11, Sim-to-Real benchmark (α=0.10).
- **Concept DOI (always-latest):** [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926).
- **Λ = Conjecture 1** — never a theorem; the uniqueness chain completes only when all Cauchy_ND sorries close on `main`.

---

## Doctrine

- **Doctrine v11 LOCKED** — 749 declarations / 14 unique axioms / 163 sorries
- **Kernel commit:** `c7c0ba17` (DO NOT BUMP)
- **Λ = Conjecture 1** — NEVER a theorem; all claims are honest per SLSA L1
- **Section 889 vendors:** Huawei, ZTE, Hytera, Hikvision, Dahua (exactly 5)
- **DCO required** on every commit: `Signed-off-by: Yachay <yachay@szlholdings.ai>`

---

## Consolidation Note

This repo was created 2026-06-03 by merging 4 previously separate repos:
- `puriq-preprint` → `preprints/puriq/`
- `ouroboros-thesis` → `thesis/ouroboros/`
- `lambda-bounty` → `bounty/`
- `prior-art-disclosures` → `prior-art/`

Original repos archived with redirect notices. Git history preserved in each source.

---

*Signed-off-by: Yachay <yachay@szlholdings.ai>*
