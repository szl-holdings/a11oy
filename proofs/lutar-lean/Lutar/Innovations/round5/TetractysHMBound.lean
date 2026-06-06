-- Lutar/Innovations/round5/TetractysHMBound.lean
-- TETRACTYS-HM-BOUND: HM <= GM <= AM for Lambda axes
-- Source: Hardy, Littlewood, Polya, Inequalities, CUP 1934, sec 2.5
-- Doctrine: v11 LOCKED 749/14/163 | Innovations/round5/ outside locked kernel
-- Signed-off-by: Yachay <yachay@szlholdings.ai>
-- Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

import Mathlib.Analysis.MeanInequalities

namespace Lutar.Innovations.Round5

open Real Finset

/-- HM <= GM <= AM for positive reals (Lambda score axes).
    Source: Hardy, Littlewood, Polya, Inequalities, CUP 1934, Section 2.5. ISBN 0-521-35880-9. -/
theorem tetractys_hm_le_gm_le_am
    (n : Nat) (hn : 0 < n) (x : Fin n -> Real) (hx : forall i, 0 < x i)
    : (n : Real) / (Finset.univ.sum (fun i => (x i)^(-(1:Real)))) <=
      (Finset.univ.prod (fun i => x i)) ^ ((1 : Real) / n) /      (Finset.univ.prod (fun i => x i)) ^ ((1 : Real) / n) <=
      (Finset.univ.sum (fun i => x i)) / n := by
  constructor
  . sorry -- HM <= GM: AM-GM applied to reciprocals
  . sorry -- GM <= AM: inner_mul_le_norm_mul_iff or NNReal.geom_mean_le_arith_mean

end Lutar.Innovations.Round5
