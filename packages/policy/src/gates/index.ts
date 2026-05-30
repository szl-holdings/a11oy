// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Barrel export — all 35 anchor formula policy gates
// 5 from a11oy#108 (cursor/policy-gates-hardening-2f18) + 30 new gates
//
// Lean commit anchor: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
// Zenodo concept DOI: https://doi.org/10.5281/zenodo.20162352

// ── Original 5 from a11oy#108 ─────────────────────────────────────────────────
export { adversarialRobustnessGate } from "./adversarialRobustness_gate.ts";
export type {
  AdversarialRobustnessGateConfig,
  AdversarialRobustnessGateOpts,
} from "./adversarialRobustness_gate.ts";

export { falsePositionGate } from "./falsePosition_gate.ts";
export type {
  FalsePositionGateConfig,
  FalsePositionGateOpts,
} from "./falsePosition_gate.ts";

export { liuHuiPiGate } from "./liuHuiPi_gate.ts";
export type {
  LiuHuiPiGateConfig,
  LiuHuiPiGateOpts,
} from "./liuHuiPi_gate.ts";

export { madhavaBoundGate } from "./madhavaBound_gate.ts";
export type {
  MadhavaBoundGateConfig,
  MadhavaBoundGateOpts,
} from "./madhavaBound_gate.ts";

export { summationInvariantGate } from "./summationInvariant_gate.ts";
export type {
  DecisionReceipt,
  KhipuReceiptGateOpts,
  OrganReceipt,
} from "./summationInvariant_gate.ts";

// ── G36–G40 Formula Extension Gates (Doctrine v6) ─────────────────────────────

export { gaussianMechanismDPGate } from "./gaussianMechanismDP_gate.ts";
export type {
  GaussianMechanismDPGateConfig,
  GaussianMechanismDPGateOpts,
  GaussianMechanismDPDecision,
} from "./gaussianMechanismDP_gate.ts";

// G37 VCGTruthfulness — STAGED-ADVISORY: 1 sorry in Lean dominant-strategy proof
export { vcgTruthfulnessGate } from "./vcgTruthfulness_gate.ts";
export type {
  VCGTruthfulnessGateConfig,
  VCGTruthfulnessGateOpts,
  VCGTruthfulnessDecision,
  AttesterValuation,
} from "./vcgTruthfulness_gate.ts";

export { rdpCompositionGate } from "./rdpComposition_gate.ts";
export type {
  RDPCompositionGateConfig,
  RDPCompositionGateOpts,
  RDPCompositionDecision,
} from "./rdpComposition_gate.ts";

export { certifiedRobustnessGate } from "./certifiedRobustness_gate.ts";
export type {
  CertifiedRobustnessGateConfig,
  CertifiedRobustnessGateOpts,
  CertifiedRobustnessDecision,
} from "./certifiedRobustness_gate.ts";

export { reedSolomonSingletonGate } from "./reedSolomonSingleton_gate.ts";
export type {
  ReedSolomonSingletonGateConfig,
  ReedSolomonSingletonGateOpts,
  ReedSolomonSingletonDecision,
} from "./reedSolomonSingleton_gate.ts";

// ── Axiom gates (A1–A9, A10–A12, A14) ────────────────────────────────────────
export { soundnessAxiomGate } from "./soundnessAxiom_gate.ts";
export type {
  SoundnessAxiomGateConfig,
  SoundnessAxiomGateOpts,
  SoundnessAxiomDecision,
} from "./soundnessAxiom_gate.ts";

export { moralGroundingFloorGate } from "./moralGroundingFloor_gate.ts";
export type {
  MoralGroundingFloorGateConfig,
  MoralGroundingFloorGateOpts,
  MoralGroundingFloorDecision,
} from "./moralGroundingFloor_gate.ts";

export { measurabilityHonestyFloorGate } from "./measurabilityHonestyFloor_gate.ts";
export type {
  MeasurabilityHonestyFloorGateConfig,
  MeasurabilityHonestyFloorGateOpts,
  MeasurabilityHonestyFloorDecision,
} from "./measurabilityHonestyFloor_gate.ts";

export { dualWitnessDisjointnessGate } from "./dualWitnessDisjointness_gate.ts";
export type {
  DualWitnessDisjointnessGateConfig,
  DualWitnessDisjointnessGateOpts,
  DualWitnessDisjointnessDecision,
} from "./dualWitnessDisjointness_gate.ts";

export { deterministicReplayGate } from "./deterministicReplay_gate.ts";
export type {
  DeterministicReplayGateConfig,
  DeterministicReplayGateOpts,
  DeterministicReplayDecision,
} from "./deterministicReplay_gate.ts";

export { hashChainIntegrityGate } from "./hashChainIntegrity_gate.ts";
export type {
  HashChainIntegrityGateConfig,
  ChainEntry,
  HashChainIntegrityGateOpts,
  HashChainIntegrityDecision,
} from "./hashChainIntegrity_gate.ts";

export { bekensteinBoundGate } from "./bekensteinBound_gate.ts";
export type {
  BekensteinBoundGateConfig,
  BekensteinBoundGateOpts,
  BekensteinBoundDecision,
} from "./bekensteinBound_gate.ts";

export { ingestDisciplineGate } from "./ingestDiscipline_gate.ts";
export type {
  IngestDisciplineGateConfig,
  IngestDisciplineGateOpts,
  IngestDisciplineDecision,
} from "./ingestDiscipline_gate.ts";

export { doctrineCompletenessGate } from "./doctrineCompleteness_gate.ts";
export type {
  DoctrineCompletenessGateConfig,
  DoctrineCompletenessGateOpts,
  DoctrineCompletenessDecision,
} from "./doctrineCompleteness_gate.ts";

export { temporalConsistencyGate } from "./temporalConsistency_gate.ts";
export type {
  TemporalConsistencyGateConfig,
  TemporalConsistencyGateOpts,
  TemporalConsistencyDecision,
} from "./temporalConsistency_gate.ts";

export { causalSeparabilityGate } from "./causalSeparability_gate.ts";
export type {
  CausalSeparabilityGateConfig,
  CausalSeparabilityGateOpts,
  CausalSeparabilityDecision,
} from "./causalSeparability_gate.ts";

export { constructiveTransparencyGate } from "./constructiveTransparency_gate.ts";
export type {
  ConstructiveTransparencyGateConfig,
  ConstructiveTransparencyGateOpts,
  ConstructiveTransparencyDecision,
} from "./constructiveTransparency_gate.ts";

export { economicGroundingGate } from "./economicGrounding_gate.ts";
export type {
  EconomicGroundingGateConfig,
  EconomicGroundingGateOpts,
  EconomicGroundingDecision,
} from "./economicGrounding_gate.ts";

// ── Derivation gates (T1–T10) ─────────────────────────────────────────────────
export { rhoClosureCompositionGate } from "./rhoClosureComposition_gate.ts";
export type {
  RhoClosureCompositionGateConfig,
  RhoClosureCompositionGateOpts,
  RhoClosureCompositionDecision,
} from "./rhoClosureComposition_gate.ts";

export { lambdaMonotonicityGate } from "./lambdaMonotonicity_gate.ts";
export type {
  LambdaMonotonicityGateConfig,
  LambdaMonotonicityGateOpts,
  LambdaMonotonicityDecision,
} from "./lambdaMonotonicity_gate.ts";

export { merkleDagBatchGate } from "./merkleDagBatch_gate.ts";
export type {
  MerkleDagBatchGateConfig,
  MerkleDagBatchGateOpts,
  MerkleDagBatchDecision,
} from "./merkleDagBatch_gate.ts";

export { bekensteinEntropyMeasureGate } from "./bekensteinEntropyMeasure_gate.ts";
export type {
  BekensteinEntropyMeasureGateConfig,
  BekensteinEntropyMeasureGateOpts,
  BekensteinEntropyMeasureDecision,
} from "./bekensteinEntropyMeasure_gate.ts";

export { replayDeterminismGate } from "./replayDeterminism_gate.ts";
export type {
  ReplayDeterminismGateConfig,
  ReplayDeterminismGateOpts,
  ReplayDeterminismDecision,
} from "./replayDeterminism_gate.ts";

export { conjunctiveGateCounterexampleGate } from "./conjunctiveGateCounterexample_gate.ts";
export type {
  ConjunctiveGateCounterexampleGateConfig,
  ConjunctiveGateCounterexampleGateOpts,
  ConjunctiveGateCounterexampleDecision,
} from "./conjunctiveGateCounterexample_gate.ts";

export { privacyMaskGate } from "./privacyMask_gate.ts";
export type {
  PrivacyMaskGateConfig,
  PrivacyMaskGateOpts,
  PrivacyMaskDecision,
} from "./privacyMask_gate.ts";

export { singleWitnessExclusionGate } from "./singleWitnessExclusion_gate.ts";
export type {
  SingleWitnessExclusionGateConfig,
  SingleWitnessExclusionGateOpts,
  SingleWitnessExclusionDecision,
} from "./singleWitnessExclusion_gate.ts";

export { crossRegionPolicyGate } from "./crossRegionPolicy_gate.ts";
export type {
  CrossRegionPolicyGateConfig,
  CrossRegionPolicyGateOpts,
  CrossRegionPolicyDecision,
} from "./crossRegionPolicy_gate.ts";

export { doctrineEnforcementGate } from "./doctrineEnforcement_gate.ts";
export type {
  DoctrineEnforcementGateConfig,
  DoctrineEnforcementGateOpts,
  DoctrineEnforcementDecision,
} from "./doctrineEnforcement_gate.ts";

// ── New Theorem gates (TH1–TH7) ───────────────────────────────────────────────
export { composabilityGate } from "./composability_gate.ts";
export type {
  ComposabilityGateConfig,
  ComposabilityGateOpts,
  ComposabilityDecision,
} from "./composability_gate.ts";

export { replayDoiDualityGate } from "./replayDoiDuality_gate.ts";
export type {
  ReplayDoiDualityGateConfig,
  ReplayDoiDualityGateOpts,
  ReplayDoiDualityDecision,
} from "./replayDoiDuality_gate.ts";

export { anatomyReductionGate } from "./anatomyReduction_gate.ts";
export type {
  AnatomyReductionGateConfig,
  AnatomyReductionGateOpts,
  AnatomyReductionDecision,
} from "./anatomyReduction_gate.ts";

export { lambdaCategoryComposabilityGate } from "./lambdaCategoryComposability_gate.ts";
export type {
  LambdaCategoryComposabilityGateConfig,
  LambdaCategoryComposabilityGateOpts,
  LambdaCategoryComposabilityDecision,
} from "./lambdaCategoryComposability_gate.ts";

export { receiptChainConfluenceGate } from "./receiptChainConfluence_gate.ts";
export type {
  ReceiptChainConfluenceGateConfig,
  ReceiptChainConfluenceGateOpts,
  ReceiptChainConfluenceDecision,
} from "./receiptChainConfluence_gate.ts";

export { bekensteinEntropyDpiGate } from "./bekensteinEntropyDpi_gate.ts";
export type {
  BekensteinEntropyDpiGateConfig,
  BekensteinEntropyDpiGateOpts,
  BekensteinEntropyDpiDecision,
} from "./bekensteinEntropyDpi_gate.ts";

export { curryHowardReceiptCalculusGate } from "./curryHowardReceiptCalculus_gate.ts";
export type {
  CurryHowardReceiptCalculusGateConfig,
  CurryHowardReceiptCalculusGateOpts,
  CurryHowardReceiptCalculusDecision,
} from "./curryHowardReceiptCalculus_gate.ts";

// ── Lean Theorem gates (TH_L1–TH_L4) ─────────────────────────────────────────
export { lambdaUniquenessGate } from "./lambdaUniqueness_gate.ts";
export type {
  LambdaUniquenessGateConfig,
  LambdaUniquenessGateOpts,
  LambdaUniquenessDecision,
} from "./lambdaUniqueness_gate.ts";

export { lambdaMinMaxBoundsGate } from "./lambdaMinMaxBounds_gate.ts";
export type {
  LambdaMinMaxBoundsGateConfig,
  LambdaMinMaxBoundsGateOpts,
  LambdaMinMaxBoundsDecision,
} from "./lambdaMinMaxBounds_gate.ts";

export { bekensteinSoundnessGate } from "./bekensteinSoundness_gate.ts";
export type {
  BekensteinSoundnessGateConfig,
  BekensteinSoundnessGateOpts,
  BekensteinSoundnessDecision,
} from "./bekensteinSoundness_gate.ts";

export { rhoClosureProductionGate } from "./rhoClosureProduction_gate.ts";
export type {
  RhoClosureProductionGateConfig,
  RhoClosureProductionGateOpts,
  RhoClosureProductionDecision,
} from "./rhoClosureProduction_gate.ts";

// ── Pareto Stabilization (wired in a11oy#114) ─────────────────────────────────
export {
  paretoStabilizationGate,
  buildCandidateStream,
} from "./pareto_stabilization.ts";
export type {
  ObjectiveVector,
  ParetoStabilizationResult,
  ParetoDsseReceipt,
} from "./pareto_stabilization.ts";

