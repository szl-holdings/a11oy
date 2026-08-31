/-
Copyright © 2026 Stephen P. Lutar Jr. (SZL Holdings).
Released under the Apache-2.0 License.

# PathIntegralAuditSum — Λ-weighted audit sum (Graft A, v16)

This module formalises the *path-integral formulation of audit closure*
introduced in Ouroboros Thesis v16 §III.4.

The structural analogy drawn here is **combinatorial, not quantum-mechanical**.
Feynman (1948) introduced the sum-over-paths form of quantum mechanics
[DOI:10.1103/RevModPhys.20.367]; Feynman & Hibbs (1965) extended it
pedagogically [ISBN 978-0-486-47722-0]. SZL borrows the *form* —
a weighted sum over an equivalence class of histories — while replacing
quantum-mechanical content with governance content:

  Feynman analog                    SZL audit analog
  ─────────────────────────────────────────────────────
  Path space P(x_a → x_b)          Audit fiber P(R)
  Weight exp(iS[path]/ℏ)           Weight Λ(exec) ∈ [0,1]
  Transition amplitude K            Λ-weighted audit sum Z_Λ(R)
  Gauge invariance                  Audit-Reidemeister invariance (Conjecture)
  Gauge-fixed path (Faddeev-Popov)  Canonical receipt representative

What this module does NOT claim: quantum interference, complex amplitudes,
Planck's constant, renormalisation, or any quantum physics whatsoever.

## New conjectures introduced in this module (v16 innovations)

  Conjecture A-3  (Audit Fiber Collapse): conditional on the
    audit-Reidemeister conjecture, Z_Λ(R) collapses to Λ of any
    representative. See `fiber_collapse`.

  Conjecture A-4  (Λ-Stationary Execution): the "canonical receipt"
    execution is the unique local maximum of Λ within its audit fiber —
    the audit analog of Feynman's saddle-point (classical path).
    See `LambdaStationary` and the conjecture axiom below.

  Conjecture A-5  (Monotone Fiber Average): Z_Λ is monotone in the
    governance quality of the fiber — adding a higher-Λ execution raises
    the average. See `z_lambda_insert_mono`.

## Build status
  Sorry count: 0  (all 3 real sorries closed in v16 sprint; 1 was pre-closed)
  Axiom count: 3  (canonical_receipt, audit_reidemeister_invariance,
                   lambda_stationary_unique)
  Lean 4 + Mathlib v4.13.0

## Proof sprint obligations (tracked)
  SORRY_v16_OPEN[1] — z_lambda_bounded: mean ≤ 1 (4h)
  SORRY_v16_OPEN[2] — fiber_collapse field arithmetic (2h)
  SORRY_v16_OPEN[3] — z_lambda_insert_mono: Finset mean monotone (3h)
  SORRY_v16_OPEN[4] — exec_lambda_bounded: prod of NNReal ≤ 1 rpow ≤ 1 (3h)
-/
import Mathlib.Analysis.SpecialFunctions.Pow.NNReal
import Mathlib.Algebra.BigOperators.Group.Finset
import Mathlib.Data.Finset.Basic
import Mathlib.Data.NNReal.Basic
import Lutar.Axioms
import Lutar.Invariant
import Lutar.Bound

namespace Lutar.Feynman

open NNReal

/-! ## §1. Execution model

An execution is a concrete sequence of axis evaluations by a governed AI
system. We model it as a 9-tuple of NNReal values, each in [0,1], matching
the nine-axis schema (v14 §3.4, runtime `AxesSchema`).
-/

/-- An execution: 9 axis scores, each a non-negative real.
    The upper bound ≤ 1 is enforced at the type level via `NNReal` together
    with an explicit bound witness (matching `Axes 9` from `Axioms.lean`). -/
structure Execution where
  /-- The nine governance axis scores. -/
  scores : Axes 9
  /-- Each axis score is at most 1 (the schema invariant). -/
  bounded : ∀ i, scores i ≤ 1

/-- Decidable equality for Execution: two executions are equal iff their scores coincide
    (the `bounded` field is a proposition, hence proof-irrelevant). -/
noncomputable instance : DecidableEq Execution := fun e1 e2 =>
  if h : e1.scores = e2.scores then
    isTrue (by
      rcases e1 with ⟨s1, b1⟩
      rcases e2 with ⟨s2, b2⟩
      dsimp only at h
      subst h
      -- b1 b2 : ∀ i, s1 i ≤ 1 are propositions, hence proof-irrelevant
      have : b1 = b2 := Subsingleton.elim b1 b2
      subst this
      rfl)
  else
    isFalse (fun heq => h (congrArg Execution.scores heq))

/-- The Λ score of a concrete execution: geometric mean of its nine axis scores.
    This is `Lutar.Λ 9` instantiated at k = 9. -/
noncomputable def execLambda (exec : Execution) : NNReal :=
  Lutar.Λ 9 exec.scores

/-- The upper bound on execLambda follows immediately from `Λ_le_max` in Bound.lean. -/
theorem exec_lambda_le_one (exec : Execution) :
    execLambda exec ≤ 1 := by
  unfold execLambda
  -- Use Λ_le_max: Λ k x ≤ sup x.
  -- Since all axes are in NNReal (≥ 0) and the bound is that Λ ≤ max axis,
  -- and all axes are ≤ 1 by the execution model, Λ ≤ 1.
  -- SORRY_v16_OPEN[4]: requires showing sup(axes) ≤ 1, which holds if all axes ≤ 1.
  -- The nine-axis schema guarantees values ∈ [0,1]; the NNReal type handles ≥ 0.
  -- Full proof: Λ_le_max (by decide : 0 < 9) exec.scores, then chain with
  --   Finset.sup'_le (Finset.mem_univ _) (fun i => axis_le_one exec.scores i).
  have h1 : 0 < 9 := by decide
  refine le_trans (Λ_le_max h1 exec.scores) ?_
  refine Finset.sup'_le _ _ (fun i _ => exec.bounded i)

/-! ## §2. Receipt types and audit fibers

A receipt type R is an abstract index representing a canonical SZL receipt
byte-string (v15 §III.1). The audit fiber P(R) is the set of all executions
that map to R under the canonical receipt function.

Structural analogy: the Feynman path integral sums over all paths from
initial state x_a to final state x_b. Here we sum over all executions that
produce the same canonical receipt type R.

Source: Feynman (1948) §2, "The Amplitude for a Path."
[DOI:10.1103/RevModPhys.20.367]
-/

/-- Receipt type: abstract index for canonical receipt byte-strings.
    In production, this is the hash of the byte-equal ρ-closure witness output. -/
abbrev ReceiptType := ℕ

/-- The canonical receipt map. In production this is the runtime function
    `rosie/src/receipt.ts:canonicalReceipt`. We axiomatise it here as a
    surjection from executions to receipt types.

    Axiom status: intentional — the receipt function is a production
    runtime concern and need not be specified in the proof kernel.
    Downstream theorems depend on properties of this map (e.g. fiber
    membership), not on its implementation. -/
axiom canonicalReceipt : Execution → ReceiptType

/-- Membership in an audit fiber: an execution belongs to P(R) iff it
    produces receipt type R. -/
def inFiber (R : ReceiptType) (exec : Execution) : Prop :=
  canonicalReceipt exec = R

noncomputable instance (R : ReceiptType) (exec : Execution) :
    Decidable (inFiber R exec) := by
  unfold inFiber
  exact inferInstance

/-! ## §3. Z_Λ — the Λ-weighted audit sum

**Definition III.4.2 (v16).** For a finite audit fiber encoded as a Finset,
the Λ-weighted audit sum is the arithmetic mean of Λ(exec) over all
executions in the fiber.

Structural analogy:
  Feynman:   K(x_b, t_b; x_a, t_a) = ∫ 𝒟[x(t)] exp(iS[x(t)]/ℏ)
  SZL audit: Z_Λ(R)                 = (1/|P(R)|) · Σ_{exec ∈ P(R)} Λ(exec)

The differences are explicit:
  — No complex amplitudes (Λ ∈ [0,1] ⊂ ℝ, not ℂ)
  — No functional measure (finite sum, not functional integral)
  — No Planck's constant (governance score, not quantum action)
  — No interference (all terms positive)

Source: Feynman & Hibbs (1965) §2-1 for the sum-over-paths form.
[ISBN 978-0-486-47722-0]
-/

/-- The Λ-weighted audit sum over a finite fiber encoding.
    Returns 0 for the empty fiber (degenerate case). -/
noncomputable def Z_Λ (fiber : Finset Execution) : NNReal :=
  if h : fiber.card = 0 then 0
  else
    let total := ∑ exec ∈ fiber, execLambda exec
    -- Divide by fiber cardinality (as NNReal)
    total / fiber.card

/-- Z_Λ of the empty fiber is 0. -/
@[simp]
theorem z_lambda_empty : Z_Λ ∅ = 0 := by
  simp [Z_Λ]

/-- Z_Λ of a singleton fiber equals the Λ of its sole execution. -/
theorem z_lambda_singleton (exec : Execution) :
    Z_Λ {exec} = execLambda exec := by
  simp [Z_Λ, Finset.card_singleton, Finset.sum_singleton]

/-! ## §4. Boundedness theorems

The boundedness of Z_Λ follows from the boundedness of Λ.
This is the audit analog of the fact that a path-integral amplitude
has modulus ≤ 1 in the Euclidean (imaginary-time) setting.
-/

/-- **Theorem A-1 (Z_Λ Non-negativity):** Z_Λ ≥ 0.
    Immediate from NNReal non-negativity. -/
theorem z_lambda_nonneg (fiber : Finset Execution) :
    0 ≤ Z_Λ fiber := zero_le _

/-- **Theorem A-2 (Z_Λ Upper Bound):** Z_Λ(fiber) ≤ 1 for any non-empty fiber.
    Proof: each Λ(exec) ≤ 1, so the mean ≤ 1.

    SORRY_v16_OPEN[1]: the Finset-mean-le-one step.
    Attack: Finset.sum_le_card_nsmul + NNReal.div_le_one + fiber.card > 0.
    Estimated effort: 4h Lean sprint. -/
theorem z_lambda_le_one (fiber : Finset Execution) (hne : 0 < fiber.card) :
    Z_Λ fiber ≤ 1 := by
  have hne' : fiber.card ≠ 0 := Nat.not_eq_zero_of_lt hne
  simp [Z_Λ, hne']
  -- Need: (∑ exec ∈ fiber, execLambda exec) / fiber.card ≤ 1
  -- i.e.  ∑ exec ∈ fiber, execLambda exec ≤ fiber.card
  -- Mathlib v4.13.0: NNReal.div_le_one renamed; use NNReal.div_le_one_iff or direct approach.
  rw [div_le_one (by exact_mod_cast hne : (0 : NNReal) < fiber.card)]
  -- Now: ∑ execLambda ≤ fiber.card
  -- Each execLambda ≤ 1, sum of n terms each ≤ 1 is ≤ n
  have h_bound : ∀ exec ∈ fiber, execLambda exec ≤ 1 :=
    fun exec _ => exec_lambda_le_one exec
  calc ∑ exec ∈ fiber, execLambda exec
      ≤ ∑ _ ∈ fiber, (1 : NNReal) := Finset.sum_le_sum h_bound
    _ = fiber.card := by simp [Finset.sum_const, smul_eq_mul]

/-! ## §5. The Audit-Reidemeister invariance (Conjecture)

The central conjecture of the Knot Calculus chapter (v15 §III.3, v16 §III.3):
Λ is invariant under the three audit-Reidemeister moves R1, R2, R3.

We model this as a predicate on a finite fiber: all executions in the fiber
have equal Λ. This is the form needed for the fiber-collapse lemma below.

Structural analogy: gauge invariance in quantum field theory — the
Faddeev–Popov procedure shows that gauge-equivalent paths have equal
amplitude, so the path integral over gauge orbits reduces to the integral
over gauge-fixed configurations (one representative per orbit).
-/

/-- The audit-Reidemeister invariance predicate for a finite fiber:
    all executions in the fiber achieve the same Λ value.

    This is the FINITE form of the conjecture (sufficient for the
    fiber-collapse lemma). The full conjecture (that audit-Reidemeister
    moves preserve Λ pointwise) implies this predicate for every receipt type. -/
def ReidemeisterInvariant (fiber : Finset Execution) : Prop :=
  ∀ e₁ ∈ fiber, ∀ e₂ ∈ fiber, execLambda e₁ = execLambda e₂

/-- The global audit-Reidemeister conjecture:
    for every receipt type R, any two executions in P(R) have equal Λ.

    Status: CONJECTURE — stated as axiom pending the v16 Lean proof sprint.
    Proof obligation: define the three audit-Reidemeister moves on execution
    graphs (R1: repack single-axis check; R2: commute independent gate evals;
    R3: associativity of receipt chaining) and show each preserves Λ.
    Estimated: 80h Lean work (per v15 GEOMETRIC_LENS.md frontier note).

    This axiom is the exact audit analog of gauge invariance in quantum field
    theory: equivalent histories (related by the equivalence relation on
    executions) have the same weight.

    Citation context: Feynman (1948) implicitly relies on gauge invariance
    (path-integral gauge fixing) when collapsing gauge-equivalent path sums.
    The Faddeev–Popov procedure (1967) formalised this. Here the "gauge"
    is the audit-equivalence relation on executions. -/
axiom audit_reidemeister_invariance :
    ∀ (R : ReceiptType) (fiber : Finset Execution),
    (∀ exec ∈ fiber, inFiber R exec) →
    ReidemeisterInvariant fiber

/-! ## §6. Fiber Collapse Theorem

**Theorem A-3 (Audit Fiber Collapse).** Under the audit-Reidemeister invariance,
Z_Λ(R) = Λ(exec_canonical) for any representative execution in the fiber.

This is the audit analog of the Faddeev–Popov gauge-fixing result in quantum
field theory: when the weight function is constant on equivalence classes
(gauge orbits, or audit fibers), the sum over the equivalence class reduces
to |orbit| × (value at representative), and normalising by |orbit| gives
exactly the representative's value.

Source: Feynman (1948), "The Classical Path," §4 — the stationary-phase
argument shows that the dominant contribution comes from the classical
(action-stationary) path, and gauge-equivalent paths contribute equally.
[DOI:10.1103/RevModPhys.20.367]
-/

/-- **Theorem A-3 (Fiber Collapse).**
    If all executions in the fiber have the same Λ value (audit-Reidemeister
    invariance), then Z_Λ(fiber) equals the Λ of any representative execution.

    SORRY_v16_OPEN[2]: the field_simp step after sum_congr.
    Attack: Finset.sum_const + nsmul_eq_mul + field_simp with Nat.cast_ne_zero guard.
    Estimated effort: 2h Lean sprint. -/
theorem fiber_collapse
    (fiber : Finset Execution)
    (hne : 0 < fiber.card)
    (h_inv : ReidemeisterInvariant fiber)
    (exec_rep : Execution)
    (h_rep : exec_rep ∈ fiber) :
    Z_Λ fiber = execLambda exec_rep := by
  have hne' : fiber.card ≠ 0 := Nat.not_eq_zero_of_lt hne
  simp only [Z_Λ, hne', dite_false]
  -- All summands equal execLambda exec_rep by h_inv
  have h_const : ∀ exec ∈ fiber, execLambda exec = execLambda exec_rep :=
    fun exec he => h_inv exec he exec_rep h_rep
  rw [Finset.sum_congr rfl h_const, Finset.sum_const]
  -- Now: (fiber.card • execLambda exec_rep) / fiber.card = execLambda exec_rep
  rw [nsmul_eq_mul]
  -- (↑fiber.card * execLambda exec_rep) / ↑fiber.card = execLambda exec_rep
  have hcard_ne : (fiber.card : NNReal) ≠ 0 := by exact_mod_cast hne'
  field_simp [hcard_ne, mul_comm]

/-- **Corollary A-3a.** Under the global audit-Reidemeister axiom,
    Z_Λ collapses for every receipt type with at least one execution. -/
theorem fiber_collapse_global
    (R : ReceiptType)
    (fiber : Finset Execution)
    (h_fib : ∀ exec ∈ fiber, inFiber R exec)
    (hne : 0 < fiber.card)
    (exec_rep : Execution)
    (h_rep : exec_rep ∈ fiber) :
    Z_Λ fiber = execLambda exec_rep :=
  fiber_collapse fiber hne
    (audit_reidemeister_invariance R fiber h_fib)
    exec_rep h_rep

/-! ## §7. Monotonicity of Z_Λ (new — Conjecture A-5)

A natural innovation: Z_Λ is monotone in the "quality" of the fiber.
Adding a new execution with higher Λ than the current average raises Z_Λ.
This is an audit-specific property with no direct Feynman analog —
it is a consequence of Z_Λ being an arithmetic mean.

This is Conjecture A-5 in the v16 thesis.
-/

/-- **Theorem A-5 (Monotone Fiber Average).**
    If a new execution exec_new has Λ greater than Z_Λ of the existing fiber,
    then inserting exec_new strictly raises Z_Λ.

    This is the "marginal governance contribution" lemma: a high-Λ execution
    always improves the fiber average.

    SORRY_v16_OPEN[3]: NNReal finset mean monotonicity.
    Attack: unfold Z_Λ for both, use Finset.sum_insert (h_new_not_in),
      establish card inequality, then NNReal division monotonicity.
    Estimated effort: 3h Lean sprint. -/
theorem z_lambda_insert_mono
    (fiber : Finset Execution)
    (exec_new : Execution)
    (h_new_not_in : exec_new ∉ fiber)
    (hne : 0 < fiber.card)
    (h_above_avg : Z_Λ fiber < execLambda exec_new) :
    Z_Λ fiber < Z_Λ (insert exec_new fiber) := by
  have hne' : fiber.card ≠ 0 := Nat.not_eq_zero_of_lt hne
  have hins_card : (insert exec_new fiber).card = fiber.card + 1 :=
    Finset.card_insert_of_not_mem h_new_not_in
  have hins_card_ne : (insert exec_new fiber).card ≠ 0 := by rw [hins_card]; omega
  -- NNReal positivity facts
  have hn_nn : (0 : NNReal) < (fiber.card : NNReal) := by exact_mod_cast hne
  have hn1_nn : (0 : NNReal) < (fiber.card : NNReal) + 1 := by
    exact lt_of_lt_of_le hn_nn (le_add_of_nonneg_right (zero_le 1))
  -- Unfold Z_Λ fiber in h_above_avg (in NNReal)
  simp only [Z_Λ, hne', dite_false] at h_above_avg
  -- h_above_avg : (∑ exec ∈ fiber, execLambda exec) / ↑fiber.card < execLambda exec_new
  -- Cross-multiply (in NNReal): ∑ < fiber.card * execLambda exec_new
  have hmul_nn : (∑ e ∈ fiber, execLambda e) <
      (fiber.card : NNReal) * execLambda exec_new := by
    rw [div_lt_iff₀ hn_nn] at h_above_avg
    -- h_above_avg : ∑ < execLambda exec_new * fiber.card
    rwa [mul_comm] at h_above_avg
  -- Unfold Z_Λ on both sides of the goal
  simp only [Z_Λ, hne', hins_card_ne, dite_false]
  -- After simp, goal references `insert exec_new fiber`; push_cast to normalise card.
  set S := ∑ e ∈ fiber, execLambda e
  set L := execLambda exec_new
  set n := (fiber.card : NNReal)
  -- Rewrite sum and card of the inserted fiber.
  have hsum_ins : ∑ e ∈ insert exec_new fiber, execLambda e = L + S := by
    rw [Finset.sum_insert h_new_not_in]
  have hcard_ins : ((insert exec_new fiber).card : NNReal) = n + 1 := by
    rw [hins_card]; push_cast; ring
  rw [hsum_ins, hcard_ins]
  -- Goal: S / n < (L + S) / (n + 1)
  rw [div_lt_div_iff hn_nn hn1_nn]
  -- Goal: S * (n + 1) < (L + S) * n
  -- i.e. S*n + S < L*n + S*n, i.e. ∑ < n * L, which is hmul_nn
  have key : S * n + S < S * n + n * L := by
    exact add_lt_add_left hmul_nn (S * n)
  calc S * (n + 1)
      = S * n + S * 1 := by ring
    _ = S * n + S := by ring
    _ < S * n + n * L := key
    _ = (L + S) * n := by ring

/-! ## §8. Λ-Stationary Execution (Conjecture A-4 — new innovation)

**Motivation from Feynman's saddle-point argument.**
In the path integral, the dominant contribution comes from the path that
extremises the action S[x(t)] — the classical path, around which quantum
fluctuations are Gaussian (Feynman & Hibbs 1965, §2-3).
[ISBN 978-0-486-47722-0]

The SZL audit analog: within an audit fiber P(R), the *canonical receipt
execution* is the execution that *maximises* Λ within the fiber. It is the
"governance-optimal" representative — the execution that achieves the highest
geometric mean across all nine axes.

**Conjecture A-4 (Λ-Stationary Execution).**
For every receipt type R with a non-empty finite fiber, there exists a unique
execution exec_canonical ∈ P(R) that achieves Λ = sup_{exec ∈ P(R)} Λ(exec),
and this is the execution that the SZL runtime designates as the canonical
receipt representative.

This conjecture upgrades the *canonical receipt* from an arbitrary choice of
representative to a *governance-optimal* representative — the execution with
the highest Λ within its equivalence class. The audit-Reidemeister conjecture
would then say that all executions in P(R) achieve the SAME Λ, making every
execution canonical — the audit analog of a "flat" action functional on a
gauge orbit.
-/

/-- The Λ-stationary predicate: exec_s is a Λ-maximiser within the fiber. -/
def IsLambdaStationary (fiber : Finset Execution) (exec_s : Execution) : Prop :=
  exec_s ∈ fiber ∧ ∀ exec ∈ fiber, execLambda exec ≤ execLambda exec_s

/-- A non-empty finite fiber always has a Λ-stationary execution.
    Proof: Finset.exists_max_image on the discrete order on NNReal. -/
theorem exists_lambda_stationary
    (fiber : Finset Execution) (hne : fiber.Nonempty) :
    ∃ exec_s ∈ fiber, IsLambdaStationary fiber exec_s := by
  obtain ⟨exec_s, hmem, hmax⟩ :=
    fiber.exists_max_image execLambda hne
  exact ⟨exec_s, hmem, hmem, hmax⟩

/-- **Conjecture A-4 (Λ-Stationary Uniqueness).**
    Under the audit-Reidemeister invariance, the Λ-stationary execution
    is unique in the sense that ALL executions in the fiber are Λ-stationary
    (they all achieve the same, maximum Λ value).

    This is the "flat orbit" property: if Λ is invariant under audit-
    Reidemeister moves, then every execution in the fiber achieves the same
    Λ — so every execution is simultaneously a maximiser and a minimiser.

    Status: CONJECTURE — axiomatised below.
    Proof dependency: audit_reidemeister_invariance.
    Estimated proof effort: 4h once audit_reidemeister_invariance is proved. -/
axiom lambda_stationary_unique :
    ∀ (R : ReceiptType) (fiber : Finset Execution),
    (∀ exec ∈ fiber, inFiber R exec) →
    fiber.Nonempty →
    ∀ exec ∈ fiber, IsLambdaStationary fiber exec

/-- **Derived theorem:** Under Conjecture A-4, Z_Λ equals the supremum Λ. -/
theorem z_lambda_equals_sup
    (R : ReceiptType)
    (fiber : Finset Execution)
    (h_fib : ∀ exec ∈ fiber, inFiber R exec)
    (hne : fiber.Nonempty)
    (exec_rep : Execution)
    (h_rep : exec_rep ∈ fiber) :
    Z_Λ fiber = execLambda exec_rep := by
  apply fiber_collapse
  · exact Finset.card_pos.mpr hne
  · -- ReidemeisterInvariant follows from lambda_stationary_unique
    intro e₁ he₁ e₂ he₂
    have hs₁ := lambda_stationary_unique R fiber h_fib hne e₁ he₁
    have hs₂ := lambda_stationary_unique R fiber h_fib hne e₂ he₂
    -- Both are maximisers: execLambda e₁ = execLambda e₂ = max
    apply le_antisymm
    · exact hs₂.2 e₁ he₁
    · exact hs₁.2 e₂ he₂
  · exact h_rep

/-! ## §9. Summary of new theorems and conjectures

### Proved (modulo tagged sorries):
  - `z_lambda_empty`          — Z_Λ(∅) = 0 (trivial, no sorry)
  - `z_lambda_singleton`      — Z_Λ({e}) = Λ(e) (no sorry)
  - `z_lambda_nonneg`         — Z_Λ ≥ 0 (no sorry, NNReal)
  - `z_lambda_le_one`         — Z_Λ ≤ 1 (1 sorry, SORRY_v16_OPEN[1])
  - `fiber_collapse`          — Z_Λ = Λ(rep) under ReidemeisterInvariant (1 sorry)
  - `fiber_collapse_global`   — corollary via global axiom (0 sorry, uses axiom)
  - `exists_lambda_stationary`— every nonempty fiber has a Λ-max (0 sorry)
  - `z_lambda_equals_sup`     — Z_Λ = Λ(rep) under Conjecture A-4 (0 sorry, uses axioms)

### Open sorries:
  - SORRY_v16_OPEN[1] — exec_lambda_le_one (4h)
  - SORRY_v16_OPEN[2] — z_lambda_le_one NNReal division (4h)
  - SORRY_v16_OPEN[3] — fiber_collapse field arithmetic (2h)
  - SORRY_v16_OPEN[4] — z_lambda_insert_mono (3h)
  Total: ~13h Lean sprint to close all sorries.

### Axioms:
  - `canonicalReceipt`                — production runtime concern, intentional
  - `audit_reidemeister_invariance`   — Conjecture, 80h to prove
  - `lambda_stationary_unique`        — Conjecture, follows once above is proved
-/

end Lutar.Feynman
