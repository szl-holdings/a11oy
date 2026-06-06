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
  resolveV4ProofRouteId,
  ROUTE_ID_V4_ALIASES,
  validateProofArtifacts,
} from './proof-route.js';
export type {
  ClaimOrAction,
  ProofArtifactKind,
  ProofRoute,
  ProofRouteId,
  ProofRouteIdV4,
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
  CYCLE_ID_V4_ALIASES,
  DEFAULT_CYCLES,
  INITIAL_ALMANAC_STATE,
  rebuildAlmanac,
  V3_CYCLES,
  V4_CYCLES,
} from './almanac.js';
export type {
  AlmanacAdvanceResult,
  AlmanacState,
  CycleConfig,
  CycleEvent,
  CycleId,
} from './almanac.js';

// ─── v3 ecosystem-master contract modules ────────────────────────────────────
// Closes the v3 "needs_code" pieces from ouroboros-runtime-contract.v3.json:
//   - domain_pack_dispatcher    → ./domain-pack.js
//   - operator_approval_gate    → ./operator-approval.js
//   - evidence_pack_contract    → ./evidence-pack.js
//   - operational_modes         → ./operational-modes.js
// Plus extends proof-route.ts with PRF_CLAIM_BOUND_RESEARCH and
// PRF_OPERATIONAL_ACTION, and almanac.ts with the review_cycle.
export { ROUTE_ID_V2_ALIASES } from './proof-route.js';

export {
  dispatchDomainPack,
  DOMAIN_PACKS,
  TASK_TO_PACK,
  TASK_TO_PACK_V4,
} from './domain-pack.js';
export type {
  DomainPack,
  DomainPackId,
  RoutingDecision,
  RoutingInput,
  RoutingTaskType,
} from './domain-pack.js';

export {
  DEFAULT_DENY_PROVIDER,
  makeAutoGrantProvider,
  requestApproval,
} from './operator-approval.js';
export type {
  ApprovalDecision,
  ApprovalProvider,
  ApprovalRecord,
  ApprovalRequest,
} from './operator-approval.js';

export { buildEvidencePack, validateEvidencePack } from './evidence-pack.js';
export type {
  EvidencePack,
  EvidencePackInput,
  EvidencePackValidationError,
} from './evidence-pack.js';

export {
  isAutoExecutionAllowed,
  OPERATIONAL_MODES,
} from './operational-modes.js';
export type {
  OperationalMode,
  OperationalModePolicy,
} from './operational-modes.js';

// ─── v4 ecosystem-master modules (replit_innovate_full_payload) ──────────────
// Closes the v4 "next_code_bindings" pieces from
// docs/research/ouroboros-runtime-contract.v4.json:
//   - validators.registry              → ./validator-registry.js
//   - ingestion_contracts (Sentra/Amaru) → ./ingestion-contract.js
//   - innovation_engine                → ./innovation-engine.js
//   - output_paths                     → ./output-paths.js
//   - paris_cadence_cycle alias        → ./almanac.js (CYCLE_ID_V4_ALIASES)
export {
  summarizeValidators,
  VALIDATOR_REGISTRY,
} from './validator-registry.js';
export type {
  ValidatorId,
  ValidatorResult,
  ValidatorSeverity,
  ValidatorSpec,
  ValidatorSummary,
} from './validator-registry.js';

export { INGESTION_CONTRACTS, validateIngestion } from './ingestion-contract.js';
export type {
  AmaruIngestType,
  IngestionContract,
  IngestionTarget,
  IngestionValidationError,
  LoopProfile,
  RequiredOutput,
  SentraIngestType,
} from './ingestion-contract.js';

export {
  INNOVATION_ENGINE_DEFAULT,
  INNOVATION_LOOPS,
  validateInnovationEngine,
} from './innovation-engine.js';
export type {
  InnovationEngineState,
  InnovationLoopId,
  InnovationLoopSpec,
} from './innovation-engine.js';

export { OUTPUT_PATHS, resolveOutputPath } from './output-paths.js';
export type { OutputPathKey } from './output-paths.js';

// ─── v4 validator FUNCTIONS (runnable implementations of VALIDATOR_REGISTRY) ──
// Until v4, the validator registry was data-only (id + severity + rule text).
// `v4-validators/` ships the 9 pure functions that compute `passed` from a
// typed `RuntimeContext`. See packages/ouroboros/src/v4-validators/VALIDATORS.md
// for the codex-aligned semantics.
export {
  valBudgetEnforcer,
  valNoSilentMutation,
  valProofRequired,
  valRiskEscalation,
  valApprovalForCriticalAction,
  valSecurityProofRequired,
  valSourcePriorityRequired,
  valMergeSafety,
  valConsistencyBeforeCommit,
  VALIDATOR_FNS,
  runValidators,
  V4_VALIDATOR_IDS,
} from './v4-validators/index.js';
export type {
  RuntimeContext,
  RuntimeRiskTier,
  RuntimeOperationalMode,
  ApprovalSnapshot,
  SourceCitation,
  MergeAction,
  ConsistencySnapshot,
  MutationRecord,
  ValidatorFn,
  RunValidatorsResult,
} from './v4-validators/index.js';

// v6 ecosystem layer (a11oy_ultimate_replit_payload).
// Adds shared runtime services list, halt-condition vocabulary, extended
// task routing, tool permission matrix, secrets-broker spec, sandbox
// execution classes, and the agent registry contract.
export {
  SHARED_RUNTIME_SERVICES_V6,
  V6_HALT_CONDITIONS,
  V6_NEW_HALT_CONDITIONS,
  TASK_TO_PACK_V6,
  TOOL_PERMISSION_MATRIX,
  checkToolPermission,
  SECRETS_BROKER_SPEC,
  SANDBOX_POLICY,
  AGENT_REGISTRY_REQUIRED_FIELDS,
  validateAgentRegistryEntry,
  V6_MANIFEST_SUMMARY,
} from './v6-payload.js';
export type {
  SharedRuntimeServiceV6,
  HaltConditionV6,
  RoutingTaskTypeV6,
  PermittedToolV6,
  ToolPermissionEntry,
  RiskTierOverride,
  ToolPermissionMatrix,
  PermissionDenyReason,
  PermissionDecision,
  SecretsBrokerSpec,
  SandboxExecutionClassId,
  SandboxExecutionClass,
  SandboxPolicy,
  AgentRegistryRequiredField,
  AgentRegistryEntry,
  V6ManifestSummary,
} from './v6-payload.js';

// SZL Holdings government procurement readiness (NYSTEC pre-briefing audit
// 2026-04-30): structured platform scorecards, NIST AI RMF + DoD tenets +
// GSAR 552.239-7001 alignment, SAM.gov + NAICS, action items.
export {
  PLATFORM_READINESS,
  NIST_RMF_ALIGNMENT,
  DOD_TENETS,
  GSAR_552_239_7001_READINESS,
  RECOMMENDED_NAICS_CODES,
  SAM_GOV_REGISTRATION_STEPS,
  NEW_YORK_STATE_REGISTRATION_STEPS,
  PRE_MEETING_ACTION_ITEMS,
  COMPETITIVE_POSITIONING_STATEMENT,
  GOV_READINESS_MANIFEST,
  getPlatformReadiness,
  listGapsAcrossPlatforms,
  actionItemsByGroup,
} from './gov-readiness.js';
export type {
  GovPlatformId,
  PlatformReadiness,
  NistRmfFunction,
  NistRmfRow,
  DodTenet,
  ReadinessStatus,
  DodTenetRow,
  GsarRow,
  NaicsCode,
  SamGovStep,
  ActionGroup,
  ActionItem,
  GovReadinessManifest,
} from './gov-readiness.js';
