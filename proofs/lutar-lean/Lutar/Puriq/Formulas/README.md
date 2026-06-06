# `Lutar/Puriq/Formulas/` — experimental scope (NOT folded into Doctrine v11)

This directory hosts **experimental, additive** Lean work that is intentionally
**excluded from the LOCKED Doctrine v11 baseline** of
**749 declarations · 14 unique axioms · 163 sorries**.

## Why this scope exists

Doctrine v11's numbers (`749 / 14 / 163`) are cited **verbatim** across the SZL
org: 32+ repositories, the org `README`, every `/healthz` surface, every ledger,
and the published **Ouroboros Thesis v20** (Zenodo). Those numbers are LOCKED.

Experimental theorem packs — discovered while building downstream runtimes — are
real and valuable, but they must **not** silently bump the v11 baseline, because
that would cascade a numbers change into every surface that cites v11. Until a
**planned Doctrine v12 release** folds them in (with a thesis update, an
all-repos sweep, a drift-gate baseline bump, an announcement, and a new Zenodo
Concept DOI), this work is staged here, outside the baseline count.

## What's here

- **`PuriqFormulaLean.lean`** — PURIQ-OS Agentic Formula Pack (Ouroboros Thesis
  v21). 23 catalogued formulas (F1..F23):
  - **5 PROVED** in Lean 4 with **no `sorry`** and **no axioms** beyond Lean
    core/`Init` (`F1`, `F11`, `F12`, `F18`, `F19`, stated over `Nat`/`Int` so they
    compile Mathlib-free).
  - **18 OPEN**, honestly tagged `SORRY_PURIQ_OPEN`, each with a discharge route
    in its docstring. None is claimed as a theorem in the thesis. `F23`
    (Λ-aggregator soundness) is explicitly **Conjecture 1** — not proved here.

## How the exclusion works (mechanism)

The canonical corpus counter `.github/scripts/lean_numbers.py` carries an
`EXPERIMENTAL_SCOPES` tuple. Any `.lean` file under a listed scope is skipped
when computing the guarded counts (`declarations`, `axioms_raw`,
`axioms_unique`, `sorries_raw`). `Lutar/Puriq/Formulas/` is one such scope.

The drift gate (`.github/workflows/lake-build.yml` →
`.github/scripts/check_numbers_drift.py`) therefore continues to assert the
LOCKED v11 baseline (`749 / 14 / 168` raw → public `749 / 14 / 163`) and stays
**green** while this experimental work accumulates.

> **`lake build` is unaffected.** This file is standalone — it is not part of the
> `Lutar` library import graph (`Lutar.lean`), so the kernel build neither
> compiles nor depends on it. The proofs here are checked separately and are
> preserved verbatim; **do not edit the proof content**.

## Graduating this scope into the baseline (Doctrine v12)

To fold this work into the baseline, in a **single** PR:

1. Remove the scope entry from `EXPERIMENTAL_SCOPES` in
   `.github/scripts/lean_numbers.py`.
2. Recompute and update `.github/data/lean_numbers.json` (explicit baseline bump).
3. Sweep all downstream repos / `/healthz` surfaces that cite the v11 numbers.
4. Update the thesis and mint a new Zenodo Concept DOI.

See `platform/docs/doctrine/v12-roadmap.md` for the v12 release plan.
