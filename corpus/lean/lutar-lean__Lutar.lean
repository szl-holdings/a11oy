import Lutar.Axioms
import Lutar.Egyptian
import Lutar.Invariant
import Lutar.Bound
import Lutar.Uniqueness
-- λ-green-strike: discoverable index of zero-sorry, Lake-verified Λ lemmas (NOT a theorem for Λ-uniqueness — Conjecture 1)
import Lutar.GreenTheorems
import Lutar.TwoWitness
import Lutar.DoctrineV3.MoralGrounding
import Lutar.DoctrineV3.MeasurabilityHonesty
import Lutar.Khipu.SummationInvariant
import Lutar.DPOFeasibility
import Lutar.PACBayes
import Lutar.Knot.ReidemeisterConjecture
-- v16 ancient-foundations grafts (b4_rosie_amaru_ancient)
import Lutar.Egyptian.HorusEye
import Lutar.Brahmi.AxisOption
import Lutar.Crt.WeightChunking
-- v16 ancient-foundations grafts (b3_a11oy_ancient)
import Lutar.Calibration.FalsePosition
import Lutar.Egyptian.AkhmimTable
import Lutar.Thresholds.QuadraticCompletion
import Lutar.PACBayes.MadhavaBound
import Lutar.Lambda.CompositionRing
-- v16 ancient-foundations grafts (b5_ouroboros_foundations)
import Lutar.Banach.BabylonianContraction
import Lutar.Banach.LiuHuiPi
import Lutar.Precision.SexagesimalRegular
import Lutar.Propagation.RelayChain
import Lutar.Transduction.ReceiptInvariant
-- v16 Feynman grafts (PR #41)
import Lutar.Feynman.FeynmanLineage
import Lutar.Feynman.PathIntegralAuditSum
-- integrity-remediation 2026-05-28: three publicly-claimed theorems + doctrine evolution
import Lutar.HUKLLA.HaltEligibility
import Lutar.OVERWATCH.ReadOnly
import Lutar.DPI.DPIBound
import Lutar.Doctrine.PublicClaims
import Lutar.Doctrine.CrossComponentInvariant
-- phd-math: R1/R2/A15/K10 (45 theorems, 0 sorry, 0 axiom)
import Lutar.Composition.TH1_Composition
import Lutar.Composition.CompositionOverhead
import Lutar.Composition.AdversarialRobustness
import Lutar.Composition.R1Tests
import Lutar.DPI.TH6_DPI_Soundness
import Lutar.DPI.MerkleDAGBuild
import Lutar.DPI.SCITTMaskEntropy
import Lutar.Topology.PersistentHomologyChain
import Lutar.PRNG.K10v2_ReplayRoot
-- v17 Wheeler delayed-choice graft
import Lutar.Wheeler.DelayedChoiceClosure
import Lutar.Shannon.DoctrineEntropy
-- khipu-consensus-roadmap: BFT 3-of-4 multi-organ signed agreement (additive,
-- 2 proof-deferred conjectures, 0 new axioms; Doctrine v12 781/14/194 -> 783/14/196)
import Lutar.KhipuConsensus
-- v17 Quantum-error-correction lineage grafts
import Lutar.QEC.HammingFoundations
import Lutar.QEC.ShorReceiptCode
import Lutar.QEC.CSSBridge
import Lutar.QEC.KitaevSurface
import Lutar.Correlator.MatchedFilter
-- v17 Gleason + Schur modules (§XVII open obligations)
import Lutar.Lambda.SchurConcave
import Lutar.Gates.Adinkra
import Lutar.Gates.GleasonMod8
-- v17.2 GraphLambda + PositionAware (GNN substrate, feat/v17-graph-lambda-substrate)
import Lutar.GraphLambda
import Lutar.PositionAware
-- phd-math-frontier: TH-V18-11 Pareto archive finite stabilization (PROVED, 0 sorry, 0 new axiom)
import Lutar.Thesis.TH_V18_11_ParetoFiniteStabilization
import Lutar.LambdaPermInvariant
-- Round 13 Λ-closure (Cauchy_ND): closable sub-lemmas (sorry-free) + terminal CONDITIONAL
-- uniqueness theorem (sorry-free) + counterexample fragment. The UNCONDITIONAL uniqueness
-- carries ONE honest, tagged open obligation (FACTORIZATION_AXIOM_GAP / needs A6 bisymmetry).
-- Λ stays Conjecture 1; no public claim flipped; axioms_unique stays 14.
import Lutar.Round13.CauchyND_Closure
import Lutar.Round13.Lambda_Uniqueness
-- Wave12 CUT-2 / CF-11: axiom-free CONDITIONAL Λ-uniqueness under slice-multiplicativity
-- (`lambda_unique_of_separable`, no sorry, NO new axiom). Strictly weaker hypothesis than
-- the `Factors` premise; derived from the already-proved `multiplicative_monotone_isPow_pos`.
-- Λ (F23) STAYS Conjecture 1 unconditionally (the unconditional claim is FALSE — maxAgg/min).
import Lutar.Round13.LambdaSeparable
-- Wave12 CF-13: DEQ/Ouro equilibrium input-Lipschitz well-posedness margin (Mathlib
-- ContractingWith; kernel-clean, no sorry, no new axiom). Companion to Wave11 CF-3.
import Lutar.Innovations.round5.OuroLoopInputLipschitz
-- Wave12 CF-17: floating-point summation forward-error bound (γ_{n-1}·Σ|xᵢ|; Higham 2002,
-- rounding model as explicit HYPOTHESIS not axiom; kernel-clean, no sorry, no new axiom).
import Lutar.Khipu.NumericStability
-- PURIQ proved-formula pack (zero sorry, Mathlib-free): F1/F11/F12/F18/F19
-- (original sprint) + F4/F7/F22 (append-only/DAG/FIFO sprint 2026-06-04). Wiring
-- this into `lake build` makes CI kernel-check every PROVED PURIQ formula. The 15
-- still-open PURIQ formulas remain in Lutar/Puriq/Formulas/PuriqFormulaLean.lean
-- (NOT imported — it carries honest `sorry` placeholders). No new axiom; the
-- locked v11 count (749/14/163) is unchanged (this scope is counter-excluded).
import Lutar.Puriq.Formulas.ProvedFormulas
-- prove-wave-3 campaign: C1-C20 research candidates (sorry-free; wiring into
-- `lake build` makes CI kernel-check every Wave3 theorem). Mathlib-free modules
-- (Consensus C10-C12, MerkleKraft C8/C13/C14, InfoEstim C9/C17/C20) were ALSO
-- bare-`lean` verified locally; Tier1Mathlib (C1 Tsirelson, C2 CHSH, C6 Jensen)
-- is CI-only (Mathlib does not fit sandbox disk). Lambda (F23) stays Conjecture 1
-- (C7 conditional only, in F23_Uniqueness.lean, NOT imported). Experimental/wave3
-- scope is counter-excluded from the locked v11 count (749/14/163 @ c7c0ba17).
import Lutar.Wave3.Consensus
import Lutar.Wave3.MerkleKraft
import Lutar.Wave3.InfoEstim
-- prove-wave-4: the two Wave-4 modules below are CI-VERIFIED GREEN (lake build).
--   * LambdaBisymmetryWitness — bare-`lean` verified, Lean-core axioms only.
--   * LambdaBlockConsistency  — conditional Λ uniqueness under the WEAKER, more
--     governance-natural block-consistency axiom A6' (declared/disclosed; NOT in
--     the locked v11 kernel). Λ (F23) STAYS Conjecture 1 unconditionally.
import Lutar.Wave4.LambdaBisymmetryWitness  -- A6 discrimination witness (bare-`lean` verified, Lean-core axioms only)
import Lutar.Wave4.LambdaBlockConsistency   -- conditional Λ uniqueness on the WEAKER block-consistency axiom A6' (Mathlib-dep, CI-verified GREEN)
-- prove-wave-5: re-wire the MINIMAL Tier1Mathlib (C1 Tsirelson / C2 CHSH / C6 Jensen)
-- after dropping the non-load-bearing `c1a_tsirelson_constant` numeric remark and its
-- two extra SpecialFunctions imports (wave-4 isolated this module as the lake-build
-- culprit; wave-5 minimizes its build closure to exactly the two modules that DEFINE the
-- instantiated theorems). Signatures verified verbatim vs pinned Mathlib d7317655.
import Lutar.Wave3.Tier1Mathlib             -- C1/C2/C6 (Mathlib-dep) — wave-5 re-wire, CI-gated
-- prove-wave-5: substrate-relevant Mathlib instantiations (AM-GM dominates Λ; Cauchy–Schwarz
-- trust-vector bound). Signatures verified verbatim vs pinned Mathlib d7317655.
import Lutar.Wave5.MathlibCore
-- prove-wave-5: Mathlib-FREE discrete substrate guarantees (bare `lean` 4.13.0 verified
-- sorry-free; #print axioms shows Lean-core deps only). Conformal-coverage count law,
-- UDS collision pigeonhole, monotone optional-stopping (anti-deflation), threshold mono.
import Lutar.Wave5.DiscreteSubstrate
-- prove-wave-6: graph-substrate guarantees from the founder's favorited graph-ML repos.
-- Mathlib-FREE bare-lean cores (F-G2 GNN≤1-WL upper bound, F-G5 bounded-frontier DAG
-- termination, F-G6 relabeling-invariant graph functionals) + Mathlib-dep (F-G1 Fréchet/
-- Bourgain finite distortion, F-G3 geometric-contraction mixing promoting SpectralAdmit).
-- F-G4 Λ-graph isomorphism invariance is closed inside Lutar.GraphLambda (above).
import Lutar.Wave6.GraphSubstrate
import Lutar.Wave6.MetricSpectral
-- prove-wave-6: Mathlib-FREE info/concentration discrete cores (DPI deterministic
-- post-processing, Fano collision-forces-error, conformal-coverage conservation). The
-- analytic KL/sub-Gaussian Mathlib modules are 404 at pin d7317655 (C3/C4/C5 deferred).
import Lutar.Wave6.InfoSubstrate
-- prove-wave-6 (Mathlib bump v4.13.0 -> v4.18.0): C3 Hoeffding / C4 Azuma-Hoeffding /
-- C5 Gibbs (KL >= 0). These were honestly BLOCKED at d7317655 because
-- Mathlib.Probability.Moments.SubGaussian and Mathlib.InformationTheory.KullbackLeibler.Basic
-- were HTTP 404 there. The bump to Mathlib v4.18.0 (aa936c36, Lean v4.18.0) makes both
-- present (earliest tagged release with BOTH files). Pure term-mode re-exports; signatures
-- verified verbatim vs v4.18.0. Experimental/wave6 scope; locked v11 kernel 749/14/163 @
-- c7c0ba17 UNCHANGED; Lambda stays Conjecture 1.
import Lutar.Wave6.SubGaussianKL
-- prove-wave-7: Mathlib-FREE discrete substrate (bare `lean` verified, sorry-free;
-- #print axioms = Lean-core only). W7-4 conformal rank-count calibration/antitone backbone
-- (Vovk-Gammerman-Shafer 2005); W7-6 Doob two-sided audit envelope (Doob 1953). Disjoint
-- from wave-5/wave-6 (which closed coverage-conservation + bounded-frontier termination).
import Lutar.Wave7.DiscreteSubstrate
-- prove-wave-7: Mathlib-DEP kernel-checked. W7-1 vertex-summed graph functional iso-
-- invariance / F-G6 additive companion (Equiv.sum_comp; graph2nn You et al. ICML 2020);
-- W7-5 PAC-Bayes min<=avg<=max routing envelope (Finset.sum_le_card_nsmul /
-- card_nsmul_le_sum; McAllester COLT 1999). Signatures verified vs Mathlib v4.18.0.
import Lutar.Wave7.MathlibCore
-- lambda-uniqueness/unconditional-setalpha (Team A, PhD): Lambda-uniqueness WITHIN
-- principled STRONGER axiom classes. These modules do NOT flip any public claim:
-- the ORIGINAL A1-A5 unconditional statement stays FALSE (Round13.maxAgg_ne_Lambda
-- in-tree) and Lambda (F23) STAYS Conjecture 1 unconditionally. Wiring them into
-- `lake build` makes CI kernel-check every theorem and every #print axioms ledger.
--   * MonotoneAdditiveLinear -- the classical Cauchy monotone-additive=>linear lemma,
--     closed with NO open obligation and NO declared axiom (pure rational squeeze).
--   * SetAlphaUniqueness -- Set alpha = {A1,A2,A3,A4,A5' MULTIPLICATIVITY}. Lambda
--     membership + all five impostor deaths are AXIOM-FREE; lambda_unique_setAlpha is
--     CONDITIONAL on ONE disclosed cited axiom setAlpha_cauchy (multivariable Cauchy core).
--   * SetDeltaUniqueness -- Set delta = {d1,d2,d3 Bisymmetry,d4 PSI,d5' MULT}; continuity
--     DERIVED (Kiss-Shulman 2026 arXiv:2606.05221 Thm 1.1). Lambda membership + impostor
--     deaths AXIOM-FREE; geomMean_unique_KS CONDITIONAL on disclosed cited axioms
--     KS_theorem_1_1 + setDelta_stage2. Drift baseline rolled forward in the same PR.
import Lutar.Wave6.MonotoneAdditiveLinear
import Lutar.Wave6.SetAlphaUniqueness
import Lutar.Wave6.SetDeltaUniqueness
-- prove-coder: EXPERIMENTAL coder-specific INNOVATE pack (Mathlib-FREE; bare `lean`
-- verified sorry-free; #print axioms shows Lean-core deps only + 1 declared
-- collision-resistance axiom on the tamper theorem). Sandbox containment (CS1),
-- bounded repair termination (CS2), router envelope+argmin stability (CR3), Byzantine
-- majority intersection (CV4), conformal never-100% confidence (CC5), receipt-log
-- Kraft compression (CK6), code-context non-interference / poisoned-dependency defense
-- (NI7). EXPERIMENTAL scope: excluded from the LOCKED v11 baseline numbers via
-- .github/scripts/lean_numbers.py EXPERIMENTAL_SCOPES (Lutar/Coder/).
import Lutar.Coder.CoderProofs

-- Wave8 PROVE-NOW experimental pack (prove-next10). EXPERIMENTAL scope:
-- excluded from the LOCKED v11 baseline numbers via
-- .github/scripts/lean_numbers.py EXPERIMENTAL_SCOPES (Lutar/Wave8/).
-- locked-proven stays EXACTLY 5; Λ remains Conjecture 1.
-- Kernel-only Lean-core group (Ph1 axiom-disclosure, M2 hash-chain, L2 min-gate
-- deny-by-default, B1 Byzantine n=3/f=1, S2 Simplex/RTA safety, CP1 split-conformal):
import Lutar.Wave8.AxiomDisclosure
import Lutar.Wave8.HashChain
import Lutar.Wave8.MinGate
import Lutar.Wave8.Byzantine
import Lutar.Wave8.Simplex
import Lutar.Wave8.Conformal
-- Mathlib group (Q1 density-matrix mixture PSD, Q2 Gershgorin governance bound,
-- G1 closest-point-approach minimality, L3 geometric-mean trust strict
-- monotonicity — L3 asserts NO Λ uniqueness, Conjecture 1 untouched):
import Lutar.Wave8.DensityMixture
import Lutar.Wave8.Gershgorin
import Lutar.Wave8.CPA
import Lutar.Wave8.LambdaMono

-- Wave9 candidate-theorem pack (wave9-experimental). EXPERIMENTAL scope:
-- excluded from the LOCKED v11 baseline numbers via
-- .github/scripts/lean_numbers.py EXPERIMENTAL_SCOPES (Lutar/Wave9/).
-- locked-proven stays EXACTLY 5 {F1,F11,F12,F18,F19}; Λ remains Conjecture 1.
-- 8 additive known-theorem formalizations (NO sorry / NO open obligation / NO
-- new declared axiom; #print axioms = Lean/Mathlib core only, per file):
--   MA1 Gershgorin zero-eigenvalue exclusion (spectral form, ℂ-general);
--   CP-1 Merkle / transparency-log inclusion soundness + append-only binding;
--   MC-4 Ville fixed-time anytime-valid supermartingale (Markov) bound;
--   GT-1 Menger cut/path duality (cut⇒disconnect + disjoint-routes⇒cut bound);
--   OE-2 covariance-intersection information-form PSD convex closure;
--   C1 Basilic BDB quorum-intersection threshold n > 3t+d+2q (sharp);
--   PB1 time-uniform PAC-Bayes Ville-assembly core (DV / sup-time = ROADMAP);
--   IF2 robust-declassification non-interference soundness.
import Lutar.Wave9.Gershgorin
import Lutar.Wave9.Merkle
import Lutar.Wave9.Ville
import Lutar.Wave9.Menger
import Lutar.Wave9.CovarianceIntersection
import Lutar.Wave9.BasilicBDB
import Lutar.Wave9.TimeUniformPACBayes
import Lutar.Wave9.RobustDeclass
import Lutar.Wave9.AxiomDisclosure

-- Wave10 candidate-theorem pack (wave10-experimental). EXPERIMENTAL scope:
-- excluded from the LOCKED v11 baseline numbers via
-- .github/scripts/lean_numbers.py EXPERIMENTAL_SCOPES (Lutar/Wave10/).
-- locked-proven stays EXACTLY 5 {F1,F11,F12,F18,F19}; Λ remains Conjecture 1.
-- 6 additive known-theorem formalizations, all Mathlib-FREE / Lean-core-only
-- (NO sorry / NO open obligation / NO new declared axiom; #print axioms =
-- kernel-only [propext, Quot.sound] or none, per file):
--   RA-1 Signal-Temporal-Logic robustness soundness (Donzé–Maler 2010,
--        two-sided bounds: Sat⇒0≤ρ and 0<ρ⇒Sat; not naive iff at boundary);
--   CN-1 quorum-intersection consensus safety / agreement (Lamport Paxos;
--        Howard Flexible Paxos, OPODIS 2016);
--   TE-3 DSSE search-token injectivity (Kamara–Papamanthou, CCS 2012;
--        PRF injectivity as explicit HYPOTHESIS, not a declared axiom);
--   IF-3 non-interference compositionality (Goguen–Meseguer 1982; Mantel MAKS);
--   AU-1 audit-replay determinism + tamper localization (Schneider 1990;
--        Lamport 1978);
--   MR-1 mesh reachability / route monotonicity (CLRS; cf Mathlib
--        Relation.ReflTransGen).
-- Plus a Wave10 AxiomDisclosure ledger re-asserting locked_count_five = 5.
import Lutar.Wave10.STLRobustness
import Lutar.Wave10.QuorumIntersection
import Lutar.Wave10.DSSEToken
import Lutar.Wave10.NonInterferenceComposition
import Lutar.Wave10.ReplayDeterminism
import Lutar.Wave10.ReachabilityRedundancy
import Lutar.Wave10.AxiomDisclosure
-- Wave13 full proof-sweep pack (wave13-sweep) — additive, EXPERIMENTAL, NOT folded
-- into the locked v11 baseline (stays 5 {F1,F11,F12,F18,F19}; Λ remains Conjecture 1;
-- Byzantine BFT safety remains Khipu Conjecture 2). Closes findReplayRoot_complete
-- in-tree (List.find?_isSome) and adds quorum single-valued-vote shadow +
-- clean-statement HM bottleneck. All kernel-clean (axioms ⊆ {propext,
-- Classical.choice, Quot.sound}); NO sorry / NO new declared axiom. Counted under
-- EXPERIMENTAL_SCOPES (Lutar/Wave13/) in .github/scripts/lean_numbers.py.
import Lutar.Wave13.Sweep
-- Wave14 frontier pack (wave14-frontier) — additive, EXPERIMENTAL, NOT folded into the
-- locked v11 baseline (stays 5 {F1,F11,F12,F18,F19}; Λ remains Conjecture 1; Byzantine BFT
-- safety remains Khipu Conjecture 2; DPO klDivergence/pinsker remain FALSE-as-stated).
-- New axiom-free theorems (all axioms ⊆ {propext, Classical.choice, Quot.sound}; NO sorry /
-- NO new declared axiom), each upgrading an existing tab via a clean companion that does NOT
-- edit the baseline (its tracked sorrys stay honest):
--   • Wave14.LeibnizRemainder  — CF-18  alternating-series / Mādhava remainder bound
--                                 (upgrades PACBayes/MadhavaBound).
--   • Wave14.ReedSolomonDistance — CF-19 Reed–Solomon MDS distance lower bound
--                                 (upgrades CodingTheory/ReedSolomonSingleton).
--   • Wave14.VCGEfficiency      — CF-20  VCG efficient-outcome maximality + truthfulness core
--                                 (clean replacement for the broken argmax-based VCG file).
--   • Wave14.LogSumInequality   — CF-21  Cover–Thomas log-sum inequality + Gibbs' inequality
--                                 (the correctly-stated DPI core the DPO tab needs).
-- Counted under EXPERIMENTAL_SCOPES (Lutar/Wave14/) in .github/scripts/lean_numbers.py.
import Lutar.Wave14.LeibnizRemainder
import Lutar.Wave14.ReedSolomonDistance
import Lutar.Wave14.VCGEfficiency
import Lutar.Wave14.LogSumInequality
-- Wave15 frontier pack (wave15-frontier) — additive, EXPERIMENTAL, NOT folded into the
-- locked v11 baseline (stays 5 {F1,F11,F12,F18,F19}). Three files, kernel-clean theorems
-- (every #print axioms ⊆ {propext, Classical.choice, Quot.sound}; NO sorry / NO new axiom):
--   • Wave15.KLDivergenceSimplex (CF-22) — KL(p‖q) ≥ 0 ON THE SIMPLEX, the CONDITIONAL repair
--                              of the FALSE-as-stated DPO klDivergence_nonneg axiom; direct
--                              corollary of Wave14 CF-21 gibbs_inequality. The baseline axiom
--                              token is UNTOUCHED; this is a NEW conditional theorem.
--   • Wave15.PinskerRoadmap     (CF-23) — Pinsker building blocks (per-term Gibbs bound + summed
--                              mass-gap lower bound) + HONEST roadmap. Full conditional Pinsker
--                              (squared-L1 ≤ 2·KL) is NOT proven (binary-bin calculus + DPI
--                              reduction not in Mathlib v4.18.0); DPOFeasibility.pinsker stays
--                              FALSE-as-stated, untouched.
--   • Wave15.BisymmetryCut1     (CF-24) — CUT-1 partial: bisymmetry as a CHECKABLE PREDICATE
--                              (NOT the declared A6 axiom token); geometric-mean bisymmetry
--                              witness + axiom-free CUT-1→CUT-2 bridge. Full bisymmetry⇒quasi-
--                              arithmetic representation is the deferred roadmap item.
-- Λ remains Conjecture 1; Byzantine BFT safety remains Khipu Conjecture 2.
-- Counted under EXPERIMENTAL_SCOPES (Lutar/Wave15/) in .github/scripts/lean_numbers.py.
import Lutar.Wave15.KLDivergenceSimplex
import Lutar.Wave15.PinskerRoadmap
import Lutar.Wave15.BisymmetryCut1
-- Wave16 frontier (EXPERIMENTAL · CI-green · kernel-clean): CF-23 binary-KL convexity crux,
-- CF-24 geometric-mean quasi-arithmetic mean axioms, CF-25 Λ product-multiplicativity (MPP
-- normalization-invariance), CF-26 Abacus positional-encoding well-posedness. All #print axioms
-- ⊆ {propext, Classical.choice, Quot.sound}; NO new axiom token; NO sorry. Λ STAYS Conjecture 1.
import Lutar.Wave16.PinskerConvexity
import Lutar.Wave16.Cut1MeanAxioms
import Lutar.Wave16.LambdaScaleInvariance
import Lutar.Wave16.AbacusPlaceValue
-- Wave17 frontier (EXPERIMENTAL · CI-green · kernel-clean): CF-23 FULL binary (two-bin) Pinsker
-- 2(p-q)² ≤ KL_bin(p,q) (assembling Wave16's g''≥0 crux into the full MVT chain), CF-27 monDEQ
-- well-posedness (strong-monotonicity ⇒ unique equilibrium; pattern-only, arXiv:2006.08591), and
-- CF-28 recurrent-depth contraction amplification (Kʳ-Lipschitz of an r-step recurrent block;
-- mcleish7/retrofitting-recurrence Apache-2.0, arXiv:2511.07384, concept-only). All #print axioms
-- ⊆ {propext, Classical.choice, Quot.sound}; NO new axiom token; NO sorry. Λ STAYS Conjecture 1;
-- DPO `pinsker` STAYS FALSE-as-stated (token UNTOUCHED — binary Pinsker is the CONDITIONAL
-- two-bin case, not the unconditional simplex axiom). Locked-proven set STAYS EXACTLY 5.
import Lutar.Wave17.BinaryPinsker
import Lutar.Wave17.MonDEQWellPosed
import Lutar.Wave17.RecurrentDepth
-- Wave18 frontier (EXPERIMENTAL · CI-green · kernel-clean): CF-29 the Aczél quasi-arithmetic
-- REPRESENTATION theorem — honest forward construction toward CUT-1. AczelRepresentation.lean
-- supplies the representation predicate `IsQuasiArithmetic2`, the BKS dyadic-midpoint recursion
-- `IsDyadicMidpointGen`, the COMPLETE soundness/only-if direction (a quasi-arithmetic mean is
-- reflexive/symmetric/BISYMMETRIC/strict-mono + satisfies the dyadic recursion), the analytic
-- heart `generator_collapse_affine`/`generator_unique_up_to_affine` (generator-uniqueness via the
-- Round13 `monotone_additive_linear` rational squeeze, NO continuity), and the Mathlib-backed
-- continuous-extension bridge `gen_continuous_of_denseRange`. Cut1Chain.lean pins φ=log via A2
-- 1-homogeneity (`expMidpoint_homogeneous`), shows the log generator IS the geometric mean
-- (`expMidpoint_eq_geom` = √(xy) = Λ binary slice), and re-exports the axiom-free conditional
-- CUT-1 conclusion `cut1_conditional_lambda` through the Wave15 bisymmetry bridge. All #print
-- axioms ⊆ {propext, Classical.choice, Quot.sound}; NO new axiom token; NO sorry. The ONLY
-- remaining gap to full CUT-1 = the topological `dyadic_image_dense` lemma (BKS arXiv:2208.07083
-- Step 2, NOT in Mathlib v4.18.0). Λ UNCONDITIONAL uniqueness STAYS Conjecture 1. Locked-proven
-- set STAYS EXACTLY 5. Counted under EXPERIMENTAL_SCOPES (Lutar/Wave18/) in lean_numbers.py.
import Lutar.Wave18.AczelRepresentation
import Lutar.Wave18.Cut1Chain
-- Wave19 frontier (EXPERIMENTAL · CI-green · kernel-clean): CUT-1 DENSITY step — closes the
-- Burai–Kiss–Szokol (arXiv:2208.07083) Lemma 6 Step-2 density engine, the single remaining gap
-- after Wave18. DisjointOpens.lean builds the MISSING "countably-many-pairwise-disjoint-nonempty
-- -opens on a separable line" contradiction engine (Mathlib has the separable-space half; we key
-- it to this construction as `false_of_uncountable_pairwiseDisjoint_Ioo`). Density.lean defines
-- the two-sided accumulation predicate, extracts a gap from non-density, discharges the
-- disjointness half of BKS bullet 3 from a clean gap-shift ordering (`pairwiseDisjoint_Ioo_of_sep`),
-- and assembles `dyadic_image_dense`/`dyadic_image_dense_of_sep`. AccumulationUncountable.lean
-- closes the QUANTITATIVE core of BKS bullet 2: a nonempty perfect subset of ℝ is uncountable
-- (Cantor injection `Perfect.exists_nat_bool_injection`; `ℕ → Bool` has cardinality 𝔠), reducing
-- "uncountably many accumulation points" to "contains a nonempty perfect subset". Cut1Density.lean
-- splices density into Wave18's `gen_continuous_of_denseRange` (BKS Step 4). DyadicImageDense.lean
-- is the capstone: `dyadic_image_dense_via_perfect` proves density kernel-clean from exactly TWO
-- named BKS literature residuals (B-residual: perfect subset of two-sided acc points; C-order: the
-- gap-separated image endpoints), and `continuous_of_perfect_accumulation` carries it to
-- continuity. All #print axioms ⊆ {propext, Classical.choice, Quot.sound}; NO new axiom; no proof placeholders.
-- The residual is the BKS self-similar generator structure (Aczél–Dhombres pp.287–290), HONESTLY
-- documented, NOT faked. Λ UNCONDITIONAL uniqueness STAYS Conjecture 1. Locked-proven set STAYS
-- EXACTLY 5. Counted under EXPERIMENTAL_SCOPES (Lutar/Wave19/) in lean_numbers.py.
import Lutar.Wave19.DisjointOpens
import Lutar.Wave19.Density
import Lutar.Wave19.AccumulationUncountable
import Lutar.Wave19.Cut1Density
import Lutar.Wave19.DyadicImageDense
-- Wave20 density PRIMITIVES (EXPERIMENTAL · CI-green · kernel-clean): the two STANDALONE reusable
-- engines behind the Burai–Kiss–Szokol (arXiv:2208.07083) Lemma 6 Step-2 density argument, proved
-- as construction-agnostic Mathlib-style lemmas (NO Wave18/Wave19 dependency). DisjointOpens.lean
-- = PRIMITIVE A: a pairwise-disjoint family of nonempty open sets is countable — given BOTH as a
-- self-contained rational-injection proof over ℝ (each nonempty open meets ℚ; disjointness ⇒ the
-- choice i ↦ qᵢ injective; ℚ countable) AND as the general SeparableSpace packaging, with the
-- uncountable/False contradiction corollaries and the concrete Set.Ioo interval form the BKS map
-- produces. Accumulation.lean = PRIMITIVE B: the quantitative engine "a nonempty perfect set of
-- reals is uncountable" (Cantor injection Perfect.exists_nat_bool_injection; ℕ→Bool has card 𝔠),
-- the requested bridge "closed + no isolated points ⇒ perfect ⇒ uncountable", the two-sided
-- accumulation predicate IsTwoSidedAccPt + its bridge to Mathlib AccPt, reducing BKS bullet 2 to a
-- SINGLE honestly-stated residual (B-residual: the dyadic image's closure contains a nonempty
-- perfect set of two-sided accumulation points; the Aczél–Dhombres self-similar structure, NOT
-- faked, NOT axiomatised). All #print axioms ⊆ {propext, Classical.choice, Quot.sound}; NO new
-- axiom; no proof placeholders. Λ UNCONDITIONAL uniqueness STAYS Conjecture 1. Locked-proven set
-- STAYS EXACTLY 5. Counted under EXPERIMENTAL_SCOPES (Lutar/Wave20/) in lean_numbers.py.
import Lutar.Wave20.DisjointOpens
import Lutar.Wave20.Accumulation

-- Wave21 frontier (EXPERIMENTAL · kernel-clean): CUT-1 FINAL — closes the FINAL residual of the
-- Burai–Kiss–Szokol (arXiv:2208.07083) Lemma 6 Step-2 density lemma and assembles the COMPLETE
-- dyadic_image_dense. Uncountable.lean discharges the (B) residual ("uncountably many two-sided
-- accumulation points") kernel-clean via the LIGHT monotone-extension route of the parent paper
-- arXiv:2107.07391 Theorem 8 — NO perfect-set / Cantor machinery: one-sided-gap points of any
-- H ⊆ ℝ inject into ℚ (countable), a non-two-sided point is a one-sided-gap point, so an
-- uncountable H has uncountably many two-sided accumulation points; and a STRICTLY monotone
-- g : ℝ → ℝ has uncountable range (injects the continuum Ioo 0 1). DyadicImageDense.lean assembles
-- dyadic_image_dense_complete with (B) internal (only the (C-order) gap-shift ordering remains a
-- stated structural hypothesis, the genuine BKS Fourth-step analytic fact). Cut1Final.lean splices
-- into Wave18 gen_continuous_of_denseRange (continuous BKS generator) and re-exports the CONDITIONAL
-- cut1_conditional_lambda_closed. All #print axioms ⊆ {propext, Classical.choice, Quot.sound}; NO
-- new axiom; no proof placeholders. Closing CUT-1 makes the CONDITIONAL Λ chain axiom-clean end to
-- end on its stated hypotheses; Λ UNCONDITIONAL uniqueness STAYS Conjecture 1 (machine-checked
-- FALSE). Locked-proven set STAYS EXACTLY 5. Counted under EXPERIMENTAL_SCOPES (Lutar/Wave21/).
import Lutar.Wave21.Uncountable
import Lutar.Wave21.DyadicImageDense
import Lutar.Wave21.Cut1Final

-- Wave22 frontier (EXPERIMENTAL · kernel-clean): CUT-1 FINAL (C-order) — closes the ONE honest
-- residual carried by Wave21's dyadic_image_dense_complete, the BKS Fourth-step gap-shift ordering
-- R s ≤ L t (arXiv:2107.07391 Thm 8 eqs (8)-(9)). GapShiftOrdering.lean derives the discrete
-- midpoint chain F (f a) (f c) ≤ F (f b) (f d) (from the generator recursion + monotone f) and the
-- monotone-limit passage; CorderClosure.lean builds the (C-order) endpoint data L α = F X α,
-- R α = F Y α (nonemptiness from φ,ψ strict mono; gap-shift DERIVED via corder_gapshift, not
-- assumed); Cut1Corder.lean discharges Wave21's hC into full CUT-1 density and continuity, with the
-- gap-shift FULLY derived (continuous_of_corder_fully_derived). LambdaConditional.lean STRENGTHENS
-- the CONDITIONAL Λ result: the sharpest conditional uniqueness cut1_sharp_conditional_lambda drops
-- both the bisymmetry hypothesis (proved redundant, bisymmetry_is_redundant) and the unit-norm
-- fᵢ 1 = 1 (derived from A3 + separability, slice_one_eq_one_of_sep), leaving the WEAKEST checkable
-- set {A1-A5}+separability+slice-multiplicativity+slice-monotonicity. All #print axioms ⊆ {propext,
-- Classical.choice, Quot.sound}; NO new axiom; no proof placeholders. CUT-1 is now FULLY closed on
-- its stated CHECKABLE hypotheses; Λ UNCONDITIONAL uniqueness STAYS Conjecture 1 (machine-checked
-- FALSE). Locked-proven set STAYS EXACTLY 5. Counted under EXPERIMENTAL_SCOPES (Lutar/Wave22/).
import Lutar.Wave22.GapShiftOrdering
import Lutar.Wave22.CorderClosure
import Lutar.Wave22.Cut1Corder
import Lutar.Wave22.LambdaConditional

-- Wave23 frontier (EXPERIMENTAL · kernel-clean): CONDITIONAL Khipu BFT SAFETY — attacks the genuine
-- open conjecture (Khipu Conjecture 2, ubuntu_quorum_safety). UNCONDITIONAL safety stays Conjecture
-- 2 (a Byzantine organ can equivocate; n ≤ 3f is impossible — Lamport–Shostak–Pease, Wave8). We do
-- NOT attempt the false unconditional statement. QuorumSafety.lean identifies the WEAKEST CHECKABLE
-- hypothesis that turns quorum safety into a THEOREM — honest non-equivocation under signed votes
-- (the BFT analog of slice-multiplicativity for Λ): votes are a RELATION (faulty organs MAY
-- equivocate), honest organs satisfy HonestNonEquivocation. exists_honest_of_card_gt /
-- exists_honest_in_inter DISCHARGE the non-faulty-witness residual the kernel/Round12
-- ubuntu_quorum_safety left deferred (Finset.not_subset + card_le_card). Reusing the in-tree,
-- placeholder-free quorum_intersection_honest (Round12, n ≥ 3f+1 ⟹ |Q₁∩Q₂| > f),
-- khipu_quorum_safety_conditional proves agreement (no split-brain): two quorums of size ≥ n−f
-- certifying v₁,v₂ ⟹ v₁ = v₂. subsumes_single_valued_shadow re-derives the Wave13 single-valued
-- shadow, witnessing strict generality. All #print axioms ⊆ {propext, Classical.choice, Quot.sound};
-- NO new axiom; no proof placeholders. CONDITIONAL on {n ≥ 3f+1, |faulty| ≤ f, |Qᵢ| ≥ n−f, honest
-- non-equivocation}; UNCONDITIONAL BFT safety STAYS Conjecture 2. Locked-proven set STAYS EXACTLY 5;
-- Λ STAYS Conjecture 1. Counted under EXPERIMENTAL_SCOPES (Lutar/Wave23/).
import Lutar.Wave23.QuorumSafety
import Lutar.Uniqueness.LambdaEquiv
import Lutar.Uniqueness.Identifiability
import Lutar.Uniqueness.TheoremU
import Lutar.Uniqueness.AxiomCheck
import Lutar.Wave24.AdmissibilityCertificate


/-!
# Lutar — root module

Re-exports the verified theorems on the Lutar Invariant Λ_k
and the Doctrine V3 §6/§7 theorems (zero sorry), plus the v16
ancient-foundations grafts: Horus-Eye dyadic encoding, Brahmi
AxisValue option type, CRT weight chunking (b4_rosie_amaru_ancient);
Egyptian false-position calibration, Akhmim/RMP 2/n threshold table,
BM 13901 completing-the-square solver, Mādhava arctan-bound for
TH14 PAC-Bayes refinement, Brahmagupta–Fibonacci 2-square
composition identity (b3_a11oy_ancient);
Babylonian (YBC 7289) sqrt iteration as Banach contraction,
Liu Hui polygon-doubling π, sexagesimal regular-number criterion,
Qhapaq Ñan chasqui relay-chain latency bound, receipt
transduction invariant (b5_ouroboros_foundations).

v16 Feynman additions (PR #41):
- `Lutar.Feynman.FeynmanLineage` — citation chain as compilable data (0 sorries, 0 axioms)
- `Lutar.Feynman.PathIntegralAuditSum` — Z_Λ over audit fiber (4 SORRY_v16_OPEN)
- `Lutar.Knot.ReidemeisterConjecture` — R1/R2 axiom; R3 proved at flat-segment level
-/

