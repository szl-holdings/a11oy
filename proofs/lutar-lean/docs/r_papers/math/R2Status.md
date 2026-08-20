# R2 Status — DPI Soundness (post-Bekenstein-retraction)

**Doctrine v6** | Last updated: 2024-12

## Post-Bekenstein-Retraction Notes

The original R2 proof attempt used an entropy-area bound derived from
Bekenstein's bound (Bekenstein 1981, Phys. Rev. D 23, 287). That argument
was retracted in internal review because: (1) the Bekenstein bound applies
to thermodynamic entropy, not Shannon entropy over finite alphabets, and
(2) the receipt chain is a discrete information-theoretic object. The revised
R2 proof rests solely on the classical Data Processing Inequality (DPI),
Cover & Thomas 2006 (ISBN 978-0-471-24195-9, §2.8).

## Per-Theorem Status Table

| # | Theorem / Lemma | File | Status | Method | References |
|---|----------------|------|--------|--------|-----------|
| TH6 | `dpi_receipt_chain_entropy_bound` | `TH6_DPI_Soundness.lean` | ✅ PROVED | list induction + `linarith` | Cover-Thomas 2006, §2.8 |
| TH6.S | `dpi_chain_stage_bound` | `TH6_DPI_Soundness.lean` | ✅ PROVED | `List.take` + TH6 | same |
| TH6.M | `dpi_chain_max_entropy_bound` | `TH6_DPI_Soundness.lean` | ✅ PROVED | `le_trans` | log₂(n) upper bound |
| MDB1 | `merkle_dag_height_bound` | `MerkleDAGBuild.lean` | ✅ PROVED | `Nat.log_pow` + `linarith` | Merkle 1979 Stanford PhD |
| MDB2 | `leafCount_le_pow_height` | `MerkleDAGBuild.lean` | ✅ PROVED | tree induction + Finset | structural |
| MDB3 | `height_le_log_leafCount` | `MerkleDAGBuild.lean` | ✅ PROVED | `Nat.log_mono_right` | same |
| MDB4 | `nodeCount_ge_leafCount` | `MerkleDAGBuild.lean` | ✅ PROVED | tree induction + omega | structural |
| SM1 | `scitt_mask_entropy_bound` | `SCITTMaskEntropy.lean` | ✅ PROVED | `simp` (prob preservation) | IETF draft-ietf-scitt-architecture |
| SM2 | `full_mask_zero_entropy` | `SCITTMaskEntropy.lean` | ✅ PROVED | `simp` | DPI corollary |
| SM3 | `mask_refinement_entropy_mono` | `SCITTMaskEntropy.lean` | ✅ PROVED | `simp` (equal prob vectors) | monotonicity |
| SM4 | `scitt_mask_preserves_hash` | `SCITTMaskEntropy.lean` | ✅ PROVED | `simp [applyMask]` | SCITT receipt integrity |

## Summary

- **Total theorems proved**: 11
- **Axioms introduced**: 0  
  (DPI is introduced as a `def DPI_hypothesis` parameterised over kernels,
   not as a Lean `axiom`; callers must supply the hypothesis for their kernel)
- **Sorry count**: 0
- **Proof methods**: `simp`, `linarith`, `omega`, `Nat.log_pow`, `positivity`, `Finset.sum_le_sum`

## References

1. Cover, T. M., & Thomas, J. A. (2006). *Elements of Information Theory* (2nd ed.).
   Wiley-Interscience. ISBN **978-0-471-24195-9**. Theorem 2.8.1 (DPI).

2. Merkle, R. C. (1979). *Secrecy, Authentication, and Public Key Systems*.
   PhD thesis, Stanford University.

3. Merkle, R. C. (1988). "A Digital Signature Based on a Conventional
   Encryption Function". CRYPTO 1987, LNCS 293, pp. 369–378.

4. IETF SCITT Working Group. "An Architecture for Trustworthy and Transparent
   Digital Supply Chains". draft-ietf-scitt-architecture.
   https://datatracker.ietf.org/doc/draft-ietf-scitt-architecture/

## Doctrine v6 Compliance

All R2 theorems have been verified to use only Cover-Thomas information-theoretic
foundations. No Bekenstein-bound arguments remain. The DPI is applied as a
hypothesis parameterised by the Markov kernel, ensuring no implicit thermodynamic
assumptions leak into the proof. SCITT receipt chain integrity is verified
structurally via `applyMask.hash = stmt.hash`.
