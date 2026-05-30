import {
  createToolEnvelope,
  emitReceipt,
  type EmitReceiptOptions,
  type OperationalReceipt,
  type ToolEnvelope,
} from "../../../receipt-substrate/src/index.ts";

export interface FormulaGateDecisionLike {
  readonly allow: boolean;
  readonly rationale: string;
  readonly formula: string;
  readonly leanTheorem: string;
  readonly leanFile: string;
  readonly leanCommitSha: string;
  readonly lambdaScore: number;
}

export interface FormulaGateReceiptOptions extends Omit<EmitReceiptOptions, "eventType"> {
  readonly actorId: string;
  readonly invocationId?: string;
  readonly vertical?: string;
  readonly regime?: string;
  readonly lambdaAxes?: readonly string[];
  readonly metadata?: Record<string, unknown>;
}

export function createFormulaGateEnvelope(
  decision: FormulaGateDecisionLike,
  options: FormulaGateReceiptOptions,
): ToolEnvelope {
  return createToolEnvelope({
    protocol: "a11oy",
    actor_id: options.actorId,
    tool_name: `policy_gate.${decision.formula}`,
    invocation_id: options.invocationId,
    lambda_axes: options.lambdaAxes ?? ["Λ6", "Λ7"],
    payload: {
      allow: decision.allow,
      formula: decision.formula,
      leanTheorem: decision.leanTheorem,
      leanFile: decision.leanFile,
      leanCommitSha: decision.leanCommitSha,
      lambdaScore: decision.lambdaScore,
      rationale: decision.rationale,
    },
    metadata: {
      source: "packages/policy/src/gates",
      vertical: options.vertical,
      regime: options.regime,
      ...options.metadata,
    },
  });
}

export function emitFormulaGateReceipt(
  decision: FormulaGateDecisionLike,
  options: FormulaGateReceiptOptions,
): OperationalReceipt {
  const envelope = createFormulaGateEnvelope(decision, options);
  return emitReceipt(envelope, {
    ...options,
    eventType: "A11OY_OPERATION",
    policy: {
      algorithm: options.policy?.algorithm ?? "SHA3-256",
      chaining: options.policy?.chaining ?? "hash_chain",
      quorum: options.policy?.quorum ?? "1-of-1",
      nodes: options.policy?.nodes ?? [options.actorId],
      vertical: options.vertical,
      regime: options.regime,
    },
  });
}
