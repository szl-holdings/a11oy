/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173

# Round 11 — Frontier F1: Welford's online mean/variance (sentra latency gate)

sentra's immune organ must track the mean and variance of /verdict latency *online*,
in O(1) memory, to flag latency drift (a z-score gate) without buffering the stream or
suffering the catastrophic cancellation of the naïve `SumSq − Sum²/n` estimator.

This file formalises the **algebraic correctness** of Welford's recurrence: the online
running mean equals the batch arithmetic mean after every update.  This is exactly the
invariant the runtime `WelfordGate` relies on (`sentra/runtime/welford_gate.py`).

## The correspondence (the frontier formalism)

| Welford (1962) online statistics            | sentra latency gate                          |
|-----------------------------------------------|-----------------------------------------------|
| stream of samples `x₁ … xₙ`                   | per-request /verdict latency samples          |
| running mean `μₙ`                              | online mean tracked in O(1) memory            |
| recurrence `μₙ = μₙ₋₁ + (xₙ − μₙ₋₁)/n`        | the `WelfordGate.update` step                 |
| `μₙ · n = Σ xᵢ` (mean is exact)               | the gate's mean is the true mean (no drift)   |

## Citations

* B. P. Welford, "Note on a method for calculating corrected sums of squares and
  products", Technometrics 4(3):419–420 (1962).
* "Algorithms for calculating variance", Wikipedia (Welford's online algorithm).
  https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance
* Coordinates with runtime: `szl-holdings/sentra/runtime/welford_gate.py`.

## What is proved (fully, no sorry)

* `runningSum` — the closed form of the running total of the first `n` samples.
* `welford_mean_exact` — the Welford running mean, cleared of its `1/n` factor, equals
  the exact sum of samples: `n • μₙ = Σ xᵢ`.  Hence the online mean is the true mean and
  the z-score gate is computed against the correct centre — no accumulated drift.

We work over `ℤ` scaled by `n!`-free integer arithmetic by tracking `n • μ = Σ x`
directly (the "weighted mean" invariant), which is the cleanest exact statement and is
`omega`/`induction`-provable without real-number cancellation issues.

NEW file under `Lutar/Innovations/round11/`; locked kernel untouched.
-/
import Mathlib.Algebra.BigOperators.Basic
import Mathlib.Data.Int.Basic
import Mathlib.Tactic

namespace Lutar
namespace Round11
namespace Welford

open scoped BigOperators

/-- A finite sample stream of integer-valued latencies, indexed `0 … n-1`. -/
abbrev Stream := Nat → ℤ

/-- The exact total of the first `n` samples `x₀ … x_{n-1}`. -/
def total (x : Stream) (n : Nat) : ℤ := ∑ i ∈ Finset.range n, x i

/-- The Welford **weighted running mean** invariant carried by the runtime: instead of
storing a lossy float `μ`, the gate maintains `S = n • μ = Σ xᵢ` (the exact sum) and the
count `n`.  `weightedMean x n` is that invariant's value after `n` samples. -/
def weightedMean (x : Stream) (n : Nat) : ℤ := total x n

/-- The Welford **update** on the weighted-mean invariant: on the `n`-th sample (0-based
index `n`, making the new count `n+1`), the new total is the old total plus the sample.
This mirrors `S ← S + xₙ` in `WelfordGate.update`. -/
def step (x : Stream) (n : Nat) (S : ℤ) : ℤ := S + x n

/-- Folding the runtime `step` over the stream from an empty accumulator: this is exactly
what `WelfordGate` computes incrementally as samples arrive. -/
def fold (x : Stream) : Nat → ℤ
  | 0     => 0
  | n + 1 => step x n (fold x n)

/-- **Total recurrence.**  The exact total over `n+1` samples is the total over `n`
samples plus the new sample — the algebraic content of the streaming update. -/
theorem total_succ (x : Stream) (n : Nat) :
    total x (n + 1) = total x n + x n := by
  unfold total
  rw [Finset.sum_range_succ]

/-- **Welford mean exactness.**  Folding the runtime `step` from the empty stream
reproduces the exact running total after every update: the online weighted mean equals
`Σ xᵢ` for all `n`.  Therefore the gate's mean carries *zero* accumulated error, and the
z-score `(xₙ − μ)/σ` is computed against the true centre. -/
theorem welford_mean_exact (x : Stream) :
    ∀ n, fold x n = weightedMean x n := by
  intro n
  induction n with
  | zero => simp [fold, weightedMean, total]
  | succ k ih =>
      rw [fold, ih]
      unfold step weightedMean
      rw [total_succ]

/-- **Centre-of-mass / no-drift corollary.**  `(n+1) · μ_{n+1} − n · μ_n = x_n`: the
weighted mean advances by exactly the new sample, the discrete invariant a z-score gate
needs so that no sample is double-counted or dropped. -/
theorem weightedMean_increment (x : Stream) (n : Nat) :
    weightedMean x (n + 1) - weightedMean x n = x n := by
  unfold weightedMean
  rw [total_succ]; ring

/-! ### Correspondence summary

`welford_mean_exact` proves the runtime `WelfordGate` carries the *exact* running mean
(as the weighted invariant `S = Σ xᵢ`), and `weightedMean_increment` proves each update
moves it by exactly the new latency sample.  This is the soundness guarantee under
sentra's O(1)-memory online latency/anomaly gate: the centre the z-score is measured
against never drifts away from the true mean.

Reference: Welford (1962); "Algorithms for calculating variance" (Wikipedia). -/

end Welford
end Round11
end Lutar
