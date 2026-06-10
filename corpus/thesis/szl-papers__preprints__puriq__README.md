# PURIQ: A Master Formula for Agentic AI under Provable Provenance

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Doctrine v11 LOCKED](https://img.shields.io/badge/Doctrine-v11_LOCKED-d4a444.svg)](https://github.com/szl-holdings/lutar-lean)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19944926.svg)](https://doi.org/10.5281/zenodo.19944926)

[![Security Policy](https://img.shields.io/badge/Security-Policy-red.svg)](SECURITY.md)


<!-- CII-BEST-PRACTICES-BADGE: PENDING — replace 'PENDING' with the project id once founder registers this repo at https://bestpractices.coreinfrastructure.org/ -->
[![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/PENDING/badge)](https://bestpractices.coreinfrastructure.org/)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19944926.svg)](https://doi.org/10.5281/zenodo.19944926)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

> The DOI badge above shows a placeholder until the first GitHub release triggers
> the **GitHub–Zenodo auto-mint** integration. After the first release, replace
> `PLACEHOLDER` with the version DOI that Zenodo assigns (Zenodo also provides the
> exact Markdown badge on the record page). The concept DOI for the Ouroboros line
> is `10.5281/zenodo.19944926`. See [`ZENODO_AUTO_MINT_SETUP.md`](ZENODO_AUTO_MINT_SETUP.md).

This repository is the **canonical, standalone citation** for the **PURIQ** formula —
an additive agentic-action layer extending the formally verified *Doctrine v11* substrate (749/14/163) of the Ouroboros line of work.

## What PURIQ is

PURIQ (Quechua *puriq*, "the one who acts") selects an action by maximizing the
product of four factors:

```
P(x, t) = argmax_{a in A} [ Λ(x) · Yuyay₁₃(a) · e^(−β·HUKLLA(a)) · ∏ᵢ Khipuᵢ(a) ]
```

1. **Λ(x)** — a positive-homogeneous (A2), bounded (A4) weighted geometric-mean aggregator.
2. **Yuyay₁₃(a)** — the canonical 13-axis conjunctive gate; `0` if any axis is below its floor.
3. **e^(−β·HUKLLA(a))** — an exponential penalty over ten HUKLLA halt-tripwires.
4. **∏ᵢ Khipuᵢ(a)** — the product of Khipu Merkle-DAG receipt verifications; `0` unless the
   action's entire provenance chain verifies.

The product form makes each factor a **multiplicative veto**: a gate failure or a single
unverifiable receipt zeroes the score, so an inadmissible or unprovenanced action can never
be selected.

## Contents

| File | Description |
|------|-------------|
| `main.tex` | LaTeX source of the preprint (IEEE two-column layout). |
| `main.pdf` | Compiled preprint (8 pages). |
| `bibliography.bib` | Reference database (primary mathematical, cryptographic, and standards sources). |
| `.zenodo.json` | Zenodo deposition metadata, read by the GitHub–Zenodo auto-mint integration on release. |
| `CITATION.cff` | Citation metadata. |
| `LICENSE` | CC-BY-4.0. |
| `ZENODO_AUTO_MINT_SETUP.md` | How DOIs are minted automatically via the GitHub–Zenodo integration. |

## Doctrine v11 LOCKED numbers (preserved verbatim)

This work is **strictly additive** to the Doctrine v11 substrate. The audited corpus state is
preserved unchanged:

- **749** Lean declarations
- **14** unique axioms
- **163** sorry obligations (112 baseline + 51 Putnam)
- Replay hash `bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5`
- Spine axioms **A2 = IsHomogeneous**, **A4 = IsBounded**; supply-chain posture **SLSA L1**
- Λ-uniqueness taxonomy: *governance-safe* uniqueness is **Theorem U** (proven, conditional, axiom-free — unique *modulo* `≈Λ` under the Identifiability Assumptions, strict `=` only under `Anchored`/`Normalized`; [`Lutar/Uniqueness/TheoremU.lean`](https://github.com/szl-holdings/lutar-lean/blob/main/Lutar/Uniqueness/TheoremU.lean)); *unconditional* uniqueness stays **Conjecture 1 — OPEN** (machine-checked false as stated, not a theorem)

PURIQ adds four **net-new** sorry-tagged obligations (`SORRY_PURIQ_OPEN[24..27]`) and **no new axiom**.

## Companion dataset

The 13-axis label set referenced by the paper is published at
[`SZLHOLDINGS/yuyay-v3-axis-labels-v1`](https://huggingface.co/datasets/SZLHOLDINGS/yuyay-v3-axis-labels-v1)
(500 examples, 400/100 train/eval split, CC-BY-4.0).

## Building the PDF

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

`IEEEtran.cls` is emulated with the base `article` class; switching `\documentclass`
to `{IEEEtran}[conference]` requires no body changes.

## How to cite

See `CITATION.cff`, or:

> Lutar, S. P., Jr. (2026). *PURIQ: A Master Formula for Agentic AI under Provable
> Provenance.* SZL Holdings. Concept DOI: 10.5281/zenodo.19944926.

## License

Released under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

---

Author: Stephen P. Lutar Jr. (Yachay).
Co-authored-by: Perplexity Computer Agent.

## SZL Holdings

![SZL Holdings](./branding/szl-avatar-animated.gif)

*Amaru — the Inca avatar of SZL Holdings. Animated mark (400×400, 16fps loop). Signed Yachay.*
