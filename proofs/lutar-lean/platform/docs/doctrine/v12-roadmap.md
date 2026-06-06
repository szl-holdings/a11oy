# Doctrine v12 — Roadmap (DRAFT / open-ended)

> **Status:** planning only. **Doctrine v11 remains LOCKED** at
> **749 declarations · 14 unique axioms · 163 sorries**. Nothing in this document
> changes any live number. v12 is a *future* release that will be cut
> deliberately, not by accident of drift.

## Purpose

v11's numbers (`749 / 14 / 163`) are cited **verbatim** across the SZL org: 32+
repositories, the org `README`, every `/healthz` surface, every ledger, and the
**published Ouroboros Thesis v20** (Zenodo Concept DOI). Bumping them is a
high-blast-radius event. v12 is the controlled vehicle for that bump — it folds
accumulated **experimental** Lean work into a new locked baseline, with a full
sweep, thesis update, and a fresh Zenodo Concept DOI.

## What v12 folds in (current candidate scope)

Experimental scopes currently excluded from the v11 baseline by the canonical
counter (`.github/scripts/lean_numbers.py` → `EXPERIMENTAL_SCOPES`):

| Scope | Contents | Δ declarations | Δ sorries (raw) |
|---|---|---|---|
| `Lutar/Puriq/Formulas/` | PURIQ-OS Agentic Formula Pack (Thesis v21): `PuriqFormulaLean.lean` — **5 PROVED** (`F1, F11, F12, F18, F19`) + **18 `SORRY_PURIQ_OPEN`** | +27 | +20 |
| `Lutar/Putnam/BekensteinBound.lean` | Bekenstein-bound scaffold (additive): 1 proved arithmetic anchor + 1 tracking conjecture sorry | +5 | +5 |

> Measured impact if folded in **today** (informational, NOT locked):
> `749 → 781` declarations, `168 → 193` raw sorries (`163` public → ~`188`).
> These numbers will be **recomputed at v12 cut time** — they will have moved as
> open obligations are discharged.

## Trigger (coherence threshold)

v12 is cut when the experimental scope reaches a coherence threshold, e.g.:

- **50+ new theorems** accumulated across experimental scopes, **AND**
- a meaningful **sorry-reduction** in those scopes (target: ≥ 60% of
  `SORRY_PURIQ_OPEN` obligations discharged into real proofs), **AND**
- the Λ-aggregator (`F23` / **Conjecture 1**) has a credible discharge route or a
  decision to ship it as a labelled conjecture.

Until then, experimental work accumulates **outside** the v11 baseline and the
drift gate stays green.

## Release checklist (all in one coordinated wave)

1. **Counter:** remove the graduated scopes from `EXPERIMENTAL_SCOPES` in
   `.github/scripts/lean_numbers.py`.
2. **Baseline:** recompute and update `.github/data/lean_numbers.json` (explicit,
   reviewable baseline bump in the same PR).
3. **Repo sweep:** update every downstream repo, the org `README`, and **every
   `/healthz`** surface that cites `749 / 14 / 163` → the new v12 numbers.
4. **Thesis:** publish an updated Ouroboros Thesis and mint a **new Zenodo
   Concept DOI**.
5. **Announcement:** post the v12 doctrine release note (lake build sweep
   confirmation + new numbers).
6. **Gate:** confirm `lake-build.yml` drift gate is green against the new
   baseline on `main`.

## Target date

**Open-ended.** Explicitly **not before Warhacker**. v12 ships when the
coherence threshold is met, not on a calendar.

---

*This roadmap is documentation only. The locked v11 numbers (`749 / 14 / 163`)
are unchanged by this file.*
