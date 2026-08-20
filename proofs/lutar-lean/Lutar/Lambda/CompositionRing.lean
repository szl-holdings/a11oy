/-
# R4-I3 — Brahmagupta–Fibonacci 2-square composition identity

Brahmagupta (598–668 CE), in the *Brāhmasphuṭasiddhānta* (628 CE),
recorded the two-square multiplication identity

  (a² + b²)(c² + d²) = (ac − bd)² + (ad + bc)²

— rediscovered by Fibonacci in the *Liber Quadratorum* (1225 CE)
[Plofker 2009, *Mathematics in India*, Princeton UP §5; Sigler 1987 trans.,
*Fibonacci's Liber Quadratorum*, Academic Press, ISBN 978-0126431308].

The identity certifies that the sum-of-squares norm `a² + b²` is
multiplicative under the bilinear product `(a,b)·(c,d) := (ac−bd, ad+bc)`,
which is the Λ-category composition rule for 2-vector certificates.

Runtime counterpart:
  `a11oy/web/packages/a11oy-core/src/lambda/composition-ring.ts`.

Sources:
  * Brahmagupta (628 CE), *Brāhmasphuṭasiddhānta*, ch. 18.
  * Fibonacci, Leonardo (1225 CE), *Liber Quadratorum*; trans.
    Sigler, L. E. (1987), Academic Press, ISBN 978-0126431308.
  * Plofker, K. (2009), *Mathematics in India*, Princeton UP,
    ISBN 978-0691120676, §5.
  * Dickson, L. E. (1919), *History of the Theory of Numbers*, vol. II,
    Carnegie Inst. of Washington, ch. VI.
-/
import Mathlib.Tactic.Ring
import Mathlib.Tactic.Linarith
import Mathlib.Algebra.Order.Ring.Defs

namespace Lutar.Lambda

/-- **R4-I3 theorem.** Brahmagupta–Fibonacci 2-square composition
    identity over any commutative ring. Closed by `ring`. -/
theorem brahmagupta_fibonacci_identity
    {R : Type*} [CommRing R] (a b c d : R) :
    (a^2 + b^2) * (c^2 + d^2)
      = (a*c - b*d)^2 + (a*d + b*c)^2 := by
  ring

/-- The bilinear product on `R × R` realising the BF composition rule. -/
def bfProduct {R : Type*} [CommRing R] (u v : R × R) : R × R :=
  (u.1 * v.1 - u.2 * v.2, u.1 * v.2 + u.2 * v.1)

/-- The sum-of-squares norm on `R × R`. -/
def squareNorm {R : Type*} [CommRing R] (u : R × R) : R :=
  u.1^2 + u.2^2

/-- **Multiplicativity of the square norm.** For all `u, v : R × R`,
    `squareNorm (bfProduct u v) = squareNorm u * squareNorm v`. This
    is the categorical content of the BF identity: composition of
    Λ-certificates preserves their norm under multiplication. -/
theorem squareNorm_bfProduct
    {R : Type*} [CommRing R] (u v : R × R) :
    squareNorm (bfProduct u v) = squareNorm u * squareNorm v := by
  unfold squareNorm bfProduct
  simp only
  ring

/-- The identity element `(1, 0)` acts as a left unit. -/
theorem bfProduct_one_left
    {R : Type*} [CommRing R] (v : R × R) :
    bfProduct (1, 0) v = v := by
  unfold bfProduct
  simp

/-- The identity element `(1, 0)` acts as a right unit. -/
theorem bfProduct_one_right
    {R : Type*} [CommRing R] (u : R × R) :
    bfProduct u (1, 0) = u := by
  unfold bfProduct
  simp

end Lutar.Lambda
