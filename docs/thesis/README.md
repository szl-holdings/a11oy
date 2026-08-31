# SZL Holdings — IP Provenance: Thesis Lineage & Proven Formula Kernel

**Proven-first.** This directory is the canonical, DOI-pinned record of the
intellectual property behind the SZL / a11oy substrate: the **v1 → v22 Ouroboros
thesis lineage** and the **machine-verified formula kernel** behind it.

**Author:** Stephen P. Lutar Jr. · ORCID
[0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)
**Concept DOI (always-latest):**
[10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926)

---

## Proven kernel (lead with what is proven)

The formula kernel is formalized in **Lean 4** in
[`szl-holdings/lutar-lean`](https://github.com/szl-holdings/lutar-lean)
(`Lutar/Puriq/Formulas/`). Honest status, verified bare-`lean` 4.13.0
(0 errors; 1 `sorry` = F23; no `sorryAx` in any proved theorem):

| Tier | Count | IDs |
|---|---|---|
| **Locked kernel (proven)** | **5** | F1, F11, F12, F18, F19 |
| Experimental sorry-free (Lean-core axioms only) | **21** | F1–F13, F15–F22 (distinct IDs) |
| Axiom-gated (declared crypto idealizations) | **3** | `f13_tamper_evident`, `f14_dsse_verifiable`, `f15_inclusion_binding` |
| **Conjecture** | **1** | **F23 (Λ-uniqueness) = Conjecture 1, NOT a theorem** |

> **Locked kernel proven = 5.** The 21 experimental sorry-free IDs are an
> engineering target and are **excluded from the locked count** until a formal
> re-audit under the authoritative `lake build` promotes them. The three
> axiom-gated results depend on **named, declared** crypto axioms
> (`hash_collision_resistant`, `ecdsa_unforgeable`, `h2_collision_resistant`) —
> these are idealizations, **not** proofs of cryptographic hardness.

### Λ = Conjecture 1

The Lutar Invariant **Λ** is **Conjecture 1 — never a theorem.** Unconditional
uniqueness is *false* under axioms A1–A5 (the 2-axis `max` aggregator is a
machine-checked counterexample). The conditional result
`lambda_unique_of_factors` **is** proved; unconditional uniqueness closes only
under the separately **declared** axiom `A6_bisymmetric`. See
[`lutar-lean`](https://github.com/szl-holdings/lutar-lean)
`Lutar/Puriq/Formulas/F23_Uniqueness.lean`.

---

## Thesis lineage (v1 → v22)

Every governance claim in the substrate traces to a versioned, DOI-pinned
thesis. The canonical timeline — each version, date, Zenodo DOI, and
contribution — is in [`THESIS_LINEAGE.md`](./THESIS_LINEAGE.md).

- **v19 is intentionally skipped** (version gap v18 → v20); there is no v19 paper
  or DOI. This is documented, not a missing artifact.
- **v22 "Convergence"** DOI is **pending founder mint**; the v22 PDF is archived
  in the thesis repo and will be Zenodo-pinned on mint. Its sources here are the
  Markdown ([`ouroboros-thesis-v22.md`](./ouroboros-thesis-v22.md)) and LaTeX
  ([`thesis_v22.tex`](./thesis_v22.tex)).

## Files in this directory

- [`THESIS_LINEAGE.md`](./THESIS_LINEAGE.md) — canonical v1 → v22 timeline (DOI-pinned).
- [`ouroboros-thesis-v22.md`](./ouroboros-thesis-v22.md) — v22 "Convergence" thesis (Markdown).
- [`thesis_v22.tex`](./thesis_v22.tex) — v22 LaTeX source.
- v22 PDF — **not committed here** (archived in the thesis repo); DOI pending founder mint.

## Machine-readable provenance

The app-facing, compact provenance feed is
[`static/thesis.json`](../../static/thesis.json): `{ versions[], proof_summary,
proven_formulas[] }`. The full formula/axiom/theorem knowledge graph lives in
[`packages/a11oy-knowledge/src/knowledge.json`](../../packages/a11oy-knowledge/src/knowledge.json)
(top-level `proof_summary` + `puriq_formulas`).

---

*Provenance compiled from `THESIS_LINEAGE.md` and the Lean proof report
(`PROOFS_WAVE2_REPORT.md`). Honesty doctrine: no conjecture is called a theorem;
locked proven count = 5.*
