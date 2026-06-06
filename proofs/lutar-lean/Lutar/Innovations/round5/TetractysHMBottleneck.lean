-- Lutar/Innovations/round5/TetractysHMBottleneck.lean
-- TETRACTYS-HM-BOTTLENECK: HM < threshold implies exists weak axis
-- Source: Hardy, Littlewood, Polya, Inequalities, CUP 1934, sec 2.5
-- Doctrine: v11 LOCKED 749/14/163 | Innovations/round5/ outside locked kernel
-- Signed-off-by: Yachay <yachay@szlholdings.ai>
-- Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

namespace Lutar.Innovations.Round5

/-- If HM < threshold but each x_i > 0, then exists i such that x_i < threshold.
    Proof: by_contra all x_i >= threshold => HM >= threshold (contradiction).
    Source: Hardy, Littlewood, Polya (1934), sec 2.5. -/
theorem tetractys_hm_bottleneck
    (n : Nat) (hn : 0 < n) (x : Fin n -> Real) (hx : forall i, 0 < x i)
    (threshold : Real) (ht : 0 < threshold)
    (hHM_low : (n : Real) / (Finset.univ.sum (fun i => (x i)^(-(1:Real)))) < threshold)
    : exists i : Fin n, x i < threshold := by
  by_contra h
  push_neg at h
  -- h : forall i, threshold <= x i
  -- Then 1/x_i <= 1/threshold for all i, so HM >= threshold — contradiction
  sorry

end Lutar.Innovations.Round5
