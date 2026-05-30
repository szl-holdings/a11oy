import {
  createToolEnvelope,
  emitReceipt,
  verifyChain,
  type EmitReceiptOptions,
  type OperationalReceipt,
  type ToolEnvelope,
  type VerifyResult,
} from "@szl-holdings/a11oy-receipt-substrate";

export type AutonomousLearningEventType =
  | "AUTONOMOUS_LEARNING_PROPOSAL"
  | "AUTONOMOUS_LEARNING_EVALUATION"
  | "HUMAN_PROMOTION";

export type AutonomousLearningClaimStatus =
  | "verified-runtime"
  | "release-payload"
  | "lean-backed-current-green"
  | "lean-backed-needs-upstream-ci"
  | "thesis-anchor"
  | "historical"
  | "roadmap"
  | "staged";

export interface ForbiddenClaimScan {
  readonly passed: boolean;
  readonly scanner: string;
  readonly forbiddenMatches: readonly string[];
}

export interface SourceIngress {
  readonly sourceUri: string;
  readonly licenseClass: "public" | "licensed" | "permissioned" | "user-owned";
  readonly contentHash?: string;
}

export interface AutonomousLearningProposalInput {
  readonly proposalId: string;
  readonly runId: string;
  readonly actorId: string;
  readonly proposalKind: "doc" | "json-map" | "patch" | "theorem-runtime-hook" | "benchmark-route" | "uds-hf-publication";
  readonly sourceCommit: string;
  readonly policyHash: string;
  readonly lambdaAxes: readonly string[];
  readonly toolVersions: Record<string, string>;
  readonly sourceIngress: readonly SourceIngress[];
  readonly intendedFiles: readonly string[];
  readonly expectedBehavior: string;
  readonly riskClass: "low" | "medium" | "high";
  readonly proposalPayloadDigest: string;
  readonly forbiddenClaimScan: ForbiddenClaimScan;
  readonly stagedAdvisory: string;
  readonly claimStatus: AutonomousLearningClaimStatus;
  readonly details?: Record<string, unknown>;
}

export interface AutonomousLearningEvaluationInput {
  readonly proposalId: string;
  readonly runId: string;
  readonly actorId: string;
  readonly proposalReceiptId: string;
  readonly proposalActorId: string;
  readonly sourceCommit: string;
  readonly policyHash: string;
  readonly harnessCommitSha: string;
  readonly replaySeeds: readonly number[];
  readonly frozenTime: string;
  readonly inputRoots: readonly string[];
  readonly outputRoots: readonly string[];
  readonly deterministicPass: boolean;
  readonly varianceBounds: Record<string, number>;
  readonly adversarialChecks: readonly string[];
  readonly failureReceipts: readonly string[];
  readonly outcome: "pass" | "fail";
  readonly details?: Record<string, unknown>;
}

export interface HumanPromotionInput {
  readonly proposalId: string;
  readonly runId: string;
  readonly actorId: string;
  readonly proposalReceiptId: string;
  readonly evaluationReceiptId: string;
  readonly proposalActorId: string;
  readonly evaluationActorId: string;
  readonly humanReviewerId: string;
  readonly approvedBy: string;
  readonly approvalTime: string;
  readonly approvalBasis: string;
  readonly sourceCommit: string;
  readonly policyHash: string;
  readonly ciRuns: readonly string[];
  readonly manifestSha256: string;
  readonly bundleSha256: string;
  readonly rollbackRef: string;
  readonly publishedSurfaces: readonly string[];
  readonly details?: Record<string, unknown>;
}

export interface AutonomousLearningChainResult extends VerifyResult {
  readonly proposalCount: number;
  readonly evaluationCount: number;
  readonly promotionCount: number;
}

function requireNonEmpty(value: string, field: string): string {
  if (!value.trim()) {
    throw new Error(`${field} is required`);
  }
  return value;
}

function validateProposal(input: AutonomousLearningProposalInput): void {
  requireNonEmpty(input.proposalId, "proposalId");
  requireNonEmpty(input.runId, "runId");
  requireNonEmpty(input.actorId, "actorId");
  requireNonEmpty(input.sourceCommit, "sourceCommit");
  requireNonEmpty(input.policyHash, "policyHash");
  requireNonEmpty(input.proposalPayloadDigest, "proposalPayloadDigest");
  if (!input.lambdaAxes.length) throw new Error("lambdaAxes must be non-empty");
  if (!input.sourceIngress.length) throw new Error("sourceIngress must be non-empty");
  if (!input.intendedFiles.length) throw new Error("intendedFiles must be non-empty");
  if (!input.forbiddenClaimScan.passed || input.forbiddenClaimScan.forbiddenMatches.length > 0) {
    throw new Error("forbidden claim scan must pass before proposal receipt emission");
  }
}

function validateEvaluation(input: AutonomousLearningEvaluationInput): void {
  requireNonEmpty(input.proposalReceiptId, "proposalReceiptId");
  requireNonEmpty(input.proposalActorId, "proposalActorId");
  requireNonEmpty(input.actorId, "actorId");
  if (input.actorId === input.proposalActorId) {
    throw new Error("evaluation actor must be distinct from proposal actor");
  }
  if (input.outcome === "pass" && input.replaySeeds.length < 5) {
    throw new Error("passing evaluation requires at least five replay seeds");
  }
  if (!input.inputRoots.length || !input.outputRoots.length) {
    throw new Error("evaluation requires inputRoots and outputRoots");
  }
}

function validatePromotion(input: HumanPromotionInput): void {
  requireNonEmpty(input.proposalReceiptId, "proposalReceiptId");
  requireNonEmpty(input.evaluationReceiptId, "evaluationReceiptId");
  requireNonEmpty(input.humanReviewerId, "humanReviewerId");
  requireNonEmpty(input.approvedBy, "approvedBy");
  requireNonEmpty(input.approvalBasis, "approvalBasis");
  if (input.humanReviewerId === input.proposalActorId || input.humanReviewerId === input.evaluationActorId) {
    throw new Error("human reviewer must be distinct from proposal and evaluation actors");
  }
  if (input.actorId !== input.humanReviewerId) {
    throw new Error("promotion actor must be the named human reviewer");
  }
  if (!input.ciRuns.length) throw new Error("promotion requires at least one CI run");
  if (!input.publishedSurfaces.length) throw new Error("promotion requires published surfaces");
}

export function createAutonomousLearningProposalEnvelope(input: AutonomousLearningProposalInput): ToolEnvelope {
  validateProposal(input);
  return createToolEnvelope({
    protocol: "a11oy",
    actor_id: input.actorId,
    tool_name: "autonomous_learning_proposal",
    lambda_axes: input.lambdaAxes,
    payload: {
      schemaVersion: "a11oy.autonomous-learning.proposal.v1",
      eventType: "AUTONOMOUS_LEARNING_PROPOSAL",
      ...input,
    },
    metadata: {
      doctrine: "docs/AUTONOMOUS_LEARNING_DOCTRINE.md",
      mode: "dream-evaluate-propose-only",
    },
  });
}

export function emitAutonomousLearningProposalReceipt(
  input: AutonomousLearningProposalInput,
  options: EmitReceiptOptions = {},
): OperationalReceipt {
  return emitReceipt(createAutonomousLearningProposalEnvelope(input), {
    ...options,
    eventType: "AUTONOMOUS_LEARNING_PROPOSAL",
    policy: {
      vertical: "autonomous-learning",
      regime: "doctrine-v6",
      ...options.policy,
    },
  });
}

export function createAutonomousLearningEvaluationEnvelope(input: AutonomousLearningEvaluationInput): ToolEnvelope {
  validateEvaluation(input);
  return createToolEnvelope({
    protocol: "a11oy",
    actor_id: input.actorId,
    tool_name: "autonomous_learning_evaluation",
    lambda_axes: ["measurabilityHonesty", "provenanceIntegrity", "operatorReversibility"],
    payload: {
      schemaVersion: "a11oy.autonomous-learning.evaluation.v1",
      eventType: "AUTONOMOUS_LEARNING_EVALUATION",
      ...input,
    },
    metadata: {
      doctrine: "docs/AUTONOMOUS_LEARNING_DOCTRINE.md",
      replayRequirement: "at-least-five-replays-for-pass",
    },
  });
}

export function emitAutonomousLearningEvaluationReceipt(
  input: AutonomousLearningEvaluationInput,
  options: EmitReceiptOptions = {},
): OperationalReceipt {
  return emitReceipt(createAutonomousLearningEvaluationEnvelope(input), {
    ...options,
    eventType: "AUTONOMOUS_LEARNING_EVALUATION",
    policy: {
      vertical: "autonomous-learning",
      regime: "doctrine-v6",
      ...options.policy,
    },
  });
}

export function createHumanPromotionEnvelope(input: HumanPromotionInput): ToolEnvelope {
  validatePromotion(input);
  return createToolEnvelope({
    protocol: "a11oy",
    actor_id: input.actorId,
    tool_name: "human_promotion",
    lambda_axes: ["moralGrounding", "measurabilityHonesty", "provenanceIntegrity", "operatorReversibility"],
    payload: {
      schemaVersion: "a11oy.autonomous-learning.human-promotion.v1",
      eventType: "HUMAN_PROMOTION",
      ...input,
    },
    metadata: {
      doctrine: "docs/AUTONOMOUS_LEARNING_DOCTRINE.md",
      boundary: "human-promotion-required",
    },
  });
}

export function emitHumanPromotionReceipt(
  input: HumanPromotionInput,
  options: EmitReceiptOptions = {},
): OperationalReceipt {
  return emitReceipt(createHumanPromotionEnvelope(input), {
    ...options,
    eventType: "HUMAN_PROMOTION",
    policy: {
      vertical: "autonomous-learning",
      regime: "doctrine-v6",
      ...options.policy,
    },
  });
}

export function verifyAutonomousLearningChain(chain: readonly OperationalReceipt[]): AutonomousLearningChainResult {
  const errors: string[] = [...verifyChain(chain).errors];
  const proposals = chain.filter((receipt) => receipt.event_type === "AUTONOMOUS_LEARNING_PROPOSAL");
  const evaluations = chain.filter((receipt) => receipt.event_type === "AUTONOMOUS_LEARNING_EVALUATION");
  const promotions = chain.filter((receipt) => receipt.event_type === "HUMAN_PROMOTION");

  const proposalById = new Map<string, OperationalReceipt>();
  for (const receipt of proposals) {
    const payload = receipt.envelope.payload as { proposalId?: string };
    if (!payload.proposalId) {
      errors.push(`${receipt.receipt_id}: proposal missing proposalId`);
      continue;
    }
    proposalById.set(payload.proposalId, receipt);
  }

  const evaluationById = new Map<string, OperationalReceipt>();
  for (const receipt of evaluations) {
    const payload = receipt.envelope.payload as {
      proposalId?: string;
      proposalReceiptId?: string;
      outcome?: string;
      replaySeeds?: readonly number[];
      sourceCommit?: string;
      policyHash?: string;
    };
    if (!payload.proposalId || !payload.proposalReceiptId) {
      errors.push(`${receipt.receipt_id}: evaluation missing proposal reference`);
      continue;
    }
    const proposal = proposalById.get(payload.proposalId);
    if (!proposal) {
      errors.push(`${receipt.receipt_id}: evaluation missing proposal ancestor`);
    } else {
      const proposalPayload = proposal.envelope.payload as { sourceCommit?: string; policyHash?: string };
      if (payload.proposalReceiptId !== proposal.receipt_id) {
        errors.push(`${receipt.receipt_id}: proposalReceiptId mismatch`);
      }
      if (payload.sourceCommit !== proposalPayload.sourceCommit) {
        errors.push(`${receipt.receipt_id}: source commit drift requires new proposal`);
      }
      if (payload.policyHash !== proposalPayload.policyHash) {
        errors.push(`${receipt.receipt_id}: policy hash drift requires new proposal`);
      }
    }
    if (payload.outcome === "pass" && (payload.replaySeeds?.length ?? 0) < 5) {
      errors.push(`${receipt.receipt_id}: passing evaluation has fewer than five replay seeds`);
    }
    evaluationById.set(receipt.receipt_id, receipt);
  }

  for (const receipt of promotions) {
    const payload = receipt.envelope.payload as {
      proposalId?: string;
      proposalReceiptId?: string;
      evaluationReceiptId?: string;
      humanReviewerId?: string;
      proposalActorId?: string;
      evaluationActorId?: string;
      sourceCommit?: string;
      policyHash?: string;
    };
    const proposal = payload.proposalId ? proposalById.get(payload.proposalId) : undefined;
    const evaluation = payload.evaluationReceiptId ? evaluationById.get(payload.evaluationReceiptId) : undefined;
    if (!proposal) {
      errors.push(`${receipt.receipt_id}: promotion missing proposal ancestor`);
    }
    if (!evaluation) {
      errors.push(`${receipt.receipt_id}: promotion missing evaluation ancestor`);
    } else {
      const evaluationPayload = evaluation.envelope.payload as { outcome?: string; sourceCommit?: string; policyHash?: string };
      if (evaluationPayload.outcome !== "pass") {
        errors.push(`${receipt.receipt_id}: promotion requires passing evaluation`);
      }
      if (payload.sourceCommit !== evaluationPayload.sourceCommit) {
        errors.push(`${receipt.receipt_id}: source commit drift after evaluation`);
      }
      if (payload.policyHash !== evaluationPayload.policyHash) {
        errors.push(`${receipt.receipt_id}: policy hash drift after evaluation`);
      }
    }
    if (payload.humanReviewerId === payload.proposalActorId || payload.humanReviewerId === payload.evaluationActorId) {
      errors.push(`${receipt.receipt_id}: human reviewer must be distinct`);
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    proposalCount: proposals.length,
    evaluationCount: evaluations.length,
    promotionCount: promotions.length,
  };
}
