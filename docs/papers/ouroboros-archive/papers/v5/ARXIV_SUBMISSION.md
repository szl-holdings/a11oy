# arXiv Submission Plan — Ouroboros Thesis v5

**Document ID:** ARXIV-V5
**Author:** Stephen P. Lutar (SZL Holdings)
**Status:** Manuscript ready (`papers/v5/ouroboros-thesis-v5.md` + the v5-canonical/abstract/essay/onepager kit). This document is the operator's submission checklist for posting paper v5 to arXiv.

---

## 1. Why arXiv

1. **Citation surface.** A stable arXiv ID makes paper v5 citable from external code and academic work without depending on Zenodo's record URL.
2. **Priority date.** The arXiv timestamp establishes priority over the formal content of v5.
3. **Distribution.** arXiv pushes to Google Scholar, Semantic Scholar, ConnectedPapers, and the cs.SE / cs.AI mailing lists.

## 2. arXiv mechanics

### 2.1 Account
- Author: Stephen P. Lutar Jr.
- Affiliation: SZL Holdings · United States
- Email: stephen@szlholdings.com
- ORCID: `0009-0001-0110-4173` (already linked to existing arXiv submissions)

### 2.2 Categories
- **Primary:** `cs.SE` (Software Engineering)
- **Cross-list (priority order):**
  - `cs.AI` (Artificial Intelligence)
  - `cs.LO` (Logic in Computer Science)
  - `cs.CR` (Cryptography and Security)

### 2.3 License
- **CC-BY-4.0** (matches the Zenodo deposit and the repository).

### 2.4 Required artefacts
- LaTeX source `.tex` compiled from `papers/v5/ouroboros-thesis-v5.md` via pandoc (§3 below).
- Bibliography `.bib`: `papers/v5/references.bib`.
- Compiled PDF preview: `papers/v5/ouroboros-thesis-v5.pdf`.

## 3. Manuscript prep

```bash
# From repo root
pandoc papers/v5/ouroboros-thesis-v5.md \
  --from markdown \
  --to latex \
  --standalone \
  --bibliography papers/v5/references.bib \
  --citeproc \
  -o papers/v5/ouroboros-thesis-v5.tex
```

Then:

- [ ] Replace `\documentclass{article}` with `\documentclass[11pt]{article}`; single-column.
- [ ] Verify all references in `references.bib` resolve. **No fake references.**
- [ ] Verify the abstract `papers/v5/v5-abstract.txt` is ≤ 1920 characters.
- [ ] Add an "Author contributions" section (single author — state explicitly).

## 4. Submission checklist

- [ ] Confirm Zenodo record exists and is finalized: **DOI 10.5281/zenodo.20020846**.
- [ ] Verify the GitHub release tag `paper-v5-5.0.0` is published.
- [ ] Run `cffconvert --validate -i papers/v5/CITATION.cff` and confirm exit 0.
- [ ] Run `markdownlint papers/v5/` and confirm no errors.
- [ ] Submit to arXiv via web UI; copy the resulting identifier into this document.
- [ ] Update root `README.md` paper table with the arXiv ID once issued.

## 5. arXiv identifier (post-submission)

Paste the assigned arXiv ID here once received (e.g. `arXiv:2605.xxxxx`):

```
arXiv:____.____  (pending)
```

---

**Companion documents** (this kit):
- `ouroboros-thesis-v5.md` — primary canonical text
- `ouroboros-thesis-v5.pdf` — typeset PDF
- `v5-canonical.md` — canonical reference copy
- `v5-abstract.txt` — ≤1920-char arXiv abstract
- `v5-essay.md` — long-form narrative essay
- `v5-onepager.md` — single-page summary
- `CITATION.cff` — schema-1.2.0 citation file
- `references.bib` — BibTeX bibliography
