<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SZL Holdings — Λ-Conjecture Bounty · Sign: Yachay <yachay@szlholdings.dev> -->

# Λ-Conjecture Bounty

**Prove Conjecture 1 — the Λ-Aggregator Uniqueness conjecture — in Lean 4, using only an allowlisted set of classical axioms, and earn a place in the SZL Holdings thesis as a Lean co-author.**

> **Doctrine v11** — 749 declarations · 14 unique axioms · 163 sorries · `locked_at c7c0ba17`
> Λ is and remains **Conjecture 1**. It is **not** a theorem. This page is the academic framing; the community can *make* it a theorem — honestly, under public axiom audit.

> **Where to submit.** The working **intake + CI arbiter** lives in
> [`szl-holdings/lambda-bounty`](https://github.com/szl-holdings/lambda-bounty)
> (formal statement, `verify-proof` CI, submission template, live webhook). The
> founder-set **bounty declaration** lives in
> [`lutar-lean/BOUNTY.md`](https://github.com/szl-holdings/lutar-lean/blob/main/BOUNTY.md).
> This page is the academic "live home" — fork and PR against `lambda-bounty`, not this repo.

---

## What is Λ?

Λ is the **9-axis geometric-mean trust aggregator** at the apex of the SZL mesh anatomy (the *crown* unifier, formula **F23**). It takes a 9-axis trust vector and collapses it to a single trust scalar with one defining behaviour: **a single fully-failed axis vetoes trust** (weakest-link / zero-absorption). Across the mesh kernels — brain, heart, spine, immune, aide — Λ is the function that decides whether composed agentic trust holds.

We **conjecture** that four natural axioms pin Λ down *uniquely*:

| Axiom | Name | Meaning |
|------:|------|---------|
| **A1** | Idempotence | Aggregating a constant vector returns that constant. |
| **A2** | Monotonicity | Pointwise ≤ on inputs ⇒ ≤ on the aggregate. |
| **A3** | Symmetry | The aggregate is invariant under permutation of the 9 axes. |
| **A4** | Zero-absorption | If any axis is `0`, the aggregate is `0` (weakest-link). |

**Conjecture 1 (Λ-Aggregator Uniqueness).** Any two aggregators satisfying A1–A4 agree on every input.

```lean
theorem lambda_aggregator_unique
    (Λ₁ Λ₂ : Aggregator)
    (h₁ : SatisfiesAxioms Λ₁) (h₂ : SatisfiesAxioms Λ₂) :
    ∀ x : Axis → Nat, Λ₁ x = Λ₂ x := by
  sorry  -- ← discharge this, win the bounty
```

The formal statement lives in [`Lambda/Lambda.lean`](Lambda/Lambda.lean). The axiom allowlist lives in [`Lambda/Allowed_Axioms.lean`](Lambda/Allowed_Axioms.lean).

> **Provenance honesty.** Quechua/heritage names elsewhere in the SZL platform are *brand naming* and analogy only — no prior-art or mystical claims. The geometric-mean / weakest-link framing is classic aggregation theory; this conjecture is our concrete Lean formalization of the mesh's apex aggregator.

> **Soundness caveat (honest, for judges).** A1–A4 *alone* do **not** single out the geometric mean: `min` satisfies all four (idempotent, monotone, symmetric, zero-absorbing) yet `min ≠ geometric mean` (Aczél 1966; Kolmogorov–Nagumo–de Finetti 1930–31; `min` is the unique idempotent t-norm). The literal A1–A4 statement is therefore refuted by the `min` counterexample. A *provable* uniqueness theorem additionally needs **continuity + bisymmetry/associativity + homogeneity (or multiplicativity)**, after which the n-D Cauchy step (`CAUCHY_ND`) closes. Tightening the axiom set is a **founder decision**; until then the conjecture stands as an honest open problem and CI stays red.

---

## The rules

A **valid winning submission** is a pull request that makes CI ([`.github/workflows/verify-proof.yml`](.github/workflows/verify-proof.yml)) **green**. CI is the sole, automated, no-bypass arbiter. It requires **all** of:

1. **`lake build` is green** on Lean `v4.13.0` + Mathlib `v4.13.0` (pinned by [`lean-toolchain`](lean-toolchain) and [`lakefile.lean`](lakefile.lean)).
2. **No `sorry` / `sorryAx` anywhere** under `Lambda/`. (Until solved, `main` *intentionally* fails this gate — that failing state is the public signal that Conjecture 1 is still **OPEN**.)
3. **No axiom beyond the allowlist.** CI runs `#print axioms lambda_aggregator_unique` and rejects any dependency outside:
   - `propext` — propositional extensionality (Lean core)
   - `Quot.sound` — quotient soundness (Lean core)
   - `Classical.choice` — classical choice (Mathlib/Std foundation)
4. **No new `axiom` declarations**, and no `native_decide`-style compiler-trust escape hatches. `decide`, `omega`, `simp`, `ring`, etc. are all fine — they elaborate to the allowlisted foundations.

There is **no bypass**: branch protection requires the `verify-proof` check to pass before merge.

---

## How to submit

1. **Fork** [`szl-holdings/lambda-bounty`](https://github.com/szl-holdings/lambda-bounty) (the intake + arbiter repo — not this `szl-papers` page).
2. **Discharge the `sorry`** in `Lambda/Lambda.lean` with a real proof. You may add helper lemmas in new files under `Lambda/Submissions/` and import them, but the final `theorem lambda_aggregator_unique` must remain in `Lambda/Lambda.lean` and must be `sorry`-free.
3. **Run locally** to self-check before opening a PR:
   ```bash
   lake exe cache get        # fetch prebuilt Mathlib
   lake build                # must be green
   echo 'import Lambda.Lambda
   open Lambda
   #print axioms lambda_aggregator_unique' > _AxiomCheck.lean
   lake env lean _AxiomCheck.lean   # must show only propext / Quot.sound / Classical.choice
   ```
4. **Open a pull request** using the [submission template](submissions/SUBMISSION_TEMPLATE.md). Fill in your name (for thesis attribution), the proof strategy, and the `#print axioms` output.
5. CI runs automatically. **Green = eligible.**

---

## What you win

When a submission passes CI and is merged:

- 🏆 **Lean co-author** credit on the SZL Holdings thesis for the discharged Conjecture 1.
- 🪢 **Khipu-signed acceptance receipt** — a Wire-D / DSSE-signed record that your proof was verified and accepted (signed `Yachay <yachay@szlholdings.dev>`).
- 📚 **Citation in the thesis** and in the platform's Concept DOI lineage (Zenodo Concept `10.5281/zenodo.19944926`) — co-authorship on the next versioned DOI.
- 💵 **Cash bounty — amount TBD** (announced with the public launch; see *Hall of Fame* below for live status).
- 🥇 A permanent entry in the **Hall of Fame**.

---

## Hall of Fame

| # | Solver | PR | Accepted (Khipu receipt) | Axioms used |
|--:|--------|----|--------------------------|-------------|
| — | *open* | —  | —                        | —           |

*Conjecture 1 is currently **OPEN**. Be the first.*

---

## Repository layout

```
lambda-bounty/
├── Lambda.lean                  # library root (imports the conjecture + allowlist)
├── Lambda/
│   ├── Lambda.lean              # CONJECTURE 1 — the bounty target (with `sorry`)
│   ├── Allowed_Axioms.lean      # the axiom allowlist + its size lemma
│   └── Submissions/             # (optional) your helper lemmas go here
├── submissions/
│   └── SUBMISSION_TEMPLATE.md   # PR template — copy into your PR description
├── lakefile.lean                # Lean 4 + Mathlib v4.13.0
├── lean-toolchain               # leanprover/lean4:v4.13.0
├── .github/workflows/verify-proof.yml  # no-bypass CI arbiter
└── LICENSE                      # Apache-2.0
```

---

## License

Apache-2.0. See [LICENSE](LICENSE). By submitting, you license your contribution under Apache-2.0 and consent to thesis/DOI co-authorship attribution.

Signed — **Yachay** `<yachay@szlholdings.dev>` · SZL Holdings · Doctrine v11 (749 / 14 / 163 · `c7c0ba17`).
