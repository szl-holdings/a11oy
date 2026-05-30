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
export { adversarialRobustnessGate } from "./adversarialRobustness_gate";
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
} from "./summationInvariant_gate";

// ── Axiom gates (A1–A9, A10–A12, A14) ────────────────────────────────────────
export { soundnessAxiomGate } from "./soundnessAxiom_gate";
export type {
  SoundnessAxiomGateConfig,
  SoundnessAxiomGateOpts,
  SoundnessAxiomDecision,
} from "./soundnessAxiom_gate";

export { moralGroundingFloorGate } from "./moralGroundingFloor_gate";
export type {
  MoralGroundingFloorGateConfig,
  MoralGroundingFloorGateOpts,
  MoralGroundingFloorDecision,
} from "./moralGroundingFloor_gate";

export { measurabilityHonestyFloorGate } from "./measurabilityHonestyFloor_gate";
export type {
  MeasurabilityHonestyFloorGateConfig,
  MeasurabilityHonestyFloorGateOpts,
  MeasurabilityHonestyFloorDecision,
} from "./measurabilityHonestyFloor_gate";

export { dualWitnessDisjointnessGate } from "./dualWitnessDisjointness_gate";
export type {
  DualWitnessDisjointnessGateConfig,
  DualWitnessDisjointnessGateOpts,
  DualWitnessDisjointnessDecision,
} from "./dualWitnessDisjointness_gate";

export { deterministicReplayGate } from "./deterministicReplay_gate";
export type {
  DeterministicReplayGateConfig,
  DeterministicReplayGateOpts,
  DeterministicReplayDecision,
} from "./deterministicReplay_gate";

export { hashChainIntegrityGate } from "./hashChainIntegrity_gate";
export type {
  HashChainIntegrityGateConfig,
  ChainEntry,
  HashChainIntegrityGateOpts,
  HashChainIntegrityDecision,
} from "./hashChainIntegrity_gate";

export { bekensteinBoundGate } from "./bekensteinBound_gate";
export type {
  BekensteinBoundGateConfig,
  BekensteinBoundGateOpts,
  BekensteinBoundDecision,
} from "./bekensteinBound_gate";

export { ingestDisciplineGate } from "./ingestDiscipline_gate";
export type {
  IngestDisciplineGateConfig,
  IngestDisciplineGateOpts,
  IngestDisciplineDecision,
} from "./ingestDiscipline_gate";

export { doctrineCompletenessGate } from "./doctrineCompleteness_gate";
export type {
  DoctrineCompletenessGateConfig,
  DoctrineCompletenessGateOpts,
  DoctrineCompletenessDecision,
} from "./doctrineCompleteness_gate";

export { temporalConsistencyGate } from "./temporalConsistency_gate";
export type {
  TemporalConsistencyGateConfig,
  TemporalConsistencyGateOpts,
  TemporalConsistencyDecision,
} from "./temporalConsistency_gate";

export { causalSeparabilityGate } from "./causalSeparability_gate";
export type {
  CausalSeparabilityGateConfig,
  CausalSeparabilityGateOpts,
  CausalSeparabilityDecision,
} from "./causalSeparability_gate";

export { constructiveTransparencyGate } from "./constructiveTransparency_gate";
export type {
  ConstructiveTransparencyGateConfig,
  ConstructiveTransparencyGateOpts,
  ConstructiveTransparencyDecision,
} from "./constructiveTransparency_gate";

export { economicGroundingGate } from "./economicGrounding_gate";
export type {
  EconomicGroundingGateConfig,
  EconomicGroundingGateOpts,
  EconomicGroundingDecision,
} from "./economicGrounding_gate";

// ── Derivation gates (T1–T10) ─────────────────────────────────────────────────
export { rhoClosureCompositionGate } from "./rhoClosureComposition_gate";
export type {
  RhoClosureCompositionGateConfig,
  RhoClosureCompositionGateOpts,
  RhoClosureCompositionDecision,
} from "./rhoClosureComposition_gate";

export { lambdaMonotonicityGate } from "./lambdaMonotonicity_gate";
export type {
  LambdaMonotonicityGateConfig,
  LambdaMonotonicityGateOpts,
  LambdaMonotonicityDecision,
} from "./lambdaMonotonicity_gate";

export { merkleDagBatchGate } from "./merkleDagBatch_gate";
export type {
  MerkleDagBatchGateConfig,
  MerkleDagBatchGateOpts,
  MerkleDagBatchDecision,
} from "./merkleDagBatch_gate";

export { bekensteinEntropyMeasureGate } from "./bekensteinEntropyMeasure_gate";
export type {
  BekensteinEntropyMeasureGateConfig,
  BekensteinEntropyMeasureGateOpts,
  BekensteinEntropyMeasureDecision,
} from "./bekensteinEntropyMeasure_gate";

export { replayDeterminismGate } from "./replayDeterminism_gate";
export type {
  ReplayDeterminismGateConfig,
  ReplayDeterminismGateOpts,
  ReplayDeterminismDecision,
} from "./replayDeterminism_gate";

export { conjunctiveGateCounterexampleGate } from "./conjunctiveGateCounterexample_gate";
export type {
  ConjunctiveGateCounterexampleGateConfig,
  ConjunctiveGateCounterexampleGateOpts,
  ConjunctiveGateCounterexampleDecision,
} from "./conjunctiveGateCounterexample_gate";

export { privacyMaskGate } from "./privacyMask_gate";
export type {
  PrivacyMaskGateConfig,
  PrivacyMaskGateOpts,
  PrivacyMaskDecision,
} from "./privacyMask_gate";

export { singleWitnessExclusionGate } from "./singleWitnessExclusion_gate";
export type {
  SingleWitnessExclusionGateConfig,
  SingleWitnessExclusionGateOpts,
  SingleWitnessExclusionDecision,
} from "./singleWitnessExclusion_gate";

export { crossRegionPolicyGate } from "./crossRegionPolicy_gate";
export type {
  CrossRegionPolicyGateConfig,
  CrossRegionPolicyGateOpts,
  CrossRegionPolicyDecision,
} from "./crossRegionPolicy_gate";

export { doctrineEnforcementGate } from "./doctrineEnforcement_gate";
export type {
  DoctrineEnforcementGateConfig,
  DoctrineEnforcementGateOpts,
  DoctrineEnforcementDecision,
} from "./doctrineEnforcement_gate";

// ── New Theorem gates (TH1–TH7) ───────────────────────────────────────────────
export { composabilityGate } from "./composability_gate";
export type {
  ComposabilityGateConfig,
  ComposabilityGateOpts,
  ComposabilityDecision,
} from "./composability_gate";

export { replayDoiDualityGate } from "./replayDoiDuality_gate";
export type {
  ReplayDoiDualityGateConfig,
  ReplayDoiDualityGateOpts,
  ReplayDoiDualityDecision,
} from "./replayDoiDuality_gate";

export { anatomyReductionGate } from "./anatomyReduction_gate";
export type {
  AnatomyReductionGateConfig,
  AnatomyReductionGateOpts,
  AnatomyReductionDecision,
} from "./anatomyReduction_gate";

export { lambdaCategoryComposabilityGate } from "./lambdaCategoryComposability_gate";
export type {
  LambdaCategoryComposabilityGateConfig,
  LambdaCategoryComposabilityGateOpts,
  LambdaCategoryComposabilityDecision,
} from "./lambdaCategoryComposability_gate";

export { receiptChainConfluenceGate } from "./receiptChainConfluence_gate";
export type {
  ReceiptChainConfluenceGateConfig,
  ReceiptChainConfluenceGateOpts,
  ReceiptChainConfluenceDecision,
} from "./receiptChainConfluence_gate";

export { bekensteinEntropyDpiGate } from "./bekensteinEntropyDpi_gate";
export type {
  BekensteinEntropyDpiGateConfig,
  BekensteinEntropyDpiGateOpts,
  BekensteinEntropyDpiDecision,
} from "./bekensteinEntropyDpi_gate";

export { curryHowardReceiptCalculusGate } from "./curryHowardReceiptCalculus_gate";
export type {
  CurryHowardReceiptCalculusGateConfig,
  CurryHowardReceiptCalculusGateOpts,
  CurryHowardReceiptCalculusDecision,
} from "./curryHowardReceiptCalculus_gate";

// ── Lean Theorem gates (TH_L1–TH_L4) ─────────────────────────────────────────
export { lambdaUniquenessGate } from "./lambdaUniqueness_gate";
export type {
  LambdaUniquenessGateConfig,
  LambdaUniquenessGateOpts,
  LambdaUniquenessDecision,
} from "./lambdaUniqueness_gate";

export { lambdaMinMaxBoundsGate } from "./lambdaMinMaxBounds_gate";
export type {
  LambdaMinMaxBoundsGateConfig,
  LambdaMinMaxBoundsGateOpts,
  LambdaMinMaxBoundsDecision,
} from "./lambdaMinMaxBounds_gate";

export { bekensteinSoundnessGate } from "./bekensteinSoundness_gate";
export type {
  BekensteinSoundnessGateConfig,
  BekensteinSoundnessGateOpts,
  BekensteinSoundnessDecision,
} from "./bekensteinSoundness_gate";

export { rhoClosureProductionGate } from "./rhoClosureProduction_gate";
export type {
  RhoClosureProductionGateConfig,
  RhoClosureProductionGateOpts,
  RhoClosureProductionDecision,
} from "./rhoClosureProduction_gate";
