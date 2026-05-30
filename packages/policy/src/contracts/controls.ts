import controlsEvidenceMap from "../../../../docs/controls-evidence-map.json" with { type: "json" };
import actionContractManifest from "../../../../docs/action-contract-manifest.json" with { type: "json" };
import {
  createToolEnvelope,
  emitReceipt,
  type EmitReceiptOptions,
  type OperationalReceipt,
  type ToolEnvelope,
} from "@szl-holdings/a11oy-receipt-substrate";

export type ControlClaimStatus =
  | "verified-runtime"
  | "release-payload"
  | "lean-backed-current-green"
  | "lean-backed-needs-upstream-ci"
  | "thesis-anchor"
  | "historical"
  | "roadmap";

export interface ControlEvidenceEntry {
  readonly controlId: string;
  readonly title: string;
  readonly description: string;
  readonly claimStatus: ControlClaimStatus;
  readonly evidencePaths: readonly string[];
  readonly validationCommands: readonly string[];
  readonly receiptHook: {
    readonly eventType: string;
    readonly status: "runtime-available" | "roadmap" | "staged";
    readonly description: string;
  };
  readonly hfExposure: string;
  readonly udsExposure: string;
  readonly invariants: readonly string[];
}

export interface ControlEvidenceMap {
  readonly schemaVersion: number;
  readonly generatedBy: string;
  readonly observedAt: string;
  readonly canonicalRule: string;
  readonly cleanRoomRule: string;
  readonly controls: readonly ControlEvidenceEntry[];
}

export interface ActionContractManifest {
  readonly schemaVersion: "a11oy.action-contract.v0.1";
  readonly contractId: string;
  readonly claimStatus: ControlClaimStatus;
  readonly canonicalRule: string;
  readonly cleanRoom: {
    readonly sourcePatternIds: readonly string[];
    readonly copyingRule: "pattern-only";
    readonly endorsementBoundary: string;
  };
  readonly intent: {
    readonly title: string;
    readonly requestedAction: string;
    readonly actionClass: string;
    readonly vertical: string;
    readonly regime: string;
    readonly riskTier: string;
    readonly lambdaAxes: readonly string[];
  };
  readonly identity: {
    readonly actorId: string;
    readonly actorKind: string;
    readonly orgUnit: string;
    readonly sessionId: string;
    readonly signerVerifier: string;
  };
  readonly policy: {
    readonly policyDocumentRef: string;
    readonly policyHash: string;
    readonly mandatoryAxes: readonly string[];
    readonly minimumLambdaCoverage: number;
    readonly approvalGate: string;
  };
  readonly evidence: {
    readonly manifestRefs: readonly string[];
    readonly attestationRefs: readonly string[];
    readonly sourceCommit: string;
    readonly payloadDigest: string;
    readonly testCommands: readonly string[];
    readonly localEvidenceRefs: readonly string[];
    readonly claimRefs: readonly string[];
  };
  readonly receiptSinks: {
    readonly primaryJsonl: string;
    readonly payloadBundlePath: string;
    readonly udsManifestRef: string;
    readonly retentionDays: number;
    readonly chainMode: "hash-chain";
  };
  readonly replayBounds: {
    readonly deterministicInputs: readonly string[];
    readonly idempotencyKey: string;
    readonly maxReplays: number;
    readonly replayWindowSeconds: number;
    readonly seedPolicy: string;
    readonly expectedRoot: string;
    readonly clockRule: string;
  };
  readonly egressLimits: {
    readonly defaultDeny: boolean;
    readonly allowedDestinations: readonly string[];
    readonly deniedCapabilities: readonly string[];
    readonly maxBytesPerAction: number;
    readonly secretHandling: string;
    readonly exportClasses: readonly string[];
  };
  readonly udsProofPoint: {
    readonly wording: string;
    readonly forbiddenClaims: readonly string[];
    readonly catalogGradeBlockers: readonly string[];
    readonly packageInspectionCommands: readonly string[];
  };
}

export interface ControlReceiptInput {
  readonly controlId: string;
  readonly actorId: string;
  readonly sourceCommit?: string;
  readonly validationCommand?: string;
  readonly outcome: "pass" | "fail" | "staged";
  readonly details?: Record<string, unknown>;
}

export interface ActionContractReceiptInput {
  readonly actorId: string;
  readonly sourceCommit?: string;
  readonly payloadDigest?: string;
  readonly policyHash?: string;
  readonly outcome: "preflight-pass" | "preflight-fail" | "staged";
  readonly details?: Record<string, unknown>;
}

const controlsMap = controlsEvidenceMap as ControlEvidenceMap;
const actionContract = actionContractManifest as ActionContractManifest;

export function getControlsEvidenceMap(): ControlEvidenceMap {
  return controlsMap;
}

export function getActionContractManifest(): ActionContractManifest {
  return actionContract;
}

export function getControlEvidence(controlId: string): ControlEvidenceEntry {
  const control = controlsMap.controls.find((entry) => entry.controlId === controlId);
  if (!control) {
    throw new Error(`Unknown A11oy control: ${controlId}`);
  }
  return control;
}

export function createControlEvidenceEnvelope(input: ControlReceiptInput): ToolEnvelope {
  const control = getControlEvidence(input.controlId);
  const validationCommand = input.validationCommand ?? control.validationCommands[0];
  if (!validationCommand) {
    throw new Error(`Control ${control.controlId} has no validation command`);
  }

  return createToolEnvelope({
    protocol: "a11oy",
    actor_id: input.actorId,
    tool_name: "a11oy_control_evidence",
    lambda_axes: [
      "moralGrounding",
      "measurabilityHonesty",
      "provenanceIntegrity",
    ],
    payload: {
      controlId: control.controlId,
      title: control.title,
      claimStatus: control.claimStatus,
      evidencePaths: control.evidencePaths,
      validationCommand,
      outcome: input.outcome,
      receiptHook: control.receiptHook,
      hfExposure: control.hfExposure,
      udsExposure: control.udsExposure,
      invariants: control.invariants,
      sourceCommit: input.sourceCommit ?? "unknown",
      details: input.details ?? {},
    },
    metadata: {
      manifest: "docs/controls-evidence-map.json",
      cleanRoomRule: controlsMap.cleanRoomRule,
    },
  });
}

export function emitControlEvidenceReceipt(
  input: ControlReceiptInput,
  options: EmitReceiptOptions = {},
): OperationalReceipt {
  return emitReceipt(createControlEvidenceEnvelope(input), {
    ...options,
    eventType: "A11OY_OPERATION",
    policy: {
      vertical: "a11oy-controls",
      regime: "doctrine-v6",
      ...options.policy,
    },
  });
}

export function createActionContractEnvelope(input: ActionContractReceiptInput): ToolEnvelope {
  return createToolEnvelope({
    protocol: "a11oy",
    actor_id: input.actorId,
    tool_name: "a11oy_action_contract_preflight",
    lambda_axes: actionContract.intent.lambdaAxes,
    payload: {
      contractId: actionContract.contractId,
      claimStatus: actionContract.claimStatus,
      requestedAction: actionContract.intent.requestedAction,
      actionClass: actionContract.intent.actionClass,
      riskTier: actionContract.intent.riskTier,
      approvalGate: actionContract.policy.approvalGate,
      policyHash: input.policyHash ?? actionContract.policy.policyHash,
      payloadDigest: input.payloadDigest ?? actionContract.evidence.payloadDigest,
      sourceCommit: input.sourceCommit ?? actionContract.evidence.sourceCommit,
      receiptSink: actionContract.receiptSinks.primaryJsonl,
      replayBounds: actionContract.replayBounds,
      egressLimits: actionContract.egressLimits,
      udsProofPoint: actionContract.udsProofPoint,
      outcome: input.outcome,
      details: input.details ?? {},
    },
    metadata: {
      manifest: "docs/action-contract-manifest.json",
      copyingRule: actionContract.cleanRoom.copyingRule,
      endorsementBoundary: actionContract.cleanRoom.endorsementBoundary,
    },
  });
}

export function emitActionContractReceipt(
  input: ActionContractReceiptInput,
  options: EmitReceiptOptions = {},
): OperationalReceipt {
  return emitReceipt(createActionContractEnvelope(input), {
    ...options,
    eventType: "A11OY_OPERATION",
    policy: {
      vertical: actionContract.intent.vertical,
      regime: actionContract.intent.regime,
      ...options.policy,
    },
  });
}
