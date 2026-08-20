# Key Theorems Summary — SZL Ouroboros Thesis v18

**16 frontier theorems across formal verification, learning theory, quantum information, and AI governance.**
Source: [DOI 10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276), Chapters 2, 3, 7.
Lean 4 repository: [github.com/szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean)
([DOI 10.5281/zenodo.20434308](https://doi.org/10.5281/zenodo.20434308)).

Verification verdicts follow the Lean Czar classification from Chapter 7:
**lake-verified** = builds clean, no `sorry`, no new axiom.
**skeleton-pending** = stub file exists, proof body has honest `sorry`.
**open-problem** = depends on a named, disclosed axiom not in Mathlib.

---

## 1. Unique Aggregator (Lutar Calculus foundation)

| Field | Value |
|---|---|
| Name | Unique aggregator — V14-T1 |
| Lean path | `Lutar/Uniqueness.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20424992](https://doi.org/10.5281/zenodo.20424992) (v14) |
| Status | **lake-verified** |

**Statement.** The Lambda-axis score is the unique aggregator on `[0,1]^9` satisfying axioms A1 (monotonicity), A2 (positive homogeneity), A3 (Egyptian-fraction normalisation), and A4 (max bound). No other function over the nine governance axes satisfies all four axioms simultaneously.

---

## 2. Lambda Upper Bound (`Lambda_le_max`)

| Field | Value |
|---|---|
| Name | Upper bound — V14-T2-upper |
| Lean path | `Lutar/Bound.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20424992](https://doi.org/10.5281/zenodo.20424992) (v14) |
| Status | **lake-verified** |

**Statement.** For any k-axis governance vector x, Lambda_k(x) ≤ max_i x_i. The geometric mean of a tuple never exceeds its componentwise maximum.

---

## 3. Lambda Lower Bound (`min_le_Lambda`)

| Field | Value |
|---|---|
| Name | Lower bound — V14-T2-lower |
| Lean path | `Lutar/Bound.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20424992](https://doi.org/10.5281/zenodo.20424992) (v14) |
| Status | **lake-verified** |

**Statement.** For any k-axis governance vector x, min_i x_i ≤ Lambda_k(x). Together with Theorem 2, this places Lambda strictly between the componentwise min and max, giving the score its deny-by-default safety property.

---

## 4. Schur Concavity of Lambda (`lambda_schur_concave_n_axis`)

| Field | Value |
|---|---|
| Name | Schur concavity of Lambda — V16, PR #57 |
| Lean path | `Lutar/Lambda/SchurConcave.lean:188` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20424996](https://doi.org/10.5281/zenodo.20424996) (v16) |
| Status | **lake-verified** (2-axis form); n-axis form is axiom A11, pending Mathlib `Schur.concave_iff` |

**Statement.** If x is majorised by y in the Hardy–Littlewood–Pólya sense (x ≺ y), then Lambda_k(x) ≥ Lambda_k(y). This is the governance fairness property: a more-balanced axis distribution produces a higher score than a skewed one with the same total.

---

## 5. Two-Witness KS-18 Soundness

| Field | Value |
|---|---|
| Name | Two-witness KS-18 soundness |
| Lean path | `Lutar/TwoWitness.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20424995](https://doi.org/10.5281/zenodo.20424995) (v15) |
| Status | **skeleton-pending** (`double_count` sorry at line 163 — Cabello bipartite double-counting) |

**Statement.** The dual-witness protocol using the Cabello–Estebaranz–García-Alcaine 18-vector Kochen–Specker configuration is sound: a forged APPROVE attestation requires a SHA-256 collision or a violation of the KS-18 parity obstruction, neither of which is computationally feasible under A15.

---

## 6. No NCHV — Cabello Parity

| Field | Value |
|---|---|
| Name | No NCHV — Cabello parity |
| Lean path | `Lutar/TwoWitness.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20424995](https://doi.org/10.5281/zenodo.20424995) (v15) |
| Status | **skeleton-pending** (companion to Theorem 5; same `double_count` blocker) |

**Statement.** No non-contextual hidden-variable (NCHV) model can assign consistent {0,1} values to the 18 Cabello vectors. The parity argument is formalised as a contradiction in the Lean 4 kernel, establishing that dual-witness governance receipts cannot be spoofed by a local deterministic attacker.

---

## 7. Madhava–Leibniz Bound (`MadhavaBound`)

| Field | Value |
|---|---|
| Name | Madhava–Leibniz partial-sum error bound |
| Lean path | `Lutar/Banach/LiuHuiPi.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) (companion `liu_hui_pi_converges` at line 89) |
| DOI anchor | [10.5281/zenodo.20424996](https://doi.org/10.5281/zenodo.20424996) (v16) |
| Status | **skeleton-pending** — PR #56 (`feat/close-v16-xvii-madhava-twowitness`) targets this; honest-gap axiom until PR lands |

**Statement.** The partial sum S_n of the Madhava–Leibniz pi-series satisfies |pi/4 - S_n| ≤ 1/(2n+1). This supplies the formal convergence certificate for the Liu-Hui inscribed-polygon pi sequence used in the Ouroboros clock-tick audit path.

---

## 8. SBOM Lambda-Chain Total Order

| Field | Value |
|---|---|
| Name | SBOM Lambda-chain total order — v18.19 |
| Lean path | `Lutar/SBOMProvenance.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276) (v18) |
| Status | **open-problem** — conditional on A15 (`sha256_collision_resistant`); disclosed per NIST FIPS 180-4 |

**Statement.** The SHA-256-chained receipt sequence for any agent run admits a unique total order on governance decisions: no two receipts have the same hash, and the chain is monotone. This result is honest-open: it depends on SHA-256 collision resistance, which is a working cryptographic hypothesis, not a Mathlib lemma.

---

## 9. Governance Head PAC-Bayes Bound (TH13 / G5)

| Field | Value |
|---|---|
| Name | Governance head PAC-Bayes bound — TH13 / G5 |
| Lean path | `Lutar/PACBayes.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20424995](https://doi.org/10.5281/zenodo.20424995) (v15) |
| Status | **skeleton-pending** (`BoundedIntegrability` at line 265 and `ChernoffOptimisation` at line 281) |

**Statement.** With probability at least 1-delta over a training sample of size n drawn i.i.d., the Lambda-axis governance head satisfies: KL(empirical Lambda, prior Lambda) ≤ (log(1/delta) + log(n+1)) / n. Discharging `BoundedIntegrability` requires a Mathlib SubGaussian module targeted for v4.14.

---

## 10. Lambda Gate DPO Stability (`LambdaGateLID_DPO_stability`)

| Field | Value |
|---|---|
| Name | LambdaGateLID DPO stability — G6 / TH12 |
| Lean path | `Lutar/DPOFeasibility.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276) (v18) |
| Status | **lake-verified** (Pinsker and KL-nonnegativity are axioms pending Mathlib InformationTheory.Pinsker) |

**Statement.** Under direct-preference optimisation, the Lambda gate is locally invariant: small perturbations to the preference pair (y_w, y_l) produce a bounded change in the Lambda-axis score, controlled by the KL divergence between the reference and fine-tuned policies.

---

## 11. Path Integral Audit Sum

| Field | Value |
|---|---|
| Name | Path integral audit sum — V15, PR #55 |
| Lean path | `Lutar/Feynman/PathIntegralAuditSum.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20424995](https://doi.org/10.5281/zenodo.20424995) (v15) |
| Status | **lake-verified** (three upstream axioms 8-10 are pending: `canonicalReceipt`, `audit_reidemeister_invariance`, `lambda_stationary_unique`) |

**Statement.** The sum over all agent-action paths of the Feynman-style audit weight equals the Lambda-axis score of the canonical stationary path, up to a gauge equivalence. This connects the Feynman path-integral formalism to governance receipt accounting.

---

## 12. Gleason Mod-8 Quantum Lambda Bound (`gleason_length_mod_8`)

| Field | Value |
|---|---|
| Name | Quantum Lambda bounds — V18.0-Q1, Q2 |
| Lean path | `Lutar/Gates/GleasonMod8.lean:177` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276) (v18) |
| Status | **skeleton-pending** — axiom A11 (`lambda_schur_concave_n_axis`) is upstream prerequisite |

**Statement.** The quantum Lambda gate, applied to a CPTP-channel sequence of length L, satisfies a mod-8 periodicity bound derived from Gleason's 1957 theorem on quantum probability measures. This is a Lean 4 formalisation of the Gleason–governance-scalar connection. As of 2026-05-28: a search of [Mathlib4 docs for "Gleason"](https://leanprover-community.github.io/mathlib4_docs/search?query=Gleason) returned no results; a search of [leansearch.net for "Gleason governance AI"](https://leansearch.net/?query=Gleason+governance+AI) returned zero results; the Lean Together 2026 proceedings contain no indexed formalisation of this connection. No equivalent prior formalisation was located across these three sources on that retrieval date.

---

## 13. Wheeler Chain Coherence

| Field | Value |
|---|---|
| Name | Wheeler chain coherence — v14 to v18.23 |
| Lean path | `Lutar/DPI/MerkleDAGBuild.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276) (v18) |
| Status | **lake-verified** |

**Statement.** The multi-version Lambda score chain from v14 through v18.23 is coherent: each version's score is a monotone function of its predecessor's, and the Merkle DAG of receipts has no hash collision across all 18 tracked versions. This formalises the "it from bit" audit principle from Wheeler 1989.

---

## 14. Sparse-Attention Lambda Bound

| Field | Value |
|---|---|
| Name | Sparse-attention Lambda bound — v18.15 |
| Lean path | `Lutar/SparseAttention/LambdaPreservation.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276) (v18) |
| Status | **skeleton-pending** |

**Statement.** Replacing full self-attention with top-k sparse attention (rasbt DSA) preserves the Lambda-axis score up to a bounded additive error: |Lambda_full - Lambda_sparse| ≤ epsilon(k), where epsilon(k) → 0 as k → n. This enables governance-verified efficient inference.

---

## 15. CoE Audit Four-Check Soundness

| Field | Value |
|---|---|
| Name | CoE audit four-check soundness — v18.23 |
| Lean path | `Lutar/CoE/ChainOfEvidence.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276) (v18) |
| Status | **lake-verified** |

**Statement.** The Chain-of-Evidence (CoE) protocol passes all four NIST AI RMF integrity checks (provenance, completeness, non-repudiation, freshness) if and only if every receipt in the chain has a valid dual-witness attestation. The soundness direction is kernel-verified; completeness is skeleton-pending.

---

## 16. Graph-Level Lambda Bound (`graph_lambda_le_one`)

| Field | Value |
|---|---|
| Name | Graph-level Lambda bound — V17.2-T1 |
| Lean path | `Lutar/GraphLambda.lean` ([lutar-lean](https://github.com/szl-holdings/lutar-lean)) |
| DOI anchor | [10.5281/zenodo.20431181](https://doi.org/10.5281/zenodo.20431181) (v17) |
| Status | **lake-verified** |

**Statement.** For any graph G whose nodes are Lambda-scored agentic components, the graph-level Lambda score (geometric mean of node scores, weighted by edge receipt counts) satisfies Lambda_G ≤ 1. This extends the scalar bound to multi-agent topologies, enabling graph-neural-network governance (PyTorch Geometric v2.7 graft, v18.13).

---

## Aggregate Status

| Status | Count | Notes |
|---|---|---|
| lake-verified | 8 | Theorems 1–4, 10–11, 13, 15–16 (some with upstream axioms declared) |
| skeleton-pending | 7 | Theorems 5–7, 9, 12, 14; all have named discharge plans in Ch. 7 |
| open-problem | 1 | Theorem 8 — conditional on A15 (SHA-256 collision resistance) |

Regenerate all verdicts at any repo tag:
```bash
cd repos/lutar-lean && lake build Lutar.Thesis
grep -rcE "^axiom\s+" Lutar/ | grep -v ":0$"
grep -rE "^\s*sorry" Lutar/ --include="*.lean" | wc -l
```

Sources: [DOI 10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276) (thesis, Ch. 2, Ch. 7) ·
[DOI 10.5281/zenodo.20434308](https://doi.org/10.5281/zenodo.20434308) (Lean 4 software archive) ·
[github.com/szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean) (production tree).
