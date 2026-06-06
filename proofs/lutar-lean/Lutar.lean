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
-- PURIQ proved-formula pack (zero sorry, Mathlib-free): F1/F11/F12/F18/F19
-- (original sprint) + F4/F7/F22 (append-only/DAG/FIFO sprint 2026-06-04). Wiring
-- this into `lake build` makes CI kernel-check every PROVED PURIQ formula. The 15
-- still-open PURIQ formulas remain in Lutar/Puriq/Formulas/PuriqFormulaLean.lean
-- (NOT imported — it carries honest `sorry` placeholders). No new axiom; the
-- locked v11 count (749/14/163) is unchanged (this scope is counter-excluded).
import Lutar.Puriq.Formulas.ProvedFormulas


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
