# Proof — Lean kernel, data lake, and DOIs

Every SZL claim is meant to be checked. This page is the **proof index**: the machine-checked
Lean kernel, the public attestation lake, and the persistent Zenodo DOIs. For the full
reproduction commands and commit anchors, see [Evidence](/evidence/).

> Doctrine v11 **LOCKED** — 749 declarations / 14 unique axioms / 163 tracked sorries ·
> kernel `c7c0ba17`. **Λ = Conjecture 1** (not a theorem). **SLSA L1 honest** (cosign-signed, keyless Sigstore — L2 provenance attestation is roadmap, not yet claimed).

## Lean kernel — `lutar-lean`

The machine-checked proof corpus.

- **Repo:** [`szl-holdings/lutar-lean`](https://github.com/szl-holdings/lutar-lean) — `Lutar/`
- **Locked snapshot:** tag `lutar-v18.0.0` / `c7c0ba17` — **749 / 14 / 163** (`lake build` clean)
- **Key files:** `Lutar/Axioms.lean` (A1–A4), `Lutar/Khipu/SummationInvariant.lean`,
  `Lutar/QEC/KitaevSurface`, `Lutar/DPI/DPIBound.lean` (Pinsker)
- **PURIQ obligations:** `formulas/PuriqLean.lean` — `puriq_halting_safety`,
  `puriq_lambda_monotone`, `puriq_khipu_integrity`, `puriq_bekenstein_bound` (all `sorry`-tagged, never hidden)

Reproduce the canonical figures yourself:

```bash
gh repo clone szl-holdings/lutar-lean /tmp/lutar -- --depth 1
cd /tmp/lutar
DECL=$(grep -rE '^(theorem|lemma|def|abbrev|axiom) ' --include='*.lean' Lutar/ | wc -l)
SORRY=$(grep -rE '\bsorry\b' --include='*.lean' Lutar/ | wc -l)
echo "Lean: $DECL declarations / $SORRY sorries"
```

> **Honest scope.** `lake build` requires Mathlib (~12 GB); the sandbox cannot build it, so
> Lean verification is performed in **GitHub Actions CI only**. Λ uniqueness remains a
> **Conjecture** — it depends on the open `CAUCHY_ND` sorry (`Uniqueness.lean:120`) plus a
> missing symmetry axiom.

## Data lake — `szl-lake`

The public attestation lake: DSSE receipts, doctrine snapshots, Khipu chains, SBOMs, and
evaluation trajectories.

- **GitHub:** [`szl-holdings/szl-lake`](https://github.com/szl-holdings/szl-lake)
- **Hugging Face:** [`SZLHOLDINGS/szl-lake`](https://huggingface.co/datasets/SZLHOLDINGS/szl-lake)
- **Layout (7 dirs):** `attestations/` · `doctrine/` · `keys/` · `khipu/` · `papers/` · `sboms/` · `trajectories/`
- **Lean companion DOI:** [10.5281/zenodo.20424992](https://doi.org/10.5281/zenodo.20424992)

## Zenodo DOIs

The Ouroboros Thesis and supporting artifacts are deposited with persistent DOIs.

| DOI | Role |
|-----|------|
| [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276) | **Ouroboros Thesis v18.0** (versioned) — cited by every flagship |
| [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926) | **Concept DOI** (always-latest) |
| [10.5281/zenodo.20424992](https://doi.org/10.5281/zenodo.20424992) | Lean companion |
| [10.5281/zenodo.20434308](https://doi.org/10.5281/zenodo.20434308) · [20431181](https://doi.org/10.5281/zenodo.20431181) | Supporting artifacts |

A complete, versioned list is maintained in the thesis repository's `CITATION.cff`. The
[Evidence page](/evidence/) carries the full DOI register and commit anchors.

---
*Doctrine v11 LOCKED · 749/14/163 · kernel c7c0ba17 · Λ = Conjecture 1 · SLSA L1 honest (L2 provenance attestation = roadmap)*
