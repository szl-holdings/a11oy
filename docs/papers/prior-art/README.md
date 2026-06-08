# Prior-Art Disclosures — SZL Holdings

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Doctrine v11 LOCKED](https://img.shields.io/badge/Doctrine-v11_LOCKED-d4a444.svg)](https://github.com/szl-holdings/lutar-lean)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19944926.svg)](https://doi.org/10.5281/zenodo.19944926)

[![Security Policy](https://img.shields.io/badge/Security-Policy-red.svg)](SECURITY.md)


<!-- CII-BEST-PRACTICES-BADGE: PENDING — replace 'PENDING' with the project id once founder registers this repo at https://bestpractices.coreinfrastructure.org/ -->
[![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/PENDING/badge)](https://bestpractices.coreinfrastructure.org/)

Public, timestamped defensive technical disclosures establishing prior art for the
PURIQ agentic-AI architecture. Publishing these methods places them in the public
record so they cannot be exclusively claimed by third parties.

## Contents

| File | Description |
|------|-------------|
| `main.tex` | IEEEtran-format technical disclosure (LaTeX source) |
| `main.pdf` | Compiled disclosure (2 pages) |
| `IEEEtran.cls` | IEEE conference document class (for reproducible compilation) |

## Disclosure: PURIQ Master Formula, 13-Axis Yuyay Gate, Khipu DAG

- **Disclosure date:** 2026-06-01 (EDT)
- **Concept DOI chain:** [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926)
- **Replay-hash anchor:** `bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5`

This disclosure publicly documents:

1. The PURIQ **master action-selection formula** `P(x,t) = argmax_a [ Λ(x) · Yuyay₁₃(a) · exp(−β·HUKLLA(a)) · ∏ᵢ Khipuᵢ(a) ]`.
2. The **13-axis Yuyay gate** — a conjunctive admissibility test (2 sacred axes ≥0.95, 7 structural ≥0.90, 4 introspection axes).
3. The **Khipu DAG** — a SHA-256 hash-chained receipt structure giving per-action provenance and an O(1) integrity tripwire (HUKLLA T01).

### Honest status

- Formal corpus: 749 Lean declarations, 14 unique axioms, **13 sorry-free (PROVED) theorems**, 163 raw sorries (open obligations), 23 extracted formulas.
- Λ-uniqueness is stated as **Conjecture 1**, not a theorem.
- Provenance level asserted: **SLSA L1** (honest).
- Load demonstration: 5.35M receipt writes/min; 100% chain-integrity tripwire on 504/504 injected corruptions.

## Reproducing the PDF

```sh
TEXMFVAR=/tmp/texmf-var pdflatex main.tex && TEXMFVAR=/tmp/texmf-var pdflatex main.tex
```

---

*Prepared by Yachay (Evaluation & Defense), on behalf of SZL Holdings.*

## SZL Holdings

![SZL Holdings](./branding/szl-avatar-animated.gif)

*Amaru — the Inca avatar of SZL Holdings. Animated mark (400×400, 16fps loop). Signed Yachay.*
