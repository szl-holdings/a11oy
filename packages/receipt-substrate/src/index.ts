import * as crypto from "node:crypto";
import * as fs from "node:fs";

export type HashAlgorithm = "SHA-256" | "SHA3-256" | "SHA3-512";
export type ReceiptProtocol = "mcp" | "cursor" | "claude" | "a11oy";
export type ReceiptEventType =
  | "MCP_TOOL_CALL"
  | "CURSOR_AGENT_EDIT"
  | "CLAUDE_SUBAGENT_CALL"
  | "A11OY_OPERATION"
  | "AUTONOMOUS_LEARNING_PROPOSAL"
  | "AUTONOMOUS_LEARNING_EVALUATION"
  | "HUMAN_PROMOTION";

export interface ToolEnvelope {
  readonly protocol: ReceiptProtocol;
  readonly actor_id: string;
  readonly tool_name: string;
  readonly tool_version?: string;
  readonly invocation_id: string;
  readonly lambda_axes: readonly string[];
  readonly payload: unknown;
  readonly metadata?: Record<string, unknown>;
}

export interface ReceiptPolicy {
  readonly algorithm: HashAlgorithm;
  readonly chaining: "hash_chain" | "merkle_dag";
  readonly quorum: string;
  readonly nodes: readonly string[];
  readonly vertical?: string;
  readonly regime?: string;
}

export interface QecWitness {
  readonly payload_byte: number;
  readonly shor_repetition_count: 9;
  readonly shor_majority_payload: number;
  readonly css_x_parity: number;
  readonly css_z_parity: number;
  readonly css_consistent: boolean;
}

export interface OperationalReceipt {
  readonly schema_version: "1.0.0";
  readonly receipt_id: string;
  readonly event_type: ReceiptEventType;
  readonly timestamp_iso8601: string;
  readonly timestamp_tai64n: string;
  readonly sequence: number;
  readonly actor_id: string;
  readonly tool_name: string;
  readonly protocol: ReceiptProtocol;
  readonly payload_hash: string;
  readonly prev_receipt_hash: string | null;
  readonly quorum_signatures: readonly string[];
  readonly policy?: Pick<ReceiptPolicy, "algorithm" | "chaining" | "quorum" | "nodes" | "vertical" | "regime">;
  readonly qec_witness: QecWitness;
  readonly envelope: ToolEnvelope;
  readonly merkle_root: string;
}

export interface EmitReceiptOptions {
  readonly previousReceipt?: OperationalReceipt | null;
  readonly policy?: Partial<ReceiptPolicy>;
  readonly quorumSignatures?: readonly string[];
  readonly timestamp?: Date;
  readonly sequence?: number;
  readonly eventType?: ReceiptEventType;
}

export interface VerifyResult {
  readonly valid: boolean;
  readonly errors: readonly string[];
}

const DEFAULT_POLICY: ReceiptPolicy = {
  algorithm: "SHA3-256",
  chaining: "hash_chain",
  quorum: "1-of-1",
  nodes: ["local-operator"],
};

function normaliseStrings(value: unknown): unknown {
  if (typeof value === "string") return value.normalize("NFC");
  if (Array.isArray(value)) return value.map(normaliseStrings);
  if (value && typeof value === "object") {
    const result: Record<string, unknown> = {};
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      result[key.normalize("NFC")] = normaliseStrings(child);
    }
    return result;
  }
  return value;
}

export function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalValue(normaliseStrings(value)));
}

function canonicalValue(value: unknown): unknown {
  if (value === null) return null;
  if (typeof value === "string" || typeof value === "boolean") return value;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("canonicalJson: non-finite numbers are not supported");
    return value;
  }
  if (Array.isArray(value)) return value.map(canonicalValue);
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const sorted: Record<string, unknown> = {};
    for (const key of Object.keys(obj).sort()) {
      const child = obj[key];
      if (typeof child === "undefined") {
        continue;
      }
      if (typeof child === "function" || typeof child === "symbol") {
        throw new Error(`canonicalJson: unsupported value at key '${key}'`);
      }
      sorted[key] = canonicalValue(child);
    }
    return sorted;
  }
  if (typeof value === "undefined" || typeof value === "function" || typeof value === "symbol") {
    throw new Error("canonicalJson: unsupported root value");
  }
  return value;
}

export function hashHex(value: unknown, algorithm: HashAlgorithm = "SHA3-256"): string {
  const nodeAlgorithm = algorithmToNode(algorithm);
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(typeof value === "string" ? value : canonicalJson(value), "utf8");
  return crypto.createHash(nodeAlgorithm).update(bytes).digest("hex");
}

function algorithmToNode(algorithm: HashAlgorithm): string {
  switch (algorithm) {
    case "SHA-256":
      return "sha256";
    case "SHA3-256":
      return crypto.getHashes().includes("sha3-256") ? "sha3-256" : "sha256";
    case "SHA3-512":
      return crypto.getHashes().includes("sha3-512") ? "sha3-512" : "sha512";
  }
}

export function parseQuorum(quorum: string): { required: number; total: number } {
  const match = /^(\d+)-of-(\d+)$/.exec(quorum);
  if (!match) throw new Error(`Invalid quorum '${quorum}'; expected N-of-M`);
  const required = Number(match[1]);
  const total = Number(match[2]);
  if (!Number.isInteger(required) || !Number.isInteger(total) || required < 1 || total < 1 || required > total) {
    throw new Error(`Invalid quorum '${quorum}'; required signers must be between 1 and total`);
  }
  return { required, total };
}

export function createToolEnvelope(input: {
  protocol?: ReceiptProtocol;
  actor_id: string;
  tool_name: string;
  tool_version?: string;
  invocation_id?: string;
  lambda_axes?: readonly string[];
  payload: unknown;
  metadata?: Record<string, unknown>;
}): ToolEnvelope {
  const invocationMaterial = {
    actor_id: input.actor_id,
    tool_name: input.tool_name,
    payload: input.payload,
    metadata: input.metadata ?? {},
  };
  return {
    protocol: input.protocol ?? "mcp",
    actor_id: input.actor_id.normalize("NFC"),
    tool_name: input.tool_name.normalize("NFC"),
    tool_version: input.tool_version?.normalize("NFC"),
    invocation_id: input.invocation_id?.normalize("NFC") ?? `inv-${hashHex(invocationMaterial).slice(0, 16)}`,
    lambda_axes: [...(input.lambda_axes ?? ["Λ7"])].map((axis) => axis.normalize("NFC")).sort(),
    payload: normaliseStrings(input.payload),
    metadata: input.metadata ? normaliseStrings(input.metadata) as Record<string, unknown> : undefined,
  };
}

export function tai64n(date: Date = new Date()): string {
  const unixSeconds = BigInt(Math.floor(date.getTime() / 1000));
  const nanos = BigInt(date.getMilliseconds()) * 1_000_000n;
  const taiSeconds = unixSeconds + 37n + 0x4000000000000000n;
  return `@${taiSeconds.toString(16).padStart(16, "0")}${nanos.toString(16).padStart(8, "0")}`;
}

export function qecWitness(payloadHash: string): QecWitness {
  const payloadByte = Number.parseInt(payloadHash.slice(0, 2), 16) & 0xff;
  const cssX = payloadByte;
  const cssZ = (payloadByte ^ 0xff) & 0xff;
  return {
    payload_byte: payloadByte,
    shor_repetition_count: 9,
    shor_majority_payload: payloadByte,
    css_x_parity: cssX,
    css_z_parity: cssZ,
    css_consistent: (cssX ^ cssZ) === 0xff,
  };
}

export function emitReceipt(envelope: ToolEnvelope, options: EmitReceiptOptions = {}): OperationalReceipt {
  const policy = { ...DEFAULT_POLICY, ...options.policy };
  parseQuorum(policy.quorum);

  const timestamp = options.timestamp ?? new Date();
  const sequence = options.sequence ?? ((options.previousReceipt?.sequence ?? -1) + 1);
  const payloadHash = hashHex(envelope, policy.algorithm);
  const prevReceiptHash = options.previousReceipt?.merkle_root ?? null;
  const signatures = options.quorumSignatures ?? policy.nodes.slice(0, parseQuorum(policy.quorum).required);

  const partial = {
    schema_version: "1.0.0" as const,
    event_type: options.eventType ?? eventTypeForProtocol(envelope.protocol),
    timestamp_iso8601: timestamp.toISOString(),
    timestamp_tai64n: tai64n(timestamp),
    sequence,
    actor_id: envelope.actor_id,
    tool_name: envelope.tool_name,
    protocol: envelope.protocol,
    payload_hash: payloadHash,
    prev_receipt_hash: prevReceiptHash,
    quorum_signatures: [...signatures].sort(),
    policy: {
      algorithm: policy.algorithm,
      chaining: policy.chaining,
      quorum: policy.quorum,
      nodes: [...policy.nodes].sort(),
      vertical: policy.vertical,
      regime: policy.regime,
    },
    qec_witness: qecWitness(payloadHash),
    envelope,
  };

  const merkleRoot = hashHex(partial, policy.algorithm);
  const receiptId = `or-${hashHex({ merkleRoot, payloadHash, sequence }, policy.algorithm).slice(0, 20)}`;
  return { receipt_id: receiptId, ...partial, merkle_root: merkleRoot };
}

function eventTypeForProtocol(protocol: ReceiptProtocol): ReceiptEventType {
  switch (protocol) {
    case "cursor":
      return "CURSOR_AGENT_EDIT";
    case "claude":
      return "CLAUDE_SUBAGENT_CALL";
    case "a11oy":
      return "A11OY_OPERATION";
    case "mcp":
      return "MCP_TOOL_CALL";
  }
}

export function appendReceipt(chain: readonly OperationalReceipt[], envelope: ToolEnvelope, options: Omit<EmitReceiptOptions, "previousReceipt"> = {}): OperationalReceipt[] {
  const previousReceipt = chain.length > 0 ? chain[chain.length - 1] : null;
  return [...chain, emitReceipt(envelope, { ...options, previousReceipt })];
}

export function verifyReceipt(receipt: OperationalReceipt): VerifyResult {
  const errors: string[] = [];
  const algorithm = receipt.policy?.algorithm ?? DEFAULT_POLICY.algorithm;
  const expectedPayloadHash = hashHex(receipt.envelope, algorithm);
  if (receipt.payload_hash !== expectedPayloadHash) {
    errors.push(`payload_hash mismatch for ${receipt.receipt_id}`);
  }

  const { merkle_root: _merkleRoot, receipt_id: _receiptId, ...partial } = receipt;
  const expectedMerkleRoot = hashHex(partial, algorithm);
  if (receipt.merkle_root !== expectedMerkleRoot) {
    errors.push(`merkle_root mismatch for ${receipt.receipt_id}`);
  }

  const expectedReceiptId = `or-${hashHex({
    merkleRoot: expectedMerkleRoot,
    payloadHash: expectedPayloadHash,
    sequence: receipt.sequence,
  }, algorithm).slice(0, 20)}`;
  if (receipt.receipt_id !== expectedReceiptId) {
    errors.push(`receipt_id mismatch for ${receipt.receipt_id}`);
  }

  if (!receipt.qec_witness.css_consistent || receipt.qec_witness.payload_byte !== receipt.qec_witness.shor_majority_payload) {
    errors.push(`qec witness mismatch for ${receipt.receipt_id}`);
  }

  return { valid: errors.length === 0, errors };
}

export function verifyChain(chain: readonly OperationalReceipt[], policyOverride?: Partial<ReceiptPolicy>): VerifyResult {
  const errors: string[] = [];
  const seen = new Set<string>();

  for (let i = 0; i < chain.length; i += 1) {
    const receipt = chain[i];
    const receiptResult = verifyReceipt(receipt);
    errors.push(...receiptResult.errors.map((error) => `position ${i}: ${error}`));

    if (seen.has(receipt.receipt_id)) {
      errors.push(`position ${i}: duplicate receipt_id ${receipt.receipt_id}`);
    }
    seen.add(receipt.receipt_id);

    const expectedPrev = i === 0 ? null : chain[i - 1].merkle_root;
    if (receipt.prev_receipt_hash !== expectedPrev) {
      errors.push(`position ${i}: prev_receipt_hash mismatch`);
    }

    if (!Number.isInteger(receipt.sequence) || receipt.sequence !== i) {
      errors.push(`position ${i}: sequence mismatch`);
    }

    if (i > 0 && receipt.timestamp_tai64n <= chain[i - 1].timestamp_tai64n) {
      errors.push(`position ${i}: timestamp regression`);
    }

    const policy = { ...DEFAULT_POLICY, ...receipt.policy, ...policyOverride };
    try {
      const quorum = parseQuorum(policy.quorum);
      const uniqueSignatures = new Set(receipt.quorum_signatures);
      const knownNodes = new Set(policy.nodes);
      if (policy.nodes.length < quorum.total) {
        errors.push(`position ${i}: quorum total exceeds known nodes`);
      }
      if (uniqueSignatures.size < quorum.required) {
        errors.push(`position ${i}: insufficient quorum signatures`);
      }
      for (const signer of uniqueSignatures) {
        if (knownNodes.size > 0 && !knownNodes.has(signer)) {
          errors.push(`position ${i}: unknown quorum signer ${signer}`);
        }
      }
    } catch (error) {
      errors.push(`position ${i}: ${(error as Error).message}`);
    }
  }

  return { valid: errors.length === 0, errors };
}

export function parseJsonlReceipts(jsonl: string): OperationalReceipt[] {
  return jsonl
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line) as OperationalReceipt);
}

export function receiptToJsonl(receipt: OperationalReceipt): string {
  return `${canonicalJson(receipt)}\n`;
}

export function readReceiptJsonl(path: string): OperationalReceipt[] {
  if (!fs.existsSync(path)) return [];
  return parseJsonlReceipts(fs.readFileSync(path, "utf8"));
}

export function appendReceiptJsonl(path: string, receipt: OperationalReceipt): void {
  fs.appendFileSync(path, receiptToJsonl(receipt), "utf8");
}
