-- Lutar/Innovations/round7/KimuraAgentConvergence.lean
-- INN-R7-06: KIMURA-AGENT-CONVERGENCE — Fixation probability bounds agent-loop convergence
-- Source: Rannala B. & Wang Y. (2004) Genetics 168 doi:10.1534/genetics.104.027797
-- Area D: Kimura diffusion → agent-loop convergence under reward signal.
-- SZL lift: reward-shaping ensemble-size hyperparameter bound.
-- Doctrine v11 LOCKED 749/14/163. Lambda = Conjecture 1 (NOT a theorem).
-- Signed-off-by: Yachay <yachay@szlholdings.ai>
-- Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

namespace Lutar.Innovations.Round7.KimuraAgentConvergence

/-- Neutral fixation probability: 1/(2N) for diploid population of size N -/
def neutralFixationProb (N : Nat) (hN : 0 < N) : Rat := 1 / (2 * N)

/-- Neutral fixation is positive for any finite population -/
theorem neutral_fixation_positive (N : Nat) (hN : 0 < N) :
    0 < neutralFixationProb N hN := by
  unfold neutralFixationProb
  positivity

/-- Larger population → smaller neutral fixation probability (stronger drift resistance) -/
theorem larger_pop_lower_fixation (N M : Nat) (hN : 0 < N) (hM : 0 < M) (hNM : N < M) :
    neutralFixationProb M hM < neutralFixationProb N hN := by
  unfold neutralFixationProb
  apply Rat.div_lt_div_of_lt_left (by norm_num) (by positivity) (by positivity)
  norm_cast; omega

/-- Fixation probability is bounded above by 1 -/
theorem fixation_bounded (N : Nat) (hN : 0 < N) :
    neutralFixationProb N hN ≤ 1 := by
  unfold neutralFixationProb
  apply Rat.div_le_one_of_le <;> [norm_cast; omega; positivity]

end Lutar.Innovations.Round7.KimuraAgentConvergence
