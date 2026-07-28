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

export const TWO_WITNESS_LIVE_ADAPTERS_ENABLED = false as const;

export type ResearchEvidenceLabel =
  | "CORROBORATED"
  | "DIVERGENT"
  | "SINGLE_PROVIDER"
  | "INSUFFICIENT"
  | "UNAVAILABLE";

export type ResearchProvider = "openai" | "perplexity";
export type ResearchProviderStatus = "SUCCESS" | "UNAVAILABLE" | "ERROR";

export interface ResearchUsageInput {
  readonly input_tokens?: number;
  readonly output_tokens?: number;
  readonly total_tokens?: number;
  readonly reasoning_tokens?: number;
  readonly cached_tokens?: number;
  readonly search_queries?: number;
}

export interface OpenAIResearchSourceInput {
  readonly url: string;
  readonly title?: string;
  readonly published_at?: string;
  readonly last_updated_at?: string;
}

export interface PerplexityResearchResultInput {
  readonly url: string;
  readonly title?: string;
  readonly date?: string;
  readonly last_updated?: string;
}

export interface OpenAIWebSearchResultInput {
  readonly provider: "openai";
  readonly status: ResearchProviderStatus;
  readonly query_sha256: string;
  readonly policy_sha256: string;
  readonly response_id?: string;
  readonly model?: string;
  readonly http_status?: number;
  readonly latency_ms?: number;
  readonly usage?: ResearchUsageInput;
  readonly cost_usd?: number;
  readonly sources?: readonly OpenAIResearchSourceInput[];
}

export interface PerplexitySearchResultInput {
  readonly provider: "perplexity";
  readonly status: ResearchProviderStatus;
  readonly query_sha256: string;
  readonly policy_sha256: string;
  readonly response_id?: string;
  readonly model?: string;
  readonly http_status?: number;
  readonly latency_ms?: number;
  readonly usage?: ResearchUsageInput;
  readonly cost_usd?: number;
  readonly results?: readonly PerplexityResearchResultInput[];
}

export interface NormalizedResearchSource {
  readonly url: string;
  readonly domain: string;
  readonly title_sha256?: string;
  readonly published_at?: string;
  readonly last_updated_at?: string;
}

export interface NormalizedResearchUsage {
  readonly input_tokens?: number;
  readonly output_tokens?: number;
  readonly total_tokens?: number;
  readonly reasoning_tokens?: number;
  readonly cached_tokens?: number;
  readonly search_queries?: number;
}

export interface NormalizedResearchProviderEvidence {
  readonly schema_version: "a11oy.research_provider_evidence/v0";
  readonly provider: ResearchProvider;
  readonly api_surface: "openai.responses.web_search" | "perplexity.search";
  readonly tool: "web_search" | "search";
  readonly status: ResearchProviderStatus;
  readonly query_sha256: string;
  readonly policy_sha256: string;
  readonly response_id?: string;
  readonly model?: string;
  readonly http_status?: number;
  readonly caller_observed_latency_ms?: number;
  readonly usage?: NormalizedResearchUsage;
  readonly provider_reported_cost_usd?: number;
  readonly sources: readonly NormalizedResearchSource[];
  readonly source_count: number;
  readonly source_list_sha256: string;
}

export interface ResearchEvidenceComparison {
  readonly schema_version: "a11oy.research_evidence_comparison/v0";
  readonly label: ResearchEvidenceLabel;
  readonly query_sha256: string;
  readonly policy_sha256: string;
  readonly providers: readonly NormalizedResearchProviderEvidence[];
  readonly successful_provider_count: number;
  readonly evidence_provider_count: number;
  readonly source_union_count: number;
  readonly source_url_overlap_count: number;
  readonly source_domain_overlap_count: number;
  readonly source_url_jaccard: number;
  readonly integrity_valid: boolean;
  readonly integrity_errors: readonly string[];
  readonly action_authorized: false;
}

export interface TwoWitnessResearchReceiptOptions extends EmitReceiptOptions {
  readonly actor_id: string;
  readonly invocation_id?: string;
}

const SHA256_PATTERN = /^[a-f0-9]{64}$/;
const SENSITIVE_SOURCE_QUERY_KEYS = new Set([
  "access_token",
  "api_key",
  "apikey",
  "auth",
  "authorization",
  "credential",
  "key",
  "password",
  "secret",
  "signature",
  "sig",
  "token",
]);
const DIGESTED_SOURCE_QUERY_KEYS = new Set(["code", "q", "snippet"]);
const ZONED_RFC3339_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})$/;
const SENSITIVE_SOURCE_QUERY_PREFIXES = ["x-amz-", "x-goog-", "x-oss-"];
const TRACKING_SOURCE_QUERY_PREFIXES = ["utm_"];
const TRACKING_SOURCE_QUERY_KEYS = new Set(["fbclid", "gclid", "mc_cid", "mc_eid"]);
const NORMALIZED_PROVIDER_KEYS = new Set([
  "schema_version",
  "provider",
  "api_surface",
  "tool",
  "status",
  "query_sha256",
  "policy_sha256",
  "response_id",
  "model",
  "http_status",
  "caller_observed_latency_ms",
  "usage",
  "provider_reported_cost_usd",
  "sources",
  "source_count",
  "source_list_sha256",
]);
const NORMALIZED_SOURCE_KEYS = new Set([
  "url",
  "domain",
  "title_sha256",
  "published_at",
  "last_updated_at",
]);
const NORMALIZED_USAGE_KEYS = new Set([
  "input_tokens",
  "output_tokens",
  "total_tokens",
  "reasoning_tokens",
  "cached_tokens",
  "search_queries",
]);

function cleanOptionalText(value: unknown, maxLength = 256): string | undefined {
  if (typeof value !== "string") return undefined;
  const cleaned = value.normalize("NFC").trim();
  if (!cleaned || cleaned.length > maxLength || /[\r\n]/.test(cleaned)) return undefined;
  return cleaned;
}

function cleanSha256(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function cleanStatus(value: unknown): ResearchProviderStatus {
  if (value === "SUCCESS" || value === "UNAVAILABLE" || value === "ERROR") return value;
  return "ERROR";
}

function cleanNonNegativeNumber(value: unknown): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return undefined;
  return value;
}

function cleanNonNegativeInteger(value: unknown): number | undefined {
  const cleaned = cleanNonNegativeNumber(value);
  return cleaned !== undefined && Number.isInteger(cleaned) ? cleaned : undefined;
}

function cleanHttpStatus(value: unknown): number | undefined {
  const cleaned = cleanNonNegativeInteger(value);
  return cleaned !== undefined && cleaned >= 100 && cleaned <= 599 ? cleaned : undefined;
}

function cleanDate(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const cleaned = value.trim();
  const match = ZONED_RFC3339_PATTERN.exec(cleaned);
  if (!match) return undefined;
  const [, yearText, monthText, dayText, hourText, minuteText, secondText, fraction = "", zone] =
    match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const hour = Number(hourText);
  const minute = Number(minuteText);
  const second = Number(secondText);
  const millisecond = Number((fraction + "000").slice(0, 3));
  if (zone === "-00:00") return undefined;
  if (zone !== "Z") {
    const offsetHour = Number(zone.slice(1, 3));
    const offsetMinute = Number(zone.slice(4, 6));
    if (offsetHour > 23 || offsetMinute > 59) return undefined;
  }
  const calendar = new Date(0);
  calendar.setUTCFullYear(year, month - 1, day);
  calendar.setUTCHours(hour, minute, second, millisecond);
  if (
    calendar.getUTCFullYear() !== year ||
    calendar.getUTCMonth() !== month - 1 ||
    calendar.getUTCDate() !== day ||
    calendar.getUTCHours() !== hour ||
    calendar.getUTCMinutes() !== minute ||
    calendar.getUTCSeconds() !== second
  ) {
    return undefined;
  }
  const date = new Date(cleaned);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

function cleanSourceUrl(raw: unknown): string | undefined {
  if (typeof raw !== "string") return undefined;
  try {
    const url = new URL(raw.trim());
    if ((url.protocol !== "http:" && url.protocol !== "https:") || url.username || url.password) {
      return undefined;
    }

    url.hash = "";
    for (const key of [...url.searchParams.keys()]) {
      const lower = key.toLowerCase();
      if (DIGESTED_SOURCE_QUERY_KEYS.has(lower)) {
        const digests = url.searchParams
          .getAll(key)
          .map((value) => (
            /^sha256:[a-f0-9]{64}$/.test(value)
              ? value.slice("sha256:".length)
              : hashHex(value, "SHA-256")
          ))
          .sort();
        url.searchParams.delete(key);
        for (const digest of digests) {
          url.searchParams.append(key, `sha256:${digest}`);
        }
        continue;
      }
      if (
        SENSITIVE_SOURCE_QUERY_KEYS.has(lower)
        || SENSITIVE_SOURCE_QUERY_PREFIXES.some((prefix) => lower.startsWith(prefix))
        || TRACKING_SOURCE_QUERY_KEYS.has(lower)
        || TRACKING_SOURCE_QUERY_PREFIXES.some((prefix) => lower.startsWith(prefix))
      ) {
        url.searchParams.delete(key);
      }
    }
    url.searchParams.sort();
    url.hostname = url.hostname.toLowerCase();
    if ((url.protocol === "http:" && url.port === "80") || (url.protocol === "https:" && url.port === "443")) {
      url.port = "";
    }
    if (url.pathname.length > 1 && url.pathname.endsWith("/")) {
      url.pathname = url.pathname.replace(/\/+$/, "");
    }
    return url.toString();
  } catch {
    return undefined;
  }
}

function normalizeResearchSources(
  inputs: readonly {
    readonly url: string;
    readonly title?: string;
    readonly published_at?: string;
    readonly last_updated_at?: string;
  }[],
): readonly NormalizedResearchSource[] {
  const byUrl = new Map<string, NormalizedResearchSource>();
  for (const input of inputs) {
    const url = cleanSourceUrl(input.url);
    if (!url) continue;
    const title = cleanOptionalText(input.title, 2_000);
    const domain = new URL(url).hostname;
    const source: NormalizedResearchSource = {
      url,
      domain,
      ...(title ? { title_sha256: hashHex(title, "SHA-256") } : {}),
      ...(cleanDate(input.published_at) ? { published_at: cleanDate(input.published_at) } : {}),
      ...(cleanDate(input.last_updated_at) ? { last_updated_at: cleanDate(input.last_updated_at) } : {}),
    };
    byUrl.set(url, source);
  }
  return [...byUrl.values()].sort((left, right) => left.url.localeCompare(right.url));
}

function normalizeResearchUsage(input: ResearchUsageInput | undefined): NormalizedResearchUsage | undefined {
  if (!input) return undefined;
  const usage: NormalizedResearchUsage = {
    ...(cleanNonNegativeInteger(input.input_tokens) !== undefined
      ? { input_tokens: cleanNonNegativeInteger(input.input_tokens) }
      : {}),
    ...(cleanNonNegativeInteger(input.output_tokens) !== undefined
      ? { output_tokens: cleanNonNegativeInteger(input.output_tokens) }
      : {}),
    ...(cleanNonNegativeInteger(input.total_tokens) !== undefined
      ? { total_tokens: cleanNonNegativeInteger(input.total_tokens) }
      : {}),
    ...(cleanNonNegativeInteger(input.reasoning_tokens) !== undefined
      ? { reasoning_tokens: cleanNonNegativeInteger(input.reasoning_tokens) }
      : {}),
    ...(cleanNonNegativeInteger(input.cached_tokens) !== undefined
      ? { cached_tokens: cleanNonNegativeInteger(input.cached_tokens) }
      : {}),
    ...(cleanNonNegativeInteger(input.search_queries) !== undefined
      ? { search_queries: cleanNonNegativeInteger(input.search_queries) }
      : {}),
  };
  return Object.keys(usage).length > 0 ? usage : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function unexpectedKeys(
  value: Record<string, unknown>,
  allowed: ReadonlySet<string>,
): readonly string[] {
  return Object.keys(value).filter((key) => !allowed.has(key)).sort();
}

function projectNormalizedResearchSource(
  input: unknown,
): NormalizedResearchSource {
  const record = isRecord(input) ? input : {};
  const url = cleanSourceUrl(record.url) ?? "";
  const domain = cleanOptionalText(record.domain, 253)?.toLowerCase() ?? "";
  const titleSha256 = record.title_sha256 === undefined
    ? undefined
    : cleanSha256(record.title_sha256);
  const publishedAt = cleanDate(record.published_at);
  const lastUpdatedAt = cleanDate(record.last_updated_at);
  return {
    url,
    domain,
    ...(titleSha256 !== undefined ? { title_sha256: titleSha256 } : {}),
    ...(publishedAt !== undefined ? { published_at: publishedAt } : {}),
    ...(lastUpdatedAt !== undefined ? { last_updated_at: lastUpdatedAt } : {}),
  };
}

function projectNormalizedResearchUsage(
  input: unknown,
): NormalizedResearchUsage | undefined {
  if (!isRecord(input)) return undefined;
  const projected: NormalizedResearchUsage = {
    ...(cleanNonNegativeInteger(input.input_tokens) !== undefined
      ? { input_tokens: cleanNonNegativeInteger(input.input_tokens) }
      : {}),
    ...(cleanNonNegativeInteger(input.output_tokens) !== undefined
      ? { output_tokens: cleanNonNegativeInteger(input.output_tokens) }
      : {}),
    ...(cleanNonNegativeInteger(input.total_tokens) !== undefined
      ? { total_tokens: cleanNonNegativeInteger(input.total_tokens) }
      : {}),
    ...(cleanNonNegativeInteger(input.reasoning_tokens) !== undefined
      ? { reasoning_tokens: cleanNonNegativeInteger(input.reasoning_tokens) }
      : {}),
    ...(cleanNonNegativeInteger(input.cached_tokens) !== undefined
      ? { cached_tokens: cleanNonNegativeInteger(input.cached_tokens) }
      : {}),
    ...(cleanNonNegativeInteger(input.search_queries) !== undefined
      ? { search_queries: cleanNonNegativeInteger(input.search_queries) }
      : {}),
  };
  return Object.keys(projected).length > 0 ? projected : undefined;
}

function projectNormalizedProviderEvidence(
  input: unknown,
): NormalizedResearchProviderEvidence {
  const record = isRecord(input) ? input : {};
  const provider = record.provider === "openai" || record.provider === "perplexity"
    ? record.provider
    : "invalid" as ResearchProvider;
  const apiSurface = record.api_surface === "openai.responses.web_search"
    || record.api_surface === "perplexity.search"
    ? record.api_surface
    : "invalid" as NormalizedResearchProviderEvidence["api_surface"];
  const tool = record.tool === "web_search" || record.tool === "search"
    ? record.tool
    : "invalid" as NormalizedResearchProviderEvidence["tool"];
  const responseId = cleanOptionalText(record.response_id);
  const model = cleanOptionalText(record.model);
  const httpStatus = cleanHttpStatus(record.http_status);
  const latencyMs = cleanNonNegativeNumber(record.caller_observed_latency_ms);
  const usage = projectNormalizedResearchUsage(record.usage);
  const costUsd = cleanNonNegativeNumber(record.provider_reported_cost_usd);
  const suppliedSources = Array.isArray(record.sources) ? record.sources : [];
  const sources = suppliedSources.map(projectNormalizedResearchSource);
  return {
    schema_version: record.schema_version === "a11oy.research_provider_evidence/v0"
      ? record.schema_version
      : "invalid" as NormalizedResearchProviderEvidence["schema_version"],
    provider,
    api_surface: apiSurface,
    tool,
    status: cleanStatus(record.status),
    query_sha256: cleanSha256(record.query_sha256),
    policy_sha256: cleanSha256(record.policy_sha256),
    ...(responseId ? { response_id: responseId } : {}),
    ...(model ? { model } : {}),
    ...(httpStatus !== undefined ? { http_status: httpStatus } : {}),
    ...(latencyMs !== undefined ? { caller_observed_latency_ms: latencyMs } : {}),
    ...(usage ? { usage } : {}),
    ...(costUsd !== undefined ? { provider_reported_cost_usd: costUsd } : {}),
    sources,
    source_count: cleanNonNegativeInteger(record.source_count) ?? -1,
    source_list_sha256: cleanSha256(record.source_list_sha256),
  };
}

function structuralResearchEvidenceErrors(
  providers: readonly unknown[],
): readonly string[] {
  const errors: string[] = [];
  for (const [providerIndex, input] of providers.entries()) {
    if (!isRecord(input)) {
      errors.push(`provider ${providerIndex}: expected an object`);
      continue;
    }
    const providerLabel = input.provider === "openai" || input.provider === "perplexity"
      ? input.provider
      : `provider ${providerIndex}`;
    for (const key of unexpectedKeys(input, NORMALIZED_PROVIDER_KEYS)) {
      errors.push(`${providerLabel}: unexpected provider field ${key}`);
    }
    if (input.usage !== undefined) {
      if (!isRecord(input.usage)) {
        errors.push(`${providerLabel}: usage must be an object`);
      } else {
        for (const key of unexpectedKeys(input.usage, NORMALIZED_USAGE_KEYS)) {
          errors.push(`${providerLabel}: unexpected usage field ${key}`);
        }
      }
    }
    if (!Array.isArray(input.sources)) {
      errors.push(`${providerLabel}: sources must be an array`);
      continue;
    }
    for (const [sourceIndex, source] of input.sources.entries()) {
      if (!isRecord(source)) {
        errors.push(`${providerLabel}: source ${sourceIndex} must be an object`);
        continue;
      }
      for (const key of unexpectedKeys(source, NORMALIZED_SOURCE_KEYS)) {
        errors.push(`${providerLabel}: source ${sourceIndex} unexpected field ${key}`);
      }
    }
  }
  return errors;
}

function normalizeProviderEvidence(input: {
  readonly provider: ResearchProvider;
  readonly api_surface: NormalizedResearchProviderEvidence["api_surface"];
  readonly tool: NormalizedResearchProviderEvidence["tool"];
  readonly status: ResearchProviderStatus;
  readonly query_sha256: string;
  readonly policy_sha256: string;
  readonly response_id?: string;
  readonly model?: string;
  readonly http_status?: number;
  readonly latency_ms?: number;
  readonly usage?: ResearchUsageInput;
  readonly cost_usd?: number;
  readonly sources: readonly NormalizedResearchSource[];
}): NormalizedResearchProviderEvidence {
  const responseId = cleanOptionalText(input.response_id);
  const model = cleanOptionalText(input.model);
  const httpStatus = cleanHttpStatus(input.http_status);
  const latencyMs = cleanNonNegativeNumber(input.latency_ms);
  const usage = normalizeResearchUsage(input.usage);
  const costUsd = cleanNonNegativeNumber(input.cost_usd);
  return {
    schema_version: "a11oy.research_provider_evidence/v0",
    provider: input.provider,
    api_surface: input.api_surface,
    tool: input.tool,
    status: cleanStatus(input.status),
    query_sha256: cleanSha256(input.query_sha256),
    policy_sha256: cleanSha256(input.policy_sha256),
    ...(responseId ? { response_id: responseId } : {}),
    ...(model ? { model } : {}),
    ...(httpStatus !== undefined ? { http_status: httpStatus } : {}),
    ...(latencyMs !== undefined ? { caller_observed_latency_ms: latencyMs } : {}),
    ...(usage ? { usage } : {}),
    ...(costUsd !== undefined ? { provider_reported_cost_usd: costUsd } : {}),
    sources: input.sources,
    source_count: input.sources.length,
    source_list_sha256: hashHex(input.sources, "SHA-256"),
  };
}

export function normalizeOpenAIWebSearchResult(
  input: OpenAIWebSearchResultInput,
): NormalizedResearchProviderEvidence {
  return normalizeProviderEvidence({
    provider: "openai",
    api_surface: "openai.responses.web_search",
    tool: "web_search",
    status: input.status,
    query_sha256: input.query_sha256,
    policy_sha256: input.policy_sha256,
    response_id: input.response_id,
    model: input.model,
    http_status: input.http_status,
    latency_ms: input.latency_ms,
    usage: input.usage,
    cost_usd: input.cost_usd,
    sources: normalizeResearchSources(input.sources ?? []),
  });
}

export function normalizePerplexitySearchResult(
  input: PerplexitySearchResultInput,
): NormalizedResearchProviderEvidence {
  return normalizeProviderEvidence({
    provider: "perplexity",
    api_surface: "perplexity.search",
    tool: "search",
    status: input.status,
    query_sha256: input.query_sha256,
    policy_sha256: input.policy_sha256,
    response_id: input.response_id,
    model: input.model,
    http_status: input.http_status,
    latency_ms: input.latency_ms,
    usage: input.usage,
    cost_usd: input.cost_usd,
    sources: normalizeResearchSources(
      (input.results ?? []).map((result) => ({
        url: result.url,
        title: result.title,
        published_at: result.date,
        last_updated_at: result.last_updated,
      })),
    ),
  });
}

function intersectionSize(left: ReadonlySet<string>, right: ReadonlySet<string>): number {
  let count = 0;
  for (const value of left) {
    if (right.has(value)) count += 1;
  }
  return count;
}

export function compareResearchEvidence(input: {
  readonly query_sha256: string;
  readonly policy_sha256: string;
  readonly providers: readonly NormalizedResearchProviderEvidence[];
}): ResearchEvidenceComparison {
  const querySha256 = cleanSha256(input.query_sha256);
  const policySha256 = cleanSha256(input.policy_sha256);
  const suppliedProviders = Array.isArray(input.providers) ? input.providers : [];
  const errors = Array.isArray(input.providers)
    ? [...structuralResearchEvidenceErrors(suppliedProviders)]
    : ["providers must be an array"];
  const providers = suppliedProviders
    .map(projectNormalizedProviderEvidence)
    .sort((left, right) => left.provider.localeCompare(right.provider));

  if (!SHA256_PATTERN.test(querySha256)) errors.push("expected query_sha256 is not a SHA-256 digest");
  if (!SHA256_PATTERN.test(policySha256)) errors.push("expected policy_sha256 is not a SHA-256 digest");

  const expectedProviders = new Set<ResearchProvider>(["openai", "perplexity"]);
  const seenProviders = new Set<ResearchProvider>();
  for (const provider of providers) {
    if (seenProviders.has(provider.provider)) errors.push(`duplicate provider: ${provider.provider}`);
    seenProviders.add(provider.provider);
    if (provider.schema_version !== "a11oy.research_provider_evidence/v0") {
      errors.push(`${provider.provider}: schema_version mismatch`);
    }
    const expectedSurface = provider.provider === "openai"
      ? "openai.responses.web_search"
      : "perplexity.search";
    const expectedTool = provider.provider === "openai" ? "web_search" : "search";
    if (provider.api_surface !== expectedSurface) {
      errors.push(`${provider.provider}: api_surface mismatch`);
    }
    if (provider.tool !== expectedTool) errors.push(`${provider.provider}: tool mismatch`);
    if (!SHA256_PATTERN.test(provider.query_sha256)) {
      errors.push(`${provider.provider}: query_sha256 is not a SHA-256 digest`);
    } else if (provider.query_sha256 !== querySha256) {
      errors.push(`${provider.provider}: query_sha256 mismatch`);
    }
    if (!SHA256_PATTERN.test(provider.policy_sha256)) {
      errors.push(`${provider.provider}: policy_sha256 is not a SHA-256 digest`);
    } else if (provider.policy_sha256 !== policySha256) {
      errors.push(`${provider.provider}: policy_sha256 mismatch`);
    }
    if (provider.source_count !== provider.sources.length) {
      errors.push(`${provider.provider}: source_count mismatch`);
    }
    if (provider.source_list_sha256 !== hashHex(provider.sources, "SHA-256")) {
      errors.push(`${provider.provider}: source_list_sha256 mismatch`);
    }
    if (provider.status !== "SUCCESS" && provider.sources.length > 0) {
      errors.push(`${provider.provider}: non-success status carries evidence`);
    }
    if (
      provider.status === "SUCCESS"
      && provider.http_status !== undefined
      && (provider.http_status < 200 || provider.http_status >= 300)
    ) {
      errors.push(`${provider.provider}: success status conflicts with http_status`);
    }
    for (const [index, source] of provider.sources.entries()) {
      if (cleanSourceUrl(source.url) !== source.url) {
        errors.push(`${provider.provider}: source ${index} URL is not canonical`);
      }
      try {
        if (new URL(source.url).hostname !== source.domain) {
          errors.push(`${provider.provider}: source ${index} domain mismatch`);
        }
      } catch {
        errors.push(`${provider.provider}: source ${index} URL is invalid`);
      }
      if (source.title_sha256 !== undefined && !SHA256_PATTERN.test(source.title_sha256)) {
        errors.push(`${provider.provider}: source ${index} title_sha256 is invalid`);
      }
    }
  }
  for (const provider of expectedProviders) {
    if (!seenProviders.has(provider)) errors.push(`missing provider: ${provider}`);
  }

  const openai = providers.find((provider) => provider.provider === "openai");
  const perplexity = providers.find((provider) => provider.provider === "perplexity");
  const openaiUrls = new Set(openai?.sources.map((source) => source.url) ?? []);
  const perplexityUrls = new Set(perplexity?.sources.map((source) => source.url) ?? []);
  const openaiDomains = new Set(openai?.sources.map((source) => source.domain) ?? []);
  const perplexityDomains = new Set(perplexity?.sources.map((source) => source.domain) ?? []);
  const sourceUrlOverlapCount = intersectionSize(openaiUrls, perplexityUrls);
  const sourceDomainOverlapCount = intersectionSize(openaiDomains, perplexityDomains);
  const sourceUnion = new Set([...openaiUrls, ...perplexityUrls]);
  const successfulProviders = providers.filter((provider) => provider.status === "SUCCESS");
  const evidenceProviders = successfulProviders.filter((provider) => provider.source_count > 0);

  let label: ResearchEvidenceLabel;
  if (errors.length > 0) {
    label = "INSUFFICIENT";
  } else if (successfulProviders.length === 0) {
    label = "UNAVAILABLE";
  } else if (evidenceProviders.length === 0 || evidenceProviders.length !== successfulProviders.length) {
    label = "INSUFFICIENT";
  } else if (successfulProviders.length === 1) {
    label = "SINGLE_PROVIDER";
  } else if (sourceUrlOverlapCount > 0) {
    label = "CORROBORATED";
  } else {
    label = "DIVERGENT";
  }

  return {
    schema_version: "a11oy.research_evidence_comparison/v0",
    label,
    query_sha256: querySha256,
    policy_sha256: policySha256,
    providers,
    successful_provider_count: successfulProviders.length,
    evidence_provider_count: evidenceProviders.length,
    source_union_count: sourceUnion.size,
    source_url_overlap_count: sourceUrlOverlapCount,
    source_domain_overlap_count: sourceDomainOverlapCount,
    source_url_jaccard: sourceUnion.size === 0
      ? 0
      : Number((sourceUrlOverlapCount / sourceUnion.size).toFixed(6)),
    integrity_valid: errors.length === 0,
    integrity_errors: errors.sort(),
    action_authorized: false,
  };
}

export function emitTwoWitnessResearchReceipt(
  comparison: ResearchEvidenceComparison,
  options: TwoWitnessResearchReceiptOptions,
): OperationalReceipt {
  const verifiedComparison = compareResearchEvidence({
    query_sha256: comparison.query_sha256,
    policy_sha256: comparison.policy_sha256,
    providers: comparison.providers,
  });
  if (canonicalJson(verifiedComparison) !== canonicalJson(comparison)) {
    throw new Error("research evidence comparison verification failed");
  }
  const payload = {
    schema_version: "a11oy.two_witness_research_receipt/v0",
    live_adapters_enabled: TWO_WITNESS_LIVE_ADAPTERS_ENABLED,
    evidence_class: "MODELED",
    signature_state: "UNSIGNED_LOCAL",
    external_attestation_state: "EXTERNAL_ATTESTATION_FALSE",
    external_attestation: false,
    action_authorization_state: "ACTION_AUTHORIZED_FALSE",
    action_authorized: false,
    query_sha256: comparison.query_sha256,
    policy_sha256: comparison.policy_sha256,
    label: comparison.label,
    integrity_valid: comparison.integrity_valid,
    integrity_errors: comparison.integrity_errors,
    successful_provider_count: comparison.successful_provider_count,
    evidence_provider_count: comparison.evidence_provider_count,
    source_union_count: comparison.source_union_count,
    source_url_overlap_count: comparison.source_url_overlap_count,
    source_domain_overlap_count: comparison.source_domain_overlap_count,
    source_url_jaccard: comparison.source_url_jaccard,
    providers: comparison.providers,
  };
  const envelope = createToolEnvelope({
    protocol: "a11oy",
    actor_id: options.actor_id,
    tool_name: "two_witness_research_compare_v0",
    tool_version: "0.1.0",
    invocation_id: options.invocation_id,
    lambda_axes: ["provenance", "restraint"],
    payload,
    metadata: {
      network_access: "DISABLED",
      provider_credentials: "NOT_ACCEPTED",
      live_adapter_feature_flag: "OFF",
    },
  });
  return emitReceipt(envelope, {
    previousReceipt: options.previousReceipt,
    policy: options.policy,
    quorumSignatures: options.quorumSignatures,
    timestamp: options.timestamp,
    sequence: options.sequence,
    eventType: "A11OY_OPERATION",
  });
}
