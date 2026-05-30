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
