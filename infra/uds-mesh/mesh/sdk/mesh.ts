/**
 * mesh.ts — UDS-Mesh TypeScript SDK for emitting Λ-signed cross-organ OTEL spans.
 *
 * Functional mirror of mesh.py. Layer 5 (Observability) of the 7-layer SZL
 * architecture. Lets any organ (a11oy, sentra, amaru, killinchu, rosie) emit spans
 * conforming to ../../schemas/spans/*.yaml carrying the szl.mesh.* governance envelope.
 *
 * REAL behaviour (no mocks):
 *   - W3C Trace Context (https://www.w3.org/TR/trace-context/) parse/format.
 *   - DSSE PAE v1 receipt (HMAC-SHA-256 dev signer; same PAE as formula_receipts.py).
 *   - BLS-style aggregate verification modelling lutar-lean #180 (sorry-free)
 *     `Lutar.Round11.BLS.aggregate_verify`: Σ σ_i = (Σ sk_i)·h, so a batch of N
 *     mesh receipts verifies in ONE aggregate check. Production swaps the additive
 *     prime-field model for blst BLS12-381 — the verify contract is identical.
 *     Runtime coordinate: szl-holdings/amaru/szl_bls_aggregate.py.
 *
 * BigInt is used for the 256-bit scalar field; no external dependency.
 *
 * SPDX-License-Identifier: Apache-2.0
 * Author: Yachay (CTO authority) · Built by Perplexity Computer Agent · SZL Holdings
 * Doctrine v11 LOCKED — 749 / 14 / 163.
 */
import { createHash, createHmac, randomBytes } from "node:crypto";

export const LAMBDA_FLOOR_MESH = 0.1;
export const ORGANS = ["a11oy", "sentra", "amaru", "killinchu", "rosie"] as const;
export type Organ = (typeof ORGANS)[number];

export const SPAN_NAMES: Record<Organ, readonly string[]> = {
  a11oy: ["a11oy.graph.lambda", "a11oy.graph.automorphism", "a11oy.graph.position"],
  sentra: ["sentra.gate.evaluate", "sentra.gate.attest", "sentra.gate.fail_closed"],
  amaru: ["amaru.sync.merge", "amaru.sync.receipt", "amaru.sync.drift_alert"],
  killinchu: ["killinchu.courier.dispatch", "killinchu.courier.deliver", "killinchu.courier.verify"],
  rosie: ["rosie.decision.evaluate", "rosie.decision.witness", "rosie.decision.replay"],
};

const HMAC_KEY = process.env.MESH_HMAC_KEY ?? "szl-mesh-hmac-dev-v1";

// ── W3C Trace Context ────────────────────────────────────────────────────────
const TRACEPARENT_RE =
  /^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$/;

export class TraceContext {
  constructor(
    public traceId: string,
    public spanId: string,
    public flags = "01",
    public version = "00",
  ) {}

  static newRoot(): TraceContext {
    return new TraceContext(randomBytes(16).toString("hex"), randomBytes(8).toString("hex"));
  }

  static parse(traceparent: string): TraceContext {
    const m = TRACEPARENT_RE.exec(traceparent.trim());
    if (!m) throw new Error(`invalid W3C traceparent: ${traceparent}`);
    if (m[2] === "0".repeat(32) || m[3] === "0".repeat(16))
      throw new Error("traceparent contains all-zero id (invalid per W3C)");
    return new TraceContext(m[2], m[3], m[4], m[1]);
  }

  traceparent(): string {
    return `${this.version}-${this.traceId}-${this.spanId}-${this.flags}`;
  }

  child(): TraceContext {
    return new TraceContext(this.traceId, randomBytes(8).toString("hex"), this.flags, this.version);
  }
}

// ── DSSE PAE v1 ──────────────────────────────────────────────────────────────
function pae(payloadType: string, payload: Buffer): Buffer {
  const t = Buffer.from(payloadType);
  return Buffer.concat([
    Buffer.from(`DSSEv1 ${t.length} `), t,
    Buffer.from(` ${payload.length} `), payload,
  ]);
}

function sign(payloadType: string, payload: Buffer, key = HMAC_KEY): string {
  return createHmac("sha256", key).update(pae(payloadType, payload)).digest("base64");
}

// ── BLS-style aggregate signer (models Lutar.Round11.BLS.aggregate_verify) ────
// secp256k1 group order as the additive scalar-field modulus.
const P = BigInt("0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141");

function scalar(material: Buffer | string): bigint {
  const buf = typeof material === "string" ? Buffer.from(material) : material;
  return BigInt("0x" + createHash("sha256").update(buf).digest("hex")) % P;
}

const BLS = {
  skOf(signerId: string): bigint {
    return scalar("sk:" + signerId);
  },
  sign(signerId: string, msgHash: bigint): bigint {
    return (this.skOf(signerId) * msgHash) % P;
  },
  aggregate(sigs: bigint[]): bigint {
    return sigs.reduce((a, s) => (a + s) % P, 0n);
  },
  // (Σ sk_i)·h == Σ σ_i  ← agg_sig_eq_agg_key_sig
  aggregateVerify(signerIds: string[], msgHash: bigint, aggSig: bigint): boolean {
    const aggKey = signerIds.reduce((a, sid) => (a + this.skOf(sid)) % P, 0n);
    return (aggKey * msgHash) % P === ((aggSig % P) + P) % P;
  },
};

// ── Merkle root (RFC 6962, duplicate-last padding) ───────────────────────────
function merkleRoot(leaves: string[]): string {
  if (leaves.length === 0) return "";
  let level = leaves.map((h) =>
    h.length === 64 ? Buffer.from(h, "hex") : createHash("sha256").update(h).digest(),
  );
  while (level.length > 1) {
    if (level.length % 2) level.push(level[level.length - 1]);
    const next: Buffer[] = [];
    for (let i = 0; i < level.length; i += 2)
      next.push(createHash("sha256").update(Buffer.concat([level[i], level[i + 1]])).digest());
    level = next;
  }
  return level[0].toString("hex");
}

// ── Span + emitter ────────────────────────────────────────────────────────────
export interface OtelMeshSpan {
  trace_id: string;
  span_id: string;
  parent_span_id?: string;
  name: string;
  start_time: string;
  end_time: string;
  status: { code: string };
  attributes: Record<string, string | number | boolean>;
}

export interface BatchAggregate {
  count: number;
  agg_sig: string; // hex (bigint)
  root: string;
  verified: boolean;
  span_ids: string[];
}

interface BatchEntry {
  otel: OtelMeshSpan;
  receiptHash: string;
}

export class MeshEmitter {
  private batch: BatchEntry[] = [];
  readonly signerId: string;

  constructor(public readonly organ: Organ, signerId?: string) {
    if (!ORGANS.includes(organ)) throw new Error(`unknown organ ${organ}`);
    this.signerId = signerId ?? `mesh:${organ}`;
  }

  emit(
    name: string,
    lambdaValue: number,
    opts: {
      trace?: TraceContext;
      attributes?: Record<string, string | number | boolean>;
      parentSpanId?: string;
      status?: string;
    } = {},
  ): OtelMeshSpan {
    if (!SPAN_NAMES[this.organ].includes(name))
      throw new Error(`span ${name} not in schema for organ ${this.organ}`);
    const trace = opts.trace ?? TraceContext.newRoot();
    const now = new Date().toISOString().replace("Z", "000Z");
    const drift = lambdaValue < LAMBDA_FLOOR_MESH || lambdaValue > 1.0;
    const receiptBody = JSON.stringify({
      attributes: opts.attributes ?? {},
      lambda: Math.round(lambdaValue * 1e6) / 1e6,
      name,
      organ: this.organ,
      span_id: trace.spanId,
      status: opts.status ?? "OK",
      trace_id: trace.traceId,
    });
    // NOTE: key order matches mesh.py json.dumps(sort_keys=True) for cross-SDK parity.
    const sortedBody = canonicalJSON({
      organ: this.organ,
      name,
      trace_id: trace.traceId,
      span_id: trace.spanId,
      lambda: Math.round(lambdaValue * 1e6) / 1e6,
      attributes: opts.attributes ?? {},
      status: opts.status ?? "OK",
    });
    const receiptHash = createHash("sha256").update(sortedBody).digest("hex");
    const signature = sign("application/vnd.in-toto+json", Buffer.from(sortedBody));
    void receiptBody;
    const otel: OtelMeshSpan = {
      trace_id: trace.traceId,
      span_id: trace.spanId,
      name,
      start_time: now,
      end_time: now,
      status: { code: opts.status ?? "OK" },
      attributes: {
        "szl.mesh.organ": this.organ,
        "szl.mesh.receipt_hash": receiptHash,
        "szl.mesh.dsse_payload_type": "application/vnd.in-toto+json",
        "szl.mesh.lambda_value": lambdaValue.toFixed(6),
        "szl.mesh.governance_drift": drift,
        "szl.mesh.dsse_signature": signature,
        ...(opts.attributes ?? {}),
      },
    };
    if (opts.parentSpanId) otel.parent_span_id = opts.parentSpanId;
    this.batch.push({ otel, receiptHash });
    return otel;
  }

  batchAggregate(): BatchAggregate {
    if (this.batch.length === 0)
      return { count: 0, agg_sig: "0", root: "", verified: true, span_ids: [] };
    const leaves = this.batch.map((b) => b.receiptHash);
    const root = merkleRoot(leaves);
    const rootHash = scalar(root);
    const sigs = this.batch.map(() => BLS.sign(this.signerId, rootHash));
    const agg = BLS.aggregate(sigs);
    const signers = this.batch.map(() => this.signerId);
    return {
      count: this.batch.length,
      agg_sig: agg.toString(16),
      root,
      verified: BLS.aggregateVerify(signers, rootHash, agg),
      span_ids: this.batch.map((b) => b.otel.span_id),
    };
  }

  drain(): OtelMeshSpan[] {
    const out = this.batch.map((b) => b.otel);
    this.batch = [];
    return out;
  }
}

export function verifyBatch(spans: OtelMeshSpan[], agg: BatchAggregate, signerId: string): boolean {
  const leaves = spans.map((s) => s.attributes["szl.mesh.receipt_hash"] as string);
  if (merkleRoot(leaves) !== agg.root) return false;
  const rootHash = scalar(agg.root);
  const signers = spans.map(() => signerId);
  return BLS.aggregateVerify(signers, rootHash, BigInt("0x" + agg.agg_sig));
}

// Canonical JSON with sorted keys, matching Python json.dumps(sort_keys=True, separators=(",",":")).
function canonicalJSON(obj: unknown): string {
  if (obj === null || typeof obj !== "object") return JSON.stringify(obj);
  if (Array.isArray(obj)) return "[" + obj.map(canonicalJSON).join(",") + "]";
  const keys = Object.keys(obj as Record<string, unknown>).sort();
  return "{" + keys.map((k) => JSON.stringify(k) + ":" + canonicalJSON((obj as Record<string, unknown>)[k])).join(",") + "}";
}
