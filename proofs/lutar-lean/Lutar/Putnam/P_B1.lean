import Mathlib

namespace Lutar.Putnam.P_B1

/-!
# Putnam 2025 B1

**Problem:** Suppose that each point in the plane is colored either red or green,
subject to the following condition: for every three noncollinear points A, B, C of
the same color, the center of the circle passing through A, B, C is also this color.
Prove that all points of the plane are the same color.

**Proof technique (Contradiction + circle center closure):**
Assume both colors are used. Then there exist a red point R and a green point G.
Consider circles passing through red (or green) triples that force more and more
points to be red (resp. green). 

Key lemma: If R is a red point, then every circle centered at R has at most 2 green
points on it. (If 3 green points lay on a circle centered at R, the center R would
need to be green — contradiction.)

Similarly, if G is green, every circle centered at G has at most 2 red points.

Using this: take R red and G green at distance d. Consider 3 circles centered at R
of radii in (d/2, d). Each meets the circle centered at G at 2 points. By pigeonhole,
we get 3 collinear red points that are non-collinear (contradiction). 

The official proof uses the following: if R is red and G is green, then any circle
centered at a red point has ≤ 2 green points, so circles "proliferate" red/green
beyond the plane's capacity unless one color fills everything.

@[source] https://maa.org/wp-content/uploads/2026/02/2025OfficialSolutions.pdf
@[source] https://kskedlaya.org/putnam-archive/
@[difficulty] 2
-/

-- Color type
inductive Color where
  | red : Color
  | green : Color
  deriving DecidableEq

-- A coloring of the plane
abbrev Coloring := EuclideanSpace ℝ (Fin 2) → Color

-- The circumcenter of three noncollinear points
-- In Mathlib this is available via EuclideanGeometry
-- We use circumcenter from Mathlib.Geometry.Euclidean
open EuclideanGeometry in
/-- A coloring is "circle-closed" if for any three same-colored noncollinear points,
    their circumcenter is the same color. -/
def CircleClosed (c : Coloring) : Prop :=
  ∀ (A B C : EuclideanSpace ℝ (Fin 2)),
    ¬ Collinear ℝ ({A, B, C} : Set (EuclideanSpace ℝ (Fin 2))) →
    c A = c B → c B = c C →
    c (circumcenter ({A, B, C} : Finset (EuclideanSpace ℝ (Fin 2)))) = c A

/-- Main theorem: any circle-closed coloring is monochromatic -/
theorem putnam_B1_correct (c : Coloring) (hc : CircleClosed c) :
    (∀ p : EuclideanSpace ℝ (Fin 2), c p = Color.red) ∨
    (∀ p : EuclideanSpace ℝ (Fin 2), c p = Color.green) := by
  -- Key lemma: if R is red, every circle centered at R has ≤ 2 green points
  -- Proof by contradiction: if 3 green points G₁,G₂,G₃ on circle centered at R,
  -- then circumcenter(G₁,G₂,G₃) = R must be green. But R is red. Contradiction.
  by_contra h
  push_neg at h
  obtain ⟨hnotall_red, hnotall_green⟩ := h
  -- Get a red and a green point
  push_neg at hnotall_red hnotall_green
  obtain ⟨R, hR⟩ := hnotall_red
  obtain ⟨G, hG⟩ := hnotall_green
  -- The key argument: circles centered at red points have ≤ 2 green points
  -- This is the crucial lemma from the official proof
  sorry -- sorry_p_B1_main: requires detailed geometric argument

-- Key lemma: at most 2 opposite-colored points on any circle centered at a colored point
lemma at_most_two_opposite_on_circle (c : Coloring) (hc : CircleClosed c)
    (O : EuclideanSpace ℝ (Fin 2)) (r : ℝ) (hr : 0 < r)
    (col : Color) (hO : c O = col) :
    -- The number of points on the circle of radius r centered at O with color ≠ col
    -- is at most 2. (More precisely, no 3 noncollinear such points exist on the circle,
    -- which is trivially true if fewer than 3 exist, or by the circumcenter argument.)
    ∀ (P Q S : EuclideanSpace ℝ (Fin 2)),
      dist P O = r → dist Q O = r → dist S O = r →
      ¬ Collinear ℝ ({P, Q, S} : Set (EuclideanSpace ℝ (Fin 2))) →
      c P = col ∨ c Q = col ∨ c S = col := by
  sorry -- sorry_p_B1_circle_lemma: circumcenter of points on circle ∘ centered at O = O

-- Correctness of circumcenter: if P, Q, S lie on the circle centered at O,
-- then their circumcenter is O.
lemma circumcenter_of_circle_points (O : EuclideanSpace ℝ (Fin 2)) (r : ℝ)
    (P Q S : EuclideanSpace ℝ (Fin 2))
    (hP : dist P O = r) (hQ : dist Q O = r) (hS : dist S O = r)
    (hncol : ¬ Collinear ℝ ({P, Q, S} : Set (EuclideanSpace ℝ (Fin 2)))) :
    EuclideanGeometry.circumcenter ({P, Q, S} : Finset _) = O := by
  sorry -- sorry_p_B1_circumcenter: standard Euclidean geometry fact

/-!
## Summary
- `putnam_B1_correct`: TRACKED — 1 sorry (sorry_p_B1_main)
- `at_most_two_opposite_on_circle`: TRACKED — 1 sorry (sorry_p_B1_circle_lemma)
- `circumcenter_of_circle_points`: TRACKED — 1 sorry (sorry_p_B1_circumcenter)
- Definitions (`Color`, `CircleClosed`): REAL definitions
- Sorry count: 3 (sorry_p_B1_main, sorry_p_B1_circle_lemma, sorry_p_B1_circumcenter)
-/

end Lutar.Putnam.P_B1
