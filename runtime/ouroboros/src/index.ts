export type {
  ConsistencyFn,
  DeltaFn,
  ExitReason,
  LoopConfig,
  LoopStep,
  LoopTrace,
  StepFn,
  StepResult,
} from './types.js';

export { runLoop } from './loop-kernel.js';
export type { RunLoopArgs } from './loop-kernel.js';

export {
  numericConsistency,
  setConsistency,
  stringConsistency,
  vectorConsistency,
} from './consistency.js';

export { allocateDepth } from './depth-allocator.js';
export type { AllocatorInput, AllocatorOutput } from './depth-allocator.js';

// ─── Operational contract modules (ouroboros-runtime-contract.v2) ────────────
// These three modules close the "missing pieces" identified in the v2 payload:
//   - proof_route_resolver       → ./proof-route.js
//   - risk_tier_escalation_gate  → ./risk-tier.js
//   - almanac_cycle_advancer     → ./almanac.js
// They are pure, deterministic, and replayable.
export {
  PROOF_ROUTES,
  resolveProofRoute,
  validateProofArtifacts,
} from './proof-route.js';
export type {
  ClaimOrAction,
  ProofArtifactKind,
  ProofRoute,
  ProofRouteId,
} from './proof-route.js';

export { evaluateRiskTier, RISK_TIERS } from './risk-tier.js';
export type {
  RiskTier,
  RiskTierContext,
  RiskTierDecision,
  RiskTierPolicy,
} from './risk-tier.js';

export {
  advanceAlmanac,
  DEFAULT_CYCLES,
  INITIAL_ALMANAC_STATE,
  rebuildAlmanac,
} from './almanac.js';
export type {
  AlmanacAdvanceResult,
  AlmanacState,
  CycleConfig,
  CycleEvent,
  CycleId,
} from './almanac.js';
