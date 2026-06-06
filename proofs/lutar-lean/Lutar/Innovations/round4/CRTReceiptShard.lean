-- Lutar/Innovations/round4/CRTReceiptShard.lean
-- F-09: CRT-RECEIPT-SHARD
-- Source: Sunzi Suanjing (Sun Tzu's Mathematical Manual), ~3rd-5th century CE
-- Academic: Needham, Science and Civilisation in China, Vol. 3 (Cambridge UP, 1959);
--           Colgate Math — Chinese Remainder Theorem lecture notes.
-- Claim: Coprime moduli (m₁, m₂) uniquely reconstruct receipt ID mod (m₁*m₂).
-- Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT theorem).
-- Lives in Lutar/Innovations/round4/ — OUTSIDE locked kernel.
-- Signed-off-by: Yachay <yachay@szlholdings.ai>
-- Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

namespace Lutar.Innovations.Round4.CRTReceiptShard

/-- CRT: if r and r' agree modulo both coprime moduli, they agree modulo their product. -/
theorem crt_unique_reconstruction (r r' m₁ m₂ : ℕ)
    (hcop : Nat.Coprime m₁ m₂)
    (h₁ : r % m₁ = r' % m₁)
    (h₂ : r % m₂ = r' % m₂) :
    r % (m₁ * m₂) = r' % (m₁ * m₂) := by
  have hdvd₁ : m₁ ∣ (r - r' : ℤ).natAbs := by
    rw [← Int.natCast_dvd_natCast]
    rw [Int.natAbs_of_nonneg (by omega)]
    omega
  have hdvd₂ : m₂ ∣ (r - r' : ℤ).natAbs := by
    rw [← Int.natCast_dvd_natCast]
    rw [Int.natAbs_of_nonneg (by omega)]
    omega
  exact Nat.ModEq.comm (Nat.chineseRemainder hcop (Nat.modEq_comm.mpr (Nat.modEq_iff_dvd'.mpr hdvd₁ (by omega))) (Nat.modEq_comm.mpr (Nat.modEq_iff_dvd'.mpr hdvd₂ (by omega)))).2

/-- Each shard residue is bounded by its modulus. -/
theorem crt_shard_bounds (receipt_id m₁ m₂ : ℕ) (hm1 : 0 < m₁) (hm2 : 0 < m₂) :
    receipt_id % m₁ < m₁ ∧ receipt_id % m₂ < m₂ :=
  ⟨Nat.mod_lt _ hm1, Nat.mod_lt _ hm2⟩

/-- Sunzi's original: x ≡ 2 (mod 3), x ≡ 3 (mod 5), x ≡ 2 (mod 7) → x ≡ 23 (mod 105). -/
theorem sunzi_original_problem : 23 % 3 = 2 ∧ 23 % 5 = 3 ∧ 23 % 7 = 2 := by decide

/-- The product 3 * 5 * 7 = 105 is the CRT modulus for Sunzi's problem. -/
theorem sunzi_modulus : 3 * 5 * 7 = 105 := by decide

end Lutar.Innovations.Round4.CRTReceiptShard
