# arXiv Submission Bundle — Ouroboros Thesis v22 (Convergence)

**For: the founder (Stephen P. Lutar Jr.).** This directory is the arXiv-ready submission bundle for
thesis v22. Account minting, OBS/endorsement, and DOI minting are **founder-only** actions; the steps
below tell you exactly what to upload and what to fill in.

---

## Contents of `thesis_v22/arxiv/`
| File | Purpose |
|---|---|
| `thesis_v22.tex` | LaTeX source (reconstructed from the v22 PDF/markdown). arXiv requires source, not just PDF. |
| `references.bib` | BibTeX bibliography — all real, verifiable works (audited; no fabricated citations). |
| `00_README_ARXIV.md` | This file. |
| `thesis_v22.pdf` | Reference compiled PDF (existing canonical artifact). |

## How to compile (verify locally before upload)
```
pdflatex thesis_v22
bibtex   thesis_v22
pdflatex thesis_v22
pdflatex thesis_v22
```
Produces `thesis_v22.pdf`. Stock `article` + `amsmath`/`amssymb`/`booktabs`/`hyperref` only — no
Type-3 bitmap fonts, no nonstandard font packages (arXiv-safe).

## arXiv submission metadata (copy-paste)
- **Title:** The Ouroboros Thesis v22 — Convergence: An Honest, Audit-Ready Convergence of the
  Λ-Aggregator Uniqueness Chain, Mechanism Truthfulness, and Sim-to-Real Doctrine Transfer
- **Author:** Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173), SZL Holdings, Inc.
- **Primary category:** `cs.LO` (Logic in Computer Science). **Cross-list:** `math.OC`, `cs.CR`, `cs.LG`.
- **MSC2020:** 39B22 (primary), 26E60, 91B26, 68V20, 94A17. **ACM:** F.4.1, F.2.0.
- **License:** CC BY 4.0.
- **Abstract:** use the `\begin{abstract}` block in `thesis_v22.tex` (1109 chars — under arXiv's 1920 limit).
- **Comments field (suggested):** "Λ-aggregator uniqueness is stated as Conjecture 1, not a theorem.
  Lean 4 + Mathlib formalization at github.com/szl-holdings/lutar-lean. Doctrine v11 LOCKED 749/14/163."

## Founder-only actions (NOT done by the agent)
1. **Mint / sign in to the arXiv account** under your name and obtain endorsement for `cs.LO` if needed
   (On-Behalf-of-Submitter / OBS is a founder action).
2. **Mint the v22 version DOI** on Zenodo via the `paper-v22-1.0.0` release. Then add
   `\doi{}` or note it in the arXiv comments. Concept DOI `10.5281/zenodo.19944926` already resolves.
3. **Pin the Walrus reference**: replace the `walrus2025` placeholder in `references.bib` with a
   resolvable arXiv ID/DOI for the Polymathic AI Walrus physical foundation model before final submit
   (it is cited only as a modeling analogy, so this is non-blocking for a v1 preprint but recommended).
4. **Upload** `thesis_v22.tex` + `references.bib` (and optionally the reference PDF) as the source
   package. Do NOT upload PDF-only — arXiv will reject a TeX-origin paper without source.

## Doctrine guardrails honored in this bundle
- Λ = **Conjecture 1, NEVER a theorem** — stated as such in title-block banner, abstract, §2, §3.
- A5 is a **structure field**, not a new axiom — unique-axiom count stays **14**.
- SLSA **L1 + L2 attested; NOT L3.**
- Doctrine v11 LOCKED **749/14/163 @ c7c0ba17** — not bumped.
- No fabricated citations; every open `sorry` is honestly classified.

*Signed-off-by: Yachay <yachay@szlholdings.ai>*
*Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>*
