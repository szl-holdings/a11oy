<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SZL Holdings — Λ-Conjecture Bounty · Sign: Yachay <yachay@szlholdings.dev> -->

# Λ-Uniqueness Bounty — Conjecture 1 (OPEN)

> **Honest posture.** The Λ-aggregator (PURIQ formula **F23**) is and remains
> **Conjecture 1**. It is **NOT a theorem**. This document declares the open
> conjecture and a **founder-set monetary bounty** for a complete, machine-checked
> Lean 4 proof. Until that proof lands, `main` of the bounty repo *intentionally*
> fails its proof gate — that red state is the public signal Conjecture 1 is still open.

- **Doctrine:** v11 — 749 declarations · 14 unique axioms · 163 sorries · `locked_at c7c0ba17`
- **Formula:** F23 — Λ-aggregator soundness / 9-axis geometric-mean uniqueness
- **Open obligation:** `Lutar/Uniqueness.lean:120` (`CAUCHY_ND` residual) + missing symmetry axiom
- **Submission repo (working intake + CI arbiter):** <https://github.com/szl-holdings/lambda-bounty>
- **Live submission webhook:** `POST https://szlholdings-a11oy.hf.space/api/lambda-bounty/submit` — **live** intake receiver (also `GET …/healthz` and `GET …/receipts`); see [`lambda-bounty/webhook/`](https://github.com/szl-holdings/lambda-bounty/tree/main/webhook). A receipt acknowledges **intake only**; eligibility is decided solely by `verify-proof` CI on a PR.

---

## The conjecture

Λ is the **9-axis geometric-mean trust aggregator** at the apex of the SZL mesh
anatomy (the *crown* unifier on the Lambda Spine). It collapses a 9-axis trust
vector to a single trust scalar, with one defining behaviour: **a single
fully-failed axis vetoes trust** (weakest-link / zero-absorption).

We **conjecture** that four natural axioms pin Λ down *uniquely*:

| Axiom | Name | Meaning |
|------:|------|---------|
| **A1** | Idempotence | Aggregating a constant vector returns that constant. |
| **A2** | Monotonicity | Pointwise ≤ on inputs ⇒ ≤ on the aggregate. |
| **A3** | Symmetry | The aggregate is invariant under permutation of the 9 axes. |
| **A4** | Zero-absorption | If any axis is `0`, the aggregate is `0` (weakest-link). |

**Conjecture 1 (Λ-Aggregator Uniqueness).** Any two aggregators satisfying A1–A4
agree on every input.

```lean
theorem lambda_aggregator_unique
    (Λ₁ Λ₂ : Aggregator)
    (h₁ : SatisfiesAxioms Λ₁) (h₂ : SatisfiesAxioms Λ₂) :
    ∀ x : Axis → Nat, Λ₁ x = Λ₂ x := by
  sorry  -- ← discharge this, win the bounty
```

The formal statement lives in
[`lambda-bounty/Lambda/Lambda.lean`](https://github.com/szl-holdings/lambda-bounty/blob/main/Lambda/Lambda.lean);
the partial in-tree progress (Aczel 1966 / Cauchy 1821 strategy, n-D `CAUCHY_ND`
residual) lives in [`Lutar/Uniqueness.lean`](./Lutar/Uniqueness.lean).

---

## The bounty

> **Founder-set amount.** The monetary award is set by the founder and published in
> the bounty repo's pinned issue. The placeholder below is replaced at publication
> by the founder; this document never invents a figure.

| Tier | Reward |
|---|---|
| **Complete sorry-free proof, axiom-allowlisted, CI-green** | 🏆 **`$<FOUNDER_SET_AMOUNT>`** (founder-set) **+** Lean co-author credit on the SZL Holdings thesis |
| **Materially-advancing partial (e.g. discharges `CAUCHY_ND`)** | pro-rata, founder discretion + acknowledgement |

A **valid winning submission** is a pull request to
[`lambda-bounty`](https://github.com/szl-holdings/lambda-bounty) that makes the
`verify-proof` CI **green**. CI is the sole, automated, no-bypass arbiter:

1. `lake build` green on Lean `v4.13.0` + Mathlib `v4.13.0`.
2. **No `sorry` / `sorryAx`** anywhere under `Lambda/`.
3. **No axiom beyond the allowlist** (`propext`, `Quot.sound`, `Classical.choice`) —
   checked via `#print axioms lambda_aggregator_unique`.
4. **No new `axiom` declarations** and no `native_decide` trust escape hatches.

---

## How to submit

Two equivalent intake paths — both produce a hash-chained **Khipu intake receipt**:

1. **Pull request** (canonical): fork `lambda-bounty`, discharge the `sorry`, open a PR
   with the [submission template](https://github.com/szl-holdings/lambda-bounty/blob/main/submissions/SUBMISSION_TEMPLATE.md).
   CI runs automatically; green = eligible.
2. **Webhook** (notify + pre-triage): `POST` your submission metadata to the live
   intake endpoint (schema in [`webhook/submission.schema.json`](https://github.com/szl-holdings/lambda-bounty/blob/main/webhook/submission.schema.json)).
   The receiver validates the payload, emits a signed intake receipt, and (when run
   with a token) opens a tracking issue. **A webhook receipt is an acknowledgement of
   intake only — eligibility is still decided solely by `verify-proof` CI on a PR.**

---

## Soundness caveat (honest, for judges)

The four axioms **A1–A4 alone do not single out the geometric mean**: `min` satisfies
all four (idempotent, monotone, symmetric, zero-absorbing) yet `min ≠ geometric mean`.
This is classical (Aczél 1966; Kolmogorov–Nagumo–de Finetti 1930–31; `min` is the
unique idempotent t-norm). So Conjecture 1 *in this literal A1–A4 form is refuted by
the `min` counterexample*. A **provable** uniqueness theorem additionally needs
**continuity + bisymmetry/associativity + homogeneity (or multiplicativity)**, after
which the n-D Cauchy step (`CAUCHY_ND`) closes the argument. Whether to tighten the
published axiom set (adding A5 bisymmetry / A6 continuity / A7 homogeneity) is a
**founder decision**. Until then the bounty stands as an honest open problem under
public axiom audit, and the `verify-proof` gate stays red. The live Λ endpoint reports
the 13-axis operational aggregate; the conjecture is stated for the general n-axis
(here 9-axis) form — the uniqueness question is independent of the axis count.

## Provenance honesty

Quechua/heritage names elsewhere in the SZL platform are **brand naming and analogy
only** — no prior-art or mystical claims. The geometric-mean / weakest-link framing
is classic aggregation theory; this conjecture is our concrete Lean formalization of
the mesh's apex aggregator. The bounty exists precisely so the community can turn
Conjecture 1 into a theorem **honestly, under public axiom audit**.

*Sign: Yachay <yachay@szlholdings.dev> · Doctrine v11 · Co-Authored-By: Perplexity Computer Agent*
