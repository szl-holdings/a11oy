import handoffManifest from "../../../../docs/cross-repo-handoff-manifest.json" with { type: "json" };
import {
  createToolEnvelope,
  emitReceipt,
  type EmitReceiptOptions,
  type OperationalReceipt,
  type ToolEnvelope,
} from "../../../receipt-substrate/src/index.ts";

export type HandoffAccessState = "blocked-by-access" | "write-ready";
export type HandoffState = "ready-for-owner-apply" | "needs-target-runner" | "blocked-by-access" | "complete";

export interface CrossRepoHandoffEntry {
  readonly handoffId: string;
  readonly targetRepo: string;
  readonly targetBranch: string;
  readonly patchPath: string;
  readonly statusPath: string;
  readonly patchSha256: string;
  readonly accessState: HandoffAccessState;
  readonly handoffState: HandoffState;
  readonly localValidation: readonly string[];
  readonly targetValidationRequired: readonly string[];
  readonly completionRequires: readonly string[];
  readonly claimStatus: string;
}

export interface CrossRepoHandoffManifest {
  readonly schemaVersion: number;
  readonly generatedBy: string;
  readonly observedAt: string;
  readonly canonicalRule: string;
  readonly accessBoundary: string;
  readonly forbiddenClaims: readonly string[];
  readonly handoffs: readonly CrossRepoHandoffEntry[];
}

export interface CrossRepoHandoffReceiptInput {
  readonly handoffId: string;
  readonly actorId: string;
  readonly sourceCommit?: string;
  readonly outcome: "queued" | "owner-applied" | "target-ci-passed" | "blocked";
  readonly upstreamPrUrl?: string;
  readonly upstreamCiUrl?: string;
  readonly details?: Record<string, unknown>;
}

const manifest = handoffManifest as CrossRepoHandoffManifest;

export function getCrossRepoHandoffManifest(): CrossRepoHandoffManifest {
  return manifest;
}

export function getCrossRepoHandoff(handoffId: string): CrossRepoHandoffEntry {
  const handoff = manifest.handoffs.find((entry) => entry.handoffId === handoffId);
  if (!handoff) {
    throw new Error(`Unknown cross-repo handoff: ${handoffId}`);
  }
  return handoff;
}

function assertCompletionEvidence(handoff: CrossRepoHandoffEntry, input: CrossRepoHandoffReceiptInput): void {
  if (input.outcome === "target-ci-passed" && (!input.upstreamPrUrl || !input.upstreamCiUrl)) {
    throw new Error(`Handoff ${handoff.handoffId} requires upstreamPrUrl and upstreamCiUrl for target-ci-passed`);
  }
  if (handoff.handoffState === "complete" && (!input.upstreamPrUrl || !input.upstreamCiUrl)) {
    throw new Error(`Complete handoff ${handoff.handoffId} requires target PR and CI evidence`);
  }
}

export function createCrossRepoHandoffEnvelope(input: CrossRepoHandoffReceiptInput): ToolEnvelope {
  const handoff = getCrossRepoHandoff(input.handoffId);
  assertCompletionEvidence(handoff, input);
  return createToolEnvelope({
    protocol: "a11oy",
    actor_id: input.actorId,
    tool_name: "a11oy_cross_repo_handoff",
    lambda_axes: ["provenanceIntegrity", "measurabilityHonesty", "operatorReversibility"],
    payload: {
      schemaVersion: "a11oy.cross-repo-handoff.v1",
      handoffId: handoff.handoffId,
      targetRepo: handoff.targetRepo,
      targetBranch: handoff.targetBranch,
      patchPath: handoff.patchPath,
      statusPath: handoff.statusPath,
      patchSha256: handoff.patchSha256,
      accessState: handoff.accessState,
      handoffState: handoff.handoffState,
      claimStatus: handoff.claimStatus,
      localValidation: handoff.localValidation,
      targetValidationRequired: handoff.targetValidationRequired,
      completionRequires: handoff.completionRequires,
      forbiddenClaims: manifest.forbiddenClaims,
      sourceCommit: input.sourceCommit ?? "unknown",
      outcome: input.outcome,
      upstreamPrUrl: input.upstreamPrUrl,
      upstreamCiUrl: input.upstreamCiUrl,
      details: input.details ?? {},
    },
    metadata: {
      manifest: "docs/cross-repo-handoff-manifest.json",
      accessBoundary: manifest.accessBoundary,
    },
  });
}

export function emitCrossRepoHandoffReceipt(
  input: CrossRepoHandoffReceiptInput,
  options: EmitReceiptOptions = {},
): OperationalReceipt {
  return emitReceipt(createCrossRepoHandoffEnvelope(input), {
    ...options,
    eventType: "A11OY_OPERATION",
    policy: {
      vertical: "cross-repo-handoff",
      regime: "doctrine-v6",
      ...options.policy,
    },
  });
}
