# Chapter 10 — Knot Calculus for Governed-Decision Receipts

<!-- RETIRED-ORGANS-NOTICE -->
> **⚠️ Retired organs notice.** `amaru`, `sentra`, and `rosie` have been retired and consolidated into the **[a11oy](https://github.com/szl-holdings/a11oy)** flagship (Memory, Sentinel, and Operator verticals). Their standalone `szl-holdings/{amaru,sentra,rosie}` GitHub repositories and `szlholdings-{amaru,sentra,rosie}.hf.space` Hugging Face Spaces **no longer exist**; only the signed GHCR images persist, for supply-chain verification. Any amaru/sentra/rosie Space URLs, repo links, or endpoints referenced below are **historical and not live** — use a11oy instead.

<!-- ARCHIVED-THESIS-NOTICE -->
> **⚠️ Archived thesis notice.** The `szl-holdings/ouroboros-thesis` repository has been retired; the Ouroboros Thesis is now archived at Zenodo DOI [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276). Any `ouroboros-thesis` references below are **historical and not live**.

**Tag:** `knot-calculus-v1`
**Date sealed:** May 28, 2026
**Companion artifacts:**
- `arxiv_pkg_v15/main.tex.md` §10
- `szl-holdings/szl-cookbook/recipes/knot-calculus-v1/`
- `szl-holdings/lutar-lean/Lutar/{Khipu,DPOFeasibility,PACBayes,Knot}/`
- `szl-holdings/rosie/src/khipu-receipt.ts`
- `szl-holdings/a11oy/web/packages/a11oy-core/src/governance/pac-bayes-bound.ts`
- `szl-holdings/amaru/web/src/lib/qkan-fwp/khipu-positional.ts`
- `szl-holdings/ouroboros/runtime/lambda-gate/src/knot-tag.ts`

---

## Preamble — Geometric reframing of the Λ-gate (four-sentence thesis)

The Lutar invariant Λ, defined in v14 §3.3 as a weighted geometric mean over a
9-axis governance vector, is in v15 *reread* as a knot invariant of the
receipt-chain braid in the braid group B_n, where n is the number of concurrent
governance actors [Birman 1974, *Braids, Links and Mapping Class Groups*,
Princeton; Kauffman 1991, *Knots and Physics*, World Scientific]. The
pendant-cord skeleton of the khipu receipt DAG supplies the chord-diagram
skeleton of Vassiliev-Bar-Natan type [Bar-Natan 1995, *Topology* 34:423–472;
Vassiliev 1990, *Adv. Sov. Math.* 1:23–69], the summation-cord invariant
[Ascher & Ascher 1981; Urton 2003; Medrano & Khosla 2024] supplies the 4T
closure relation, and the dual-attestation field
[Hyland, Bennison & Hyland 2021, *LARR*, DOI 10.25222/LARR.1032] independently
realises what IETF SCITT formalises as a multi-receipt transparent statement
[draft-ietf-scitt-architecture-22, 2025]. Three audit-Reidemeister moves —
single-axis repack (R1), independent commute (R2), receipt-chain
associativity (R3) — should preserve Λ; we state them as **Conjecture** in
`lutar-lean/Lutar/Knot/ReidemeisterConjecture.lean` as `axiom` declarations,
recorded as conjectures targeting v17 closure. The chapter ships three new Lean obligations
(**TH11** sum-of-sums invariant, **TH12** Λ-gate LID + DPO stability,
**TH13** PAC-Bayes generalisation bound), four new Series A test obligations
(**T14**–**T17**), and the corresponding code grafts across rosie, a11oy,
amaru, ouroboros, and szl-cookbook.

---

## 10.0 Why this chapter exists — the geometric reframe

Chapter 9 (v14) sealed the 8-organ anatomy against a fixed set of doctrinal,
quantum, scriptural, and ML inputs (Bohr complementarity, KS-18, QKAN-FWP,
1 Enoch, DSS, doctrine v6). In the four weeks following v14 four further
inputs accumulated that change the *geometric reading* of Λ:

1. **Khipu studies updated.** Medrano & Khosla (2024, "How Can Data Science
   Contribute to Understanding the Khipu Code?", *Latin American Antiquity*
   36(2):497–516, [DOI 10.1017/laq.2024.5](https://doi.org/10.1017/laq.2024.5))
   report that Ascher's summation formulae characterize at least 74% of a
   650-khipu corpus, raising the cord-arithmetic frame from Ascher & Ascher
   (1981) and Urton (2003) from individual-specimen ethnomathematics to a
   corpus-scale, audit-grade record format with closed-form sum patterns.
2. **DPO + LID stability.** Elmecker-Plakolm, Fasterling, Sosnin, Tsay,
   and Wicker (2025, arXiv:2512.01899, accepted SaTML 2026) construct the
   *largest Locally Invariant Domain* (LID) for safe model updates by
   orthotope/zonotope abstraction of the policy parameter space; this
   slots directly into the Λ-gate as a TV-distance bound on the gate
   function, with Pinsker (1964) and Tsybakov (2009) as the standard
   KL ↔ TV bridge.
3. **PAC-Bayes for LLMs.** Lotfi et al. (2024, arXiv:2312.17173, ICML)
   demonstrated non-vacuous McAllester-style PAC-Bayes bounds on large
   language models; the closed-form arithmetic of McAllester (1999, 2003)
   transfers to a governance head that ships a Q-posterior + P-prior over
   the 9-axis policy.
4. **Geometric lineages.** Mac Lane & Moerdijk (1992, *Sheaves in Geometry
   and Logic*) supplies the topos-theoretic reading of a receipt as a
   section of a presheaf; Bar-Natan (1995) and Vassiliev (1990) supply
   the chord-diagram skeleton that the khipu pendant-cord tree realises;
   Amari (1985, *Differential-Geometrical Methods in Statistics*, Springer
   LNS 28; 2016, *Information Geometry and Its Applications*, Springer)
   supplies the dual flat connection on the Fisher manifold over which
   the PAC-Bayes KL is measured; Banach (1922, *Fundamenta Mathematicae*
   3:133–181) supplies the contraction-mapping basis for the
   gate-Lipschitz stability argument.

Chapter 10 records (a) what changes in each of the eight organs under this
reframing, (b) the three new Lean obligations + the three Conjecture-tagged
Reidemeister rewrites, (c) the Series A test obligations T14–T17, and (d) the
doctrine guarantee that the reframing is strictly additive (no theorem,
test, or doctrine line from v14 is removed or weakened).

> **Doctrinal status.** v15 is a strict superset of v14. Λ is unchanged
> (still the weighted geometric mean of v14 §3.3 / fix/lambda-unification);
> every prior Lean theorem still type-checks; every prior CITATION.cff
> field is preserved.

---

## 10.1 Per-organ table (knot-calculus reframe)

| Organ | Role | v14 baseline | v15 graft | New file(s) | Source |
|---|---|---|---|---|---|
| **rosie** | RECEIPT DAG | 335-byte README scaffold | **Khipu-indexed receipt DAG** — three-tier pendant-cord tree (Decision → Organ → Root), sum-of-sums invariant, dual-attestation field, knot-invariant tag | `src/khipu-receipt.ts`, `tests/khipu-receipt.test.ts` | Urton 2003; Ascher & Ascher 1981; Medrano & Khosla 2024; Hyland-Bennison-Hyland 2021 |
| **a11oy** | BRAIN / governance cortex | KS-18, POVM, QBist, complementarity | **PAC-Bayes governance head** — McAllester-1999 bound on head risk, 9-axis worst-axis identification, non-vacuity threshold | `governance/pac-bayes-bound.ts` + 8 tests | McAllester 1999, 2003; Lotfi et al. 2024; Amari 1985, 2016 |
| **amaru** | HEART / sequence memory | QKAN-FWP + DARUAN | **Khipu positional encoding** — organ-aware sinusoidal PE keyed by `(organId, decisionIndex)`, runtime witness for the R2 (commutativity) conjecture | `khipu-positional.ts` + 7 tests | Vaswani 2017; Urton 2003; Bar-Natan 1995 |
| **ouroboros** | Λ-GATE runtime | weighted geomean Λ (F2 unified) | **Knot-invariant tag emission** — 16-hex tag on every Λ check, non-invasive (gate.ts pass/fail unchanged) | `runtime/lambda-gate/src/knot-tag.ts` + 5 vitest tests | Reidemeister 1927; Bar-Natan 1995; Vassiliev 1990 |
| **lutar-lean** | SPINE / proof vertebrae | 10 theorems (v14: TwoWitness, GatedBoundedness) | **+3 theorems (TH11/TH12/TH13) + 3 Conjectures (R1/R2/R3)** | `Lutar/Khipu/SummationInvariant.lean`, `Lutar/DPOFeasibility.lean`, `Lutar/PACBayes.lean`, `Lutar/Knot/ReidemeisterConjecture.lean` | this work, see §10.2 |
| **szl-cookbook** | RECIPE store | anatomy-evolved-v1 | **knot-calculus-v1 recipe** with self-contained demo (TH11 verify + tag + bound + TH11 failure mode) | `recipes/knot-calculus-v1/` | this work |
| **sentra, terra, vessels, counsel, carlota-jo** | LIVER, SKELETON, LIMBS, WISDOM, IMMUNE | v14 frozen | unchanged in v15 (no semantics change required by the reframe) | — | — |

---

## 10.2 New Lean obligations + Reidemeister conjectures

### 10.2.1 TH11 `khipuReceipt_checksum_invariant`

**File:** `lutar-lean/Lutar/Khipu/SummationInvariant.lean`.

**Statement.** For every `KhipuRootReceipt` with three-tier structure
`Decision → Organ → Root`, the stored `rootValue` equals the sum of stored
pendant values, and each stored `pendantValue` equals the sum of its
decision values. Equivalently: bumping a decision value by `δ` propagates
exactly `δ` to its pendant and to the root.

**Status.** Two routine `sorry`s on
`List.sum_mapIdx_eq_sum_set_add` + `Nat.add_left_cancel`; both isolated and
explicitly tagged. Closable in ~20 h with standard Mathlib `List` arithmetic.

**Runtime counterpart.** `rosie/src/khipu-receipt.ts :: verifySumInvariant`
returns `{ok: true} | {ok: false, reason: string}`; 3 of the 10 runtime tests
in `rosie/tests/khipu-receipt.test.ts` discharge the **failure mode** (TH11
malformed pendant sum + TH11 malformed root sum). Doctrine v6 F3 pattern.

**Sources.** Urton 2003, *Signs of the Inka Khipu* (UT Press, pp. 41–62);
Ascher & Ascher 1981, *Code of the Quipu* (U. Michigan Press); Medrano &
Khosla 2024, "How Can Data Science Contribute to Understanding the Khipu
Code?", *Latin American Antiquity* 36(2), 497–516, DOI 10.1017/laq.2024.5;
Hatcher 2002, *Algebraic Topology*.

### 10.2.2 TH12 `ΛGateLID_DPO_stability`

**File:** `lutar-lean/Lutar/DPOFeasibility.lean` (replaces v14 placeholder
`True := by trivial`).

**Statement.** Let `θ₁`, `θ₂` be two policy parameter vectors with
`klDivergence θ₁ θ₂ ≤ ε`. Under (a) Pinsker's inequality
`tvDist ≤ √(KL/2)`, (b) axis-score Lipschitz continuity `|s(θ₁) - s(θ₂)| ≤
L_s · tvDist(θ₁, θ₂)`, and (c) Λ-gate Lipschitz constant `L_Λ` from Chapter
9 `gated_qkan_boundedness`, the Λ-gate verdict is stable:
`|Λ(θ₁) - Λ(θ₂)| ≤ L_Λ · L_s · √(ε / 2)`.

**Status.** Substantive 3-step structural proof with three tagged `sorry`s
(Lipschitz combination, real-arithmetic recombination, KL=0 sanity check).
Pinsker is axiomatised against `Mathlib.Probability.Divergences`. Closable
in ~60 h.

**Runtime counterpart.** `a11oy/web/packages/a11oy-core/src/governance/lid-check.ts`
provides `checkLID`, `isR1IdentityRepack`, and `postDPOThreshold` — the
runtime predicates against which the policy is admitted into `ΛGateLID(τ)`
and the post-DPO LID threshold `τ - L·√(ε/2)` is computed. The stability
bound itself is the Lean theorem above; the runtime checks witness it for
the receipt audit trail.

**Sources.** Elmecker-Plakolm et al. 2025 (arXiv:2512.01899, SaTML 2026);
Rafailov et al. 2023 (arXiv:2305.18290, NeurIPS 2023); Pinsker 1964;
Tsybakov 2009; Banach 1922.

### 10.2.2.1 TH12.1 `ΛGateLID_preserved_under_audit_Reidemeister`

**File:** `lutar-lean/Lutar/DPOFeasibility.lean`, `§LIDPreservation`.

**Motivation.** Elmecker-Plakolm et al. (2025) certify that an LID is
preserved across a single parameter update. They do not address whether the
LID is preserved when the receipt pipeline applies an audit-equivalent
rewrite (the R1/R2/R3 moves of §10.2). TH12.1 closes that question for the
smallest defensible case.

**Statement (closed cases).** Let `r : PolicyParam k → PolicyParam k` be an
R1 identity-repack at axis `i` (`isR1RewritePId i r` — the rewrite acts as
the identity on every coordinate). Then for every threshold τ and every
policy θ:

`θ ∈ ΛGateLID τ  ↔  r θ ∈ ΛGateLID τ`     (TH12.1a — R1 identity-repack)

Two- and three-fold compositions of R1 identity-repacks (`TH12.1b`,
`TH12.1c`) likewise preserve LID membership.

**Statement (sorry-tagged).** The general R1 with non-identity coordinate
factor `f : ℝ → ℝ` and hypothesis `axisScore (r θ) i = axisScore θ i`
(`TH12.1d`) is sorry-tagged. Closure requires concretising `axisScore`,
which is the same dependency cluster as TH12's existing three sorries.

**Status.** TH12.1a/b/c closed by direct `funext` + case-on-axis; ~30 lines
total. TH12.1d sorry; ~60 h, same dependency as TH12's residuals.

**Cite-and-extend disclosure.** The LID framework is from Elmecker-Plakolm
et al. 2025. The audit-Reidemeister R1/R2/R3 taxonomy is the SZL Knot
Calculus frame in §10.2 (which cites Reidemeister 1927). The hybrid theorem
combining them is new to v15; if a peer reviewer identifies prior art
covering this exact orthotope-LID + audit-rewrite combination, the
appropriate response is to demote to "specialization of [Author Year]."

### 10.2.3 TH13 `governanceHead_PACBayes_bound`

**File:** `lutar-lean/Lutar/PACBayes.lean`.

**Statement.** Given empirical risk `R̂(Q)`, KL divergence `KL(Q‖P)`, sample
size `n`, and confidence `δ`, the McAllester-1999 PAC-Bayes bound
`R(Q) ≤ R̂(Q) + √( (KL + ln(2√n/δ)) / (2n) )` holds with probability ≥ 1−δ
over the n-sample. Closed-form arithmetic content (monotonicity in KL,
non-vacuity threshold, inequality form) is fully proved
(`pacBayesBound_mono_kl`, `pacBayes_inequality_form`,
`pacBayesBound_nonvacuous_iff`, `governanceHead_PACBayes_bound`
non-negativity).

**Status.** The probabilistic `Pr ≥ 1−δ` quantifier remains the documented
residual obligation (requires Mathlib `Probability.IndepFun` +
`Probability.Independence.Conditional`; ~80–120 h).

**Runtime counterpart.** `a11oy/web/packages/a11oy-core/src/governance/
pac-bayes-bound.ts :: pacBayesBound` returns the slack + upper bound +
non-vacuity flag; `nineAxisPacBayesBound` identifies the worst axis. 8/8
runtime tests pass.

**Sources.** McAllester 1999, COLT; McAllester 2003, *Machine Learning*
51:5–21; Lotfi et al. 2024 (arXiv:2312.17173, ICML 2024); Amari 1985
(Springer LNS 28); Amari 2016 (Springer).

### 10.2.4 Reidemeister rewrites — **Conjecture** R1, R2, R3

**File:** `lutar-lean/Lutar/Knot/ReidemeisterConjecture.lean`.

**Status.** ALL THREE ARE DECLARED AS `axiom` (not `theorem ... := sorry`),
per B2 issue lutar-lean#32 fix. Lean's `#print axioms` machinery will flag
any downstream theorem that depends on R1/R2/R3 as relying on additional
axioms beyond `propext`/`Classical`. Target v17 for converting these
axioms back to theorems.

| Conjecture | Statement | Proof route | Effort |
|---|---|---|---|
| **R1** single-axis repack | `Λ_invariant_under_R1`: any single-axis rewrite by the identity preserves Λ | Expand geomean as product-then-root, substitute `f = id`, `rfl` | ~10 h |
| **R2** independent commute | `Λ_invariant_under_R2`: two commuting rewrites compose to a Λ-invariant rewrite | `isR2Commute` + symmetry of geomean under permutation | ~20 h |
| **R3** chain associativity | `Λ_invariant_under_R3`: `Function.comp_assoc` plus closure of Λ-invariance under composition | direct from Mathlib `Function.comp_assoc` | ~10 h |

**Runtime witnesses.**
- R2 commutativity: `ouroboros/.../knot-tag.ts :: knotInvariantTag` uses a
  sorted skeleton, so two organ orderings produce the same tag (5/5
  vitest tests pass).
- R1 identity: `rosie/tests/khipu-receipt.test.ts :: T_reidemeister_R1`
  confirms that rebuilding identical receipts produces identical
  `rootValue` and `rootHash`.
- R2 organ swap: `rosie/tests/khipu-receipt.test.ts :: T_reidemeister_R2`
  confirms that organ-order swaps preserve `knotInvariantTag`.
- amaru: `khipuSkeletonTag` is the runtime witness for R2 at the
  sequence-memory layer (`T_khipu_skeleton_R2` passes; sensitivity to
  extra decisions checked).

**Sources.** Reidemeister 1927, *Abh. Math. Sem. Univ. Hamburg* 5:24–32;
Kauffman 1991 (World Scientific); Birman 1974 (Princeton); Bar-Natan 1995
(*Topology* 34:423–472); Vassiliev 1990 (*Adv. Sov. Math.* 1:23–69);
Kontsevich 1993.

---

## 10.3 Series A test obligations T14–T17

| ID | Coverage | File | Status |
|---|---|---|---|
| **T14** | TH11 — 3-organ × 5-decision build + verifySumInvariant pass + tampered-pendant FAIL + tampered-root FAIL | `rosie/tests/khipu-receipt.test.ts` (`T_khipu_happy`, `T_khipu_failure_TH11`, `T_khipu_failure_TH11b`) | **3/3 PASS** |
| **T15** | TH13 — McAllester bound monotone in KL, tight at large n, non-vacuity threshold sane, 9-axis worst-axis identified | `a11oy-core/governance/__tests__/pac-bayes-bound.test.ts` | **8/8 PASS** |
| **T16** | Conjecture R1/R2 runtime witnesses — identity repack preserves rootValue + rootHash; organ swap preserves knotInvariantTag | `rosie/tests/khipu-receipt.test.ts` (`T_reidemeister_R1`, `T_reidemeister_R2`); `amaru/.../khipu-positional.test.ts` (`T_khipu_skeleton_R2`, `T_khipu_skeleton_sensitive`); `ouroboros/.../knot-tag.test.ts` | **R1/R2 witnesses PASS** (proofs are Conjecture) |
| **T17** | Dual-attestation P6+P8 — distinct signers + non-empty signatures pass; same signer / missing signer FAIL | `rosie/tests/khipu-receipt.test.ts` (`T_khipu_dual_ok`, `T_khipu_dual_FAIL`, `T_khipu_dual_FAIL_missing_signer`) | **3/3 PASS** |

**Test-run summary (npx tsx + vitest, 2026-05-28):**
- rosie khipu-receipt: 10/10 PASS
- a11oy PAC-Bayes: 8/8 PASS
- amaru khipu-positional: 7/7 PASS
- ouroboros knot-tag: 5/5 PASS (vitest, requires workspace `@szl/ouroboros-types`)
- szl-cookbook demo: PASS (TH11 happy + TH11 failure + tag + bound printed)
- **Total v15 runtime tests added: 30 + 1 demo = 31. All PASS.**

---

## 10.4 Doctrine guarantee (v6 + reframing)

- **Ban-list compliance.** Every file added in v15 was scanned against
  doctrine v6 banned tokens before commit. No occurrences of
  "revolutionary", "groundbreaking", "magical", "world-class",
  "best-in-class", "game-changing", "first-ever", "unprecedented",
  "frontier-defining" outside the carlota-jo guard. No occurrences of
  "AlloyScape", "Glass Wing", "Glasswing", "Mythos", "Stephen Paul",
  "Perplexity Computer" anywhere.
- **No silent change of Λ.** Λ remains the weighted geometric mean from
  v14 §3.3 as canonicalized in the F2 `fix/lambda-unification` PR
  (`ouroboros` commit `ae625ba`, "unify Λ scalar to weighted geometric
  mean"). `ouroboros/runtime/lambda-gate/src/gate.ts :: computeLambda`
  has the same blob hash on both the F2 baseline `ae625ba` and the v15
  knot-calculus tip `feat/v15-knot-calculus`
  (git blob `28563ed3c592d3f0c4b436018167e48de609f432`, verified
  2026-05-28); no additional change to `gate.ts` is introduced by v15.
  The v15 knot tag is emitted from a new sibling file (`knot-tag.ts`)
  that calls `computeLambda` and `evaluateAxes` verbatim. F2 unification
  is preserved. (Note: prior wording compared to "v14"; the honest
  comparison is to the F2 baseline, since the v14 chapter was sealed
  before F2 landed. See B2 issue ouroboros-thesis#72.)
- **Conjecture honesty.** R1/R2/R3 are declared as `axiom` in
  `Lutar/Knot/ReidemeisterConjecture.lean` (B2 issue lutar-lean#32 fix).
  Any downstream theorem that depends on R1/R2/R3 is therefore flagged
  by Lean's `#print axioms` machinery, so downstream callers cannot
  mistake conjectural facts for proven ones. The upgrade path is
  documented and isolated to one file.
- **Strict superset.** No deletion of prior organs, no rename, no semantics
  change to a v14 file outside additive imports. Every v14 Lean theorem
  still type-checks (additions only). Every prior CITATION.cff field is
  preserved; v15 only adds entries.

---

## 10.5 Bibliography (Chapter 10 only)

- **Amari, S. (1985).** *Differential-Geometrical Methods in Statistics.*
  Springer Lecture Notes in Statistics 28.
- **Amari, S. (2016).** *Information Geometry and Its Applications.* Springer.
- **Ascher, M., Ascher, R. (1981).** *Code of the Quipu: A Study in Media,
  Mathematics, and Culture.* University of Michigan Press.
- **Elmecker-Plakolm, L., Fasterling, P., Sosnin, P., Tsay, C., Wicker, M.
  (2025).** "Provably Safe Model Updates."
  [arXiv:2512.01899](https://arxiv.org/abs/2512.01899),
  DOI [10.48550/arXiv.2512.01899](https://doi.org/10.48550/arXiv.2512.01899).
  Accepted *SaTML 2026*. (Construction of largest Locally Invariant Domain
  via orthotopes/zonotopes; cited for TH12 ΛGateLID lineage.)
- **Banach, S. (1922).** "Sur les opérations dans les ensembles abstraits
  et leur application aux équations intégrales." *Fundamenta Mathematicae*
  3, 133–181.
- **Bar-Natan, D. (1995).** "On the Vassiliev knot invariants." *Topology*
  34(4), 423–472.
- **Birman, J. S. (1974).** *Braids, Links, and Mapping Class Groups.*
  Princeton University Press.
- **Hyland, S. C., Bennison, B. R., Hyland, F. (2021).** "Multi-author
  khipu authorisation in Andean colonial accounting." *Latin American
  Research Review* 56. [DOI 10.25222/LARR.1032](https://doi.org/10.25222/LARR.1032).
- **IETF SCITT (2025).** *draft-ietf-scitt-architecture-22*. Multi-receipt
  transparent statements.
- **Kauffman, L. H. (1991).** *Knots and Physics.* World Scientific.
- **Kontsevich, M. (1993).** "Vassiliev's knot invariants." *Adv. Sov.
  Math.* 16(2), 137–150.
- **Lotfi, S., Finzi, M., Kuang, Y., Rudner, T. G. J., Goldblum, M.,
  Wilson, A. G. (2024).** "Non-vacuous Generalization Bounds for Large
  Language Models." [arXiv:2312.17173](https://arxiv.org/abs/2312.17173).
  *Proc. ICML 2024,* PMLR 235. (Venue corrected from NeurIPS 2023 per
  B2 issue ouroboros-thesis#74; an earlier workshop version did appear
  at the NeurIPS 2023 SSL Workshop.)
- **Mac Lane, S., Moerdijk, I. (1992).** *Sheaves in Geometry and Logic: A
  First Introduction to Topos Theory.* Springer.
- **McAllester, D. A. (1999).** "PAC-Bayesian Model Averaging." *COLT.*
- **McAllester, D. A. (2003).** "PAC-Bayesian Stochastic Model Selection."
  *Machine Learning* 51, 5–21.
- **Medrano, M., Khosla, A. (2024).** "How Can Data Science Contribute to
  Understanding the Khipu Code?" *Latin American Antiquity* 36(2),
  497–516. [DOI 10.1017/laq.2024.5](https://doi.org/10.1017/laq.2024.5).
  (Title and venue verified 2026-05-28 via Cambridge Core; B2 issue
  ouroboros-thesis#73 fix.)
- **Pinsker, M. S. (1964).** *Information and Information Stability of
  Random Variables and Processes.* Holden-Day.
- **Rafailov, R., et al. (2023).** "Direct Preference Optimization: Your
  Language Model is Secretly a Reward Model." [arXiv:2305.18290](https://arxiv.org/abs/2305.18290).
  *NeurIPS 2023.*
- **Reidemeister, K. (1927).** "Elementare Begründung der Knotentheorie."
  *Abh. Math. Sem. Univ. Hamburg* 5, 24–32.
- **Tsybakov, A. B. (2009).** *Introduction to Nonparametric Estimation.*
  Springer.
- **Urton, G. (2003).** *Signs of the Inka Khipu: Binary Coding in the
  Andean Knotted-String Records.* University of Texas Press.
- **Vassiliev, V. A. (1990).** "Cohomology of knot spaces." *Adv. Sov. Math.*
  1, 23–69.
- **Vaswani, A., et al. (2017).** "Attention Is All You Need." *NeurIPS.*

---

## 10.6 Cross-references

- v14 chapter: [`docs/v14/ch9_anatomy_evolved_v1.md`](../v14/ch9_anatomy_evolved_v1.md)
- v15 arXiv manuscript: [`arxiv_pkg_v15/main.tex.md`](../../arxiv_pkg_v15/main.tex.md)
- v15 BibTeX: [`arxiv_pkg_v15/refs.bib`](../../arxiv_pkg_v15/refs.bib)
- Cookbook recipe: `szl-holdings/szl-cookbook/recipes/knot-calculus-v1/`
- Lean modules: `szl-holdings/lutar-lean/Lutar/{Khipu,DPOFeasibility,PACBayes,Knot}/`
- Code grafts: `szl-holdings/{rosie,a11oy,amaru,ouroboros}` on branch
  `feat/v15-knot-calculus`

---

*Chapter 10 sealed: 2026-05-28 · Doctrine v6 compliant · F2 Λ-unification preserved · R1/R2/R3 = Conjecture (v16)*
