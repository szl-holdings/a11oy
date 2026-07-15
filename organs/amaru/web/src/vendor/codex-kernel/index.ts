// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — packages/codex-kernel/src/index.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/**
 * Codex-Kernel — public API surface.
 *
 * Replay-grade governed iteration. Pure TS, zero runtime deps.
 * Inspired by the Dresden Codex Venus tables; aligned with EU AI Act
 * Article 12 logging and NIST AI RMF traceability requirements.
 */

export type {
  ApprovalEvent,
  ApprovalStatus,
  Budgets,
  DecisionReceipt,
  Hex,
  ISO8601,
  Json,
  KernelConfig,
  KernelRunResult,
  LoopPolicy,
  PipelineStage,
  ProofLedgerEntry,
  RunSummary,
  StepProposal,
  StopReason,
  TraceEvent,
  ValidationContext,
  ValidatorResult,
  ValidatorSeverity,
} from './types.js';

export { canonicalize, chainHash, hashJson, hashString, shortHash } from './hash.js';
export { driftBounds, evidenceProvenance, humanGate, stateTransitionRule } from './validators.js';
export { buildReceiptId, finalizeReceipt, isMocked } from './receipts.js';
export { ProofLedger } from './ledger.js';
export { runLoop } from './kernel.js';
export {
  parseTraceJsonl,
  replay,
  serializeTraceJsonl,
  type ReplayReport,
} from './replay.js';
export {
  DRESDEN_DEFAULT_CONFIG,
  DRESDEN_INITIAL_STATE,
  dresdenSteps,
  type DresdenSimConfig,
  type VenusRow,
  type VenusState,
} from './dresden-venus.js';
export {
  DEFAULT_DEPTH_ALLOCATOR_CONFIG,
  decideDepth,
  deltaHammingWitness,
  rollingSoftFailRate,
  severityEntropyBits,
  type AllocatorStepRecord,
  type DepthAllocatorConfig,
  type DepthAllocatorContext,
  type DepthAllocatorResult,
  type DepthVerdict,
} from './depth-allocator.js';
