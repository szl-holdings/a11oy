/-
# R4-C2 — Liu Hui polygon-doubling π converges

Liu Hui (3rd c. CE, *Jiu Zhang Suanshu* commentary) computed `π` by
inscribed regular polygon doubling: starting from the regular hexagon
(`s₆ = 1` on the unit circle) and applying `s_{2k}² = 2 - √(4 - s_k²)`,
the 96-gon (`k = 4`) gives the classical bound
`3.141024 < π < 3.142704`.

The sequence `π_n := n · s_n / 2` is monotonically increasing in `n`
(more sides ⇒ closer to the inscribed-arc length) and bounded above by
`π`, hence convergent. This is the twin contraction lineage to the
Babylonian sqrt (R3-G1).

Citations:
- Cullen, C. (1996). *Astronomy and Mathematics in Ancient China.* CUP.
- Martzloff, J.-C. (1997). *A History of Chinese Mathematics.* Springer.

Status: skeleton; monotone-bounded convergence is recorded with a tagged
`sorry` deferring to the monotone-convergence theorem in Mathlib.
-/
import Mathlib.Analysis.SpecialFunctions.Pow.Real
import Mathlib.Data.Real.Sqrt

/- **Namespace note (PhD audit 2026-05-29):** This file lives under `Lutar.Banach` because
   Liu Hui's polygon-doubling recurrence `s_{2k}² = 2 - √(4 - s_k²)` is a *contractive iteration*
   on the interval [0,4]: each step halves the geometric error relative to the circle's arc length.
   This is the Banach Fixed-Point structure (the fixed point is `s² = 0`, corresponding to the
   unit-circle inscribed polygon collapsing to a point as k → ∞). The *practical* fixed point
   under the rescaled limit `liuHuiPi k → π` relates to the contraction sequence.
   Liu Hui (3rd c. CE) discovered this recurrence geometrically; the Banach framing is a modern
   formal-verification lens on his original construction. These are distinct mathematical traditions
   and the namespace label reflects the verification structure, not a claim that Liu Hui knew
   Banach's theorem (which is 20th century). -/
namespace Lutar.Banach.LiuHui

open Real

/-- Squared inscribed-side length at the `k`-th polygon-doubling, starting
    from the regular hexagon (`s₆ = 1`, `s₆² = 1`). -/
noncomputable def sideSquared : ℕ → ℝ
  | 0     => 1
  | n + 1 => 2 - Real.sqrt (4 - sideSquared n)

/-- Number of sides at doubling step `k`:  `n_k = 6 · 2^k`. -/
def sideCount (k : ℕ) : ℕ := 6 * 2 ^ k

/-- Inscribed-polygon estimate of `π` at doubling step `k`. -/
noncomputable def liuHuiPi (k : ℕ) : ℝ :=
  (sideCount k : ℝ) * Real.sqrt (sideSquared k) / 2

/-- The 96-gon (Liu Hui's documented choice): `k = 4` since `6 · 2^4 = 96`. -/
noncomputable def liuHui96Gon : ℝ := liuHuiPi 4

/-- `sideSquared n ∈ [0, 4]` for all `n` (well-definedness of the recurrence). -/
theorem sideSquared_bounds : ∀ n, 0 ≤ sideSquared n ∧ sideSquared n ≤ 4 := by
  intro n
  induction n with
  | zero =>
    constructor
    · -- 0 ≤ sideSquared 0 = 1
      unfold sideSquared; norm_num
    · -- sideSquared 0 = 1 ≤ 4
      unfold sideSquared; norm_num
  | succ n ih =>
    obtain ⟨h0, h4⟩ := ih
    unfold sideSquared
    have hsub_nn : 0 ≤ 4 - sideSquared n := by linarith
    have hsub_le : 4 - sideSquared n ≤ 4 := by linarith
    have hsqrt_nn : 0 ≤ Real.sqrt (4 - sideSquared n) := Real.sqrt_nonneg _
    have hsqrt_le_2 : Real.sqrt (4 - sideSquared n) ≤ 2 := by
      have hle : Real.sqrt (4 - sideSquared n) ≤ Real.sqrt 4 :=
        Real.sqrt_le_sqrt hsub_le
      have h4sqrt : Real.sqrt 4 = 2 := by
        rw [show (4:ℝ) = 2^2 by norm_num]
        exact Real.sqrt_sq (by norm_num : (0:ℝ) ≤ 2)
      linarith
    refine ⟨by linarith, by linarith⟩

/-- **Liu Hui π convergence (axiomatised pending the v18 half-angle proof).**

    The sequence `liuHuiPi` is monotone increasing and bounded above by `π`,
    hence convergent by monotone-bounded convergence (Mathlib4
    `tendsto_atTop_of_monotone_of_bounded`). The classical limit is `π`.

    Status: AXIOM-TAGGED, honest §XVII obligation deferred to v18.
    Justification: the proof requires the half-angle identity
      `sin(θ/2) = √((1 - cos θ)/2)`
    plus a Cauchy-criterion argument linking sideSquared to `4 sin²(π/n_k)`;
    estimated 40h Lean sprint.
    Liu Hui's original argument (*Jiu Zhang Suanshu* commentary, c. 263 CE)
    is geometric, not within the scope of v17.

    Citation: Martzloff, J.-C. (1997). *A History of Chinese Mathematics.*
    Springer, §3.3. Cullen, C. (1996). *Astronomy and Mathematics in
    Ancient China.* CUP, §2.4.

    Proof obligation reference: §XVII.RC1 (v18 sprint backlog). -/
axiom liu_hui_pi_converges :
    ∃ L : ℝ, ∀ ε > 0, ∃ N : ℕ, ∀ k ≥ N, |liuHuiPi k - L| < ε

end Lutar.Banach.LiuHui
