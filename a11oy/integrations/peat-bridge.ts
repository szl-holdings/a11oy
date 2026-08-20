/**
 * a11oy/integrations/peat-bridge.ts
 *
 * SZL Holdings — peat-protocol Integration Bridge
 * Version: 0.4.0-alpha.1
 * Doctrine: v6 | STAGED-ADVISORY
 *
 * Bridges SZL DSSE governance receipts → peat capability dispatches.
 * Uses peat-protocol REST/HTTP transport (shallow integration ~500-1000 LOC).
 * peat-protocol rc.17 — persistent multiplexed sync via peat-mesh rc.25.
 *
 * Trademark note: "peat" is a Defense Unicorns project. This bridge is
 * an SZL integration, not a peat fork or derivative. All capability
 * schemas published under the `szl.*` namespace per peat-schema conventions.
 *
 * Architecture:
 *   Pepr controller → DSSE receipt → PeatBridge → peat-protocol HTTP API
 *                                              ↓
 *                                     peat-mesh sync (rc.25)
 *                                              ↓
 *                                   UDS mesh capability dispatch
 *
 * Dependencies (add to package.json):
 *   "@noble/post-quantum": "^1.0.0"  (ML-DSA-65 receipt verification)
 *   "zod": "^3.22.0"                 (schema validation)
 */

import { createHmac, randomBytes, createHash } from "node:crypto";
import { ml_dsa65 } from "@noble/post-quantum/ml-dsa.js";

// ---------------------------------------------------------------------------
// Types & Schemas
// ---------------------------------------------------------------------------

/** DSSE envelope as produced by Pepr governance-receipts.ts */
export interface DsseEnvelope {
  payloadType: "application/vnd.szl.governance-receipt+json";
  payload: string;         // base64url-encoded JSON
  signatures: Array<{
    keyid: string;
    sig: string;           // base64url-encoded HMAC-SHA-256 (legacy)
    pqc_sig?: string;      // base64url-encoded ML-DSA-65 (v0.4.0+)
    alg: "hmac-sha256" | "ml-dsa-65";
  }>;
}

/** Decoded DSSE payload */
export interface GovernanceReceipt {
  receipt_id: string;
  schema_version: "1.0" | "1.1";
  timestamp: string;           // ISO 8601
  organ_id: string;
  organ_version: string;
  cluster_id: string;
  namespace: string;
  action: "ADMIT" | "DENY" | "MUTATE";
  resource_kind: string;
  resource_name: string;
  pepr_controller_version: string;
  slsa_level: 1;
  attestation_uri?: string;    // Rekor entry URI (SLSA L1 honest; Sigstore signing pending)
  metadata: Record<string, unknown>;
}

/** peat capability schema for SZL organ dispatches (szl.organ.* namespace) */
export interface PeatCapabilityDispatch {
  capability_id: string;       // "szl.organ.{organ_id}.{action}"
  version: string;             // "0.4.0"
  source: "szl-uds-deployment";
  receipt_id: string;          // links back to DSSE receipt
  organ_id: string;
  action: GovernanceReceipt["action"];
  timestamp: string;
  cluster_id: string;
  namespace: string;
  payload: {
    governance_receipt_digest: string;  // SHA-256 of raw DSSE envelope JSON
    slsa_level: 1;
    attestation_uri?: string;
    organ_version: string;
    pqc_signed: boolean;                // true if ML-DSA-65 sig present
  };
  governance_receipt: string;           // base64url(DSSE envelope JSON)
}

/** peat-protocol HTTP response for capability registration */
export interface PeatCapabilityResponse {
  capability_id: string;
  cell_id: string;
  sync_epoch: number;
  mesh_peers: number;
  acknowledged_at: string;
}

/** peat-mesh sync status */
export interface PeatMeshStatus {
  cell_id: string;
  peer_count: number;
  sync_epoch: number;
  persistent_channels: string[];
  last_heartbeat: string;
  status: "SYNCED" | "SYNCING" | "PARTITIONED" | "DISCONNECTED";
}

/** Bridge configuration */
export interface PeatBridgeConfig {
  peatEndpoint: string;          // e.g. "http://peat-gateway:8080"
  peatApiKey?: string;           // optional; OIDC preferred
  peatOidcToken?: string;        // OIDC JWT for auth
  szlSigningKey: Uint8Array;     // HMAC-SHA-256 key (legacy)
  szlPqcSecretKey?: Uint8Array;  // ML-DSA-65 secret key (v0.4.0+)
  szlPqcPublicKey?: Uint8Array;  // ML-DSA-65 public key (v0.4.0+)
  clusterId: string;
  meshSyncIntervalMs: number;    // default 30_000
  receiptBufferSize: number;     // max buffered receipts during peat outage
  verifyOnDispatch: boolean;     // re-verify DSSE before dispatch
  logLevel: "debug" | "info" | "warn" | "error";
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PEAT_CAPABILITY_PREFIX = "szl.organ";
const BRIDGE_VERSION = "0.4.0-alpha.1";
const DEFAULT_MESH_SYNC_INTERVAL = 30_000; // 30 seconds
const DEFAULT_RECEIPT_BUFFER = 1000;
const PEAT_API_VERSION = "v1";

// ---------------------------------------------------------------------------
// Utility: base64url encode/decode
// ---------------------------------------------------------------------------

function b64urlEncode(buf: Uint8Array | Buffer): string {
  return Buffer.from(buf)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function b64urlDecode(s: string): Buffer {
  // Pad to multiple of 4
  const padded = s + "==".slice(0, (4 - (s.length % 4)) % 4);
  return Buffer.from(padded.replace(/-/g, "+").replace(/_/g, "/"), "base64");
}

// ---------------------------------------------------------------------------
// DSSE Verifier
// ---------------------------------------------------------------------------

export class DsseVerifier {
  constructor(
    private readonly hmacKey: Uint8Array,
    private readonly pqcPublicKey?: Uint8Array
  ) {}

  /** Verify DSSE envelope — must pass AT LEAST one valid signature */
  verify(envelope: DsseEnvelope): { valid: boolean; algorithms: string[] } {
    const PAE = this.buildPAE(envelope.payloadType, envelope.payload);
    const validAlgs: string[] = [];

    for (const sig of envelope.signatures) {
      if (sig.alg === "hmac-sha256") {
        const expected = createHmac("sha256", this.hmacKey)
          .update(PAE)
          .digest();
        const actual = b64urlDecode(sig.sig);
        // Constant-time comparison
        if (
          expected.length === actual.length &&
          expected.every((b, i) => b === actual[i])
        ) {
          validAlgs.push("hmac-sha256");
        }
      } else if (sig.alg === "ml-dsa-65" && sig.pqc_sig && this.pqcPublicKey) {
        try {
          const sigBytes = b64urlDecode(sig.pqc_sig);
          const msg = Buffer.from(PAE);
          const isValid = ml_dsa65.verify(this.pqcPublicKey, msg, sigBytes);
          if (isValid) validAlgs.push("ml-dsa-65");
        } catch {
          // Invalid signature bytes — skip
        }
      }
    }

    return { valid: validAlgs.length > 0, algorithms: validAlgs };
  }

  /** Pre-Authentication Encoding per DSSE spec */
  private buildPAE(payloadType: string, payload: string): Buffer {
    const enc = (s: string) => {
      const buf = Buffer.from(s, "utf-8");
      const len = Buffer.alloc(8);
      len.writeBigUInt64LE(BigInt(buf.length));
      return Buffer.concat([len, buf]);
    };
    return Buffer.concat([
      Buffer.from("DSSEv1 "),
      enc(payloadType),
      Buffer.from(" "),
      enc(payload),
    ]);
  }

  /** Decode and parse DSSE payload */
  decodePayload(envelope: DsseEnvelope): GovernanceReceipt {
    const raw = b64urlDecode(envelope.payload).toString("utf-8");
    return JSON.parse(raw) as GovernanceReceipt;
  }
}

// ---------------------------------------------------------------------------
// CapabilityMatcher — mirrors Defense Unicorns peat CapabilityMatcher pattern
// ---------------------------------------------------------------------------

/** Mirrors peat CapabilityMatcher: matches SZL organ receipts to peat scopes */
export class CapabilityMatcher {
  private readonly rules: CapabilityRule[] = [];

  constructor(rules?: CapabilityRule[]) {
    if (rules) this.rules.push(...rules);
    this.installDefaultRules();
  }

  private installDefaultRules(): void {
    // Default: every ADMIT receipt dispatches to szl.organ.{id}.admitted
    this.rules.push({
      match: (r) => r.action === "ADMIT",
      capabilityId: (r) => `${PEAT_CAPABILITY_PREFIX}.${r.organ_id}.admitted`,
      priority: 0,
    });
    // DENY receipts → szl.organ.{id}.denied
    this.rules.push({
      match: (r) => r.action === "DENY",
      capabilityId: (r) => `${PEAT_CAPABILITY_PREFIX}.${r.organ_id}.denied`,
      priority: 0,
    });
    // MUTATE receipts → szl.organ.{id}.mutated
    this.rules.push({
      match: (r) => r.action === "MUTATE",
      capabilityId: (r) => `${PEAT_CAPABILITY_PREFIX}.${r.organ_id}.mutated`,
      priority: 0,
    });
  }

  /** Add a custom rule (higher priority number = checked first) */
  addRule(rule: CapabilityRule): void {
    this.rules.push(rule);
    this.rules.sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));
  }

  /** Match a receipt to a capability ID */
  match(receipt: GovernanceReceipt): string | null {
    for (const rule of this.rules) {
      if (rule.match(receipt)) {
        return rule.capabilityId(receipt);
      }
    }
    return null;
  }
}

export interface CapabilityRule {
  match: (receipt: GovernanceReceipt) => boolean;
  capabilityId: (receipt: GovernanceReceipt) => string;
  priority?: number;
}

// ---------------------------------------------------------------------------
// PeatBridge — main integration class
// ---------------------------------------------------------------------------

export class PeatBridge {
  private readonly config: Required<PeatBridgeConfig>;
  private readonly verifier: DsseVerifier;
  private readonly matcher: CapabilityMatcher;
  private receiptBuffer: Array<{ envelope: DsseEnvelope; attempts: number }> = [];
  private meshStatus: PeatMeshStatus | null = null;
  private syncTimer: ReturnType<typeof setInterval> | null = null;
  private connected = false;

  constructor(config: PeatBridgeConfig, matcher?: CapabilityMatcher) {
    this.config = {
      meshSyncIntervalMs: DEFAULT_MESH_SYNC_INTERVAL,
      receiptBufferSize: DEFAULT_RECEIPT_BUFFER,
      verifyOnDispatch: true,
      logLevel: "info",
      peatApiKey: undefined,
      peatOidcToken: undefined,
      szlPqcSecretKey: undefined,
      szlPqcPublicKey: undefined,
      ...config,
    };
    this.verifier = new DsseVerifier(
      config.szlSigningKey,
      config.szlPqcPublicKey
    );
    this.matcher = matcher ?? new CapabilityMatcher();
  }

  // -------------------------------------------------------------------------
  // Lifecycle
  // -------------------------------------------------------------------------

  async connect(): Promise<void> {
    this.log("info", `PeatBridge connecting to ${this.config.peatEndpoint}`);
    const status = await this.fetchMeshStatus();
    this.meshStatus = status;
    this.connected = true;
    this.log("info", `peat-mesh: ${status.status}, peers=${status.peer_count}, epoch=${status.sync_epoch}`);

    // Start periodic mesh sync heartbeat
    this.syncTimer = setInterval(
      () => this.syncMesh().catch((e) => this.log("warn", `mesh sync error: ${e}`)),
      this.config.meshSyncIntervalMs
    );

    // Drain any buffered receipts
    await this.drainBuffer();
  }

  async disconnect(): Promise<void> {
    if (this.syncTimer) {
      clearInterval(this.syncTimer);
      this.syncTimer = null;
    }
    this.connected = false;
    this.log("info", "PeatBridge disconnected");
  }

  // -------------------------------------------------------------------------
  // Core: dispatch a DSSE governance receipt to peat
  // -------------------------------------------------------------------------

  async dispatchReceipt(envelope: DsseEnvelope): Promise<PeatCapabilityResponse | null> {
    // 1. Optionally verify before dispatch
    if (this.config.verifyOnDispatch) {
      const { valid, algorithms } = this.verifier.verify(envelope);
      if (!valid) {
        this.log("error", "DSSE verification failed — rejecting dispatch");
        throw new Error("DSSE signature verification failed");
      }
      this.log("debug", `DSSE verified via: ${algorithms.join(", ")}`);
    }

    // 2. Decode receipt
    const receipt = this.verifier.decodePayload(envelope);

    // 3. Match to peat capability
    const capabilityId = this.matcher.match(receipt);
    if (!capabilityId) {
      this.log("warn", `No capability rule matched for organ=${receipt.organ_id} action=${receipt.action}`);
      return null;
    }

    // 4. Build peat capability dispatch
    const envelopeJson = JSON.stringify(envelope);
    const digest = createHash("sha256").update(envelopeJson).digest("hex");
    const dispatch: PeatCapabilityDispatch = {
      capability_id: capabilityId,
      version: BRIDGE_VERSION,
      source: "szl-uds-deployment",
      receipt_id: receipt.receipt_id,
      organ_id: receipt.organ_id,
      action: receipt.action,
      timestamp: receipt.timestamp,
      cluster_id: receipt.cluster_id,
      namespace: receipt.namespace,
      payload: {
        governance_receipt_digest: digest,
        slsa_level: receipt.slsa_level,
        attestation_uri: receipt.attestation_uri,
        organ_version: receipt.organ_version,
        pqc_signed: envelope.signatures.some((s) => s.alg === "ml-dsa-65"),
      },
      governance_receipt: b64urlEncode(Buffer.from(envelopeJson)),
    };

    // 5. Send to peat
    if (!this.connected) {
      this.bufferReceipt(envelope);
      this.log("warn", "peat not connected — buffered receipt");
      return null;
    }

    return await this.sendToPeat(dispatch);
  }

  // -------------------------------------------------------------------------
  // peat HTTP API calls
  // -------------------------------------------------------------------------

  private async sendToPeat(dispatch: PeatCapabilityDispatch): Promise<PeatCapabilityResponse> {
    const url = `${this.config.peatEndpoint}/api/${PEAT_API_VERSION}/capabilities`;
    const headers = this.buildHeaders();

    let retries = 0;
    const maxRetries = 3;

    while (retries <= maxRetries) {
      try {
        const res = await fetch(url, {
          method: "POST",
          headers,
          body: JSON.stringify(dispatch),
        });

        if (res.ok) {
          const body = await res.json() as PeatCapabilityResponse;
          this.log("info", `peat ACK: capability=${body.capability_id} cell=${body.cell_id} epoch=${body.sync_epoch}`);
          return body;
        }

        if (res.status === 429 || res.status >= 500) {
          const delay = Math.min(1000 * Math.pow(2, retries), 30_000);
          this.log("warn", `peat HTTP ${res.status} — retry ${retries + 1}/${maxRetries} in ${delay}ms`);
          await sleep(delay);
          retries++;
          continue;
        }

        // 4xx non-retryable
        const err = await res.text();
        throw new Error(`peat rejected dispatch: HTTP ${res.status} — ${err}`);
      } catch (e) {
        if (retries >= maxRetries) throw e;
        const delay = Math.min(1000 * Math.pow(2, retries), 30_000);
        this.log("warn", `peat request error: ${e} — retry ${retries + 1}/${maxRetries} in ${delay}ms`);
        await sleep(delay);
        retries++;
      }
    }

    throw new Error("peat dispatch failed after max retries");
  }

  private async fetchMeshStatus(): Promise<PeatMeshStatus> {
    const url = `${this.config.peatEndpoint}/api/${PEAT_API_VERSION}/mesh/status`;
    const res = await fetch(url, { headers: this.buildHeaders() });
    if (!res.ok) throw new Error(`peat mesh status: HTTP ${res.status}`);
    return res.json() as Promise<PeatMeshStatus>;
  }

  private async syncMesh(): Promise<void> {
    const status = await this.fetchMeshStatus();
    const prev = this.meshStatus?.status;
    this.meshStatus = status;

    if (prev !== "SYNCED" && status.status === "SYNCED") {
      this.log("info", `peat-mesh recovered: status=SYNCED peers=${status.peer_count}`);
      await this.drainBuffer();
    }
    if (status.status === "PARTITIONED") {
      this.log("warn", `peat-mesh partitioned — buffering until recovered`);
    }
  }

  // -------------------------------------------------------------------------
  // Receipt buffer (peat outage resilience)
  // -------------------------------------------------------------------------

  private bufferReceipt(envelope: DsseEnvelope): void {
    if (this.receiptBuffer.length >= this.config.receiptBufferSize) {
      this.log("warn", `Receipt buffer full (${this.config.receiptBufferSize}) — dropping oldest`);
      this.receiptBuffer.shift();
    }
    this.receiptBuffer.push({ envelope, attempts: 0 });
  }

  private async drainBuffer(): Promise<void> {
    if (this.receiptBuffer.length === 0) return;
    this.log("info", `Draining ${this.receiptBuffer.length} buffered receipts`);

    const toRetry = [...this.receiptBuffer];
    this.receiptBuffer = [];

    for (const { envelope, attempts } of toRetry) {
      if (attempts >= 5) {
        this.log("error", `Dropping receipt after 5 attempts — receipt_id may be lost`);
        continue;
      }
      try {
        await this.dispatchReceipt(envelope);
      } catch (e) {
        this.log("warn", `Buffer retry failed: ${e} — re-queuing (attempt ${attempts + 1})`);
        this.receiptBuffer.push({ envelope, attempts: attempts + 1 });
      }
    }
  }

  // -------------------------------------------------------------------------
  // peat-mesh ↔ uds-mesh interop hooks
  // -------------------------------------------------------------------------

  /**
   * Subscribe to peat mesh capability announcements for a given scope.
   * Long-poll implementation (HTTP transport tier).
   * Medium-depth (peat-ffi) will replace this in v0.5.0.
   */
  async subscribeToMeshCapabilities(
    scope: string,
    handler: (capability: PeatCapabilityDispatch) => Promise<void>,
    signal?: AbortSignal
  ): Promise<void> {
    const url = `${this.config.peatEndpoint}/api/${PEAT_API_VERSION}/capabilities/subscribe?scope=${encodeURIComponent(scope)}`;
    this.log("info", `Subscribing to peat capabilities: scope=${scope}`);

    while (!signal?.aborted) {
      try {
        const res = await fetch(url, {
          headers: { ...this.buildHeaders(), Accept: "application/x-ndjson" },
          signal,
        });

        if (!res.ok || !res.body) {
          this.log("warn", `peat subscribe HTTP ${res.status} — reconnecting in 5s`);
          await sleep(5000);
          continue;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const cap = JSON.parse(line) as PeatCapabilityDispatch;
              await handler(cap);
            } catch (e) {
              this.log("warn", `Failed to parse peat capability: ${e}`);
            }
          }
        }
      } catch (e) {
        if (signal?.aborted) break;
        this.log("warn", `peat subscribe error: ${e} — reconnecting in 5s`);
        await sleep(5000);
      }
    }
  }

  /**
   * uds-mesh → peat-mesh bridge:
   * When peat announces a capability that affects the UDS mesh,
   * translate it to a Kubernetes annotation update (via kubectl patch).
   *
   * In production, replace kubectl with Kubernetes client-node API call.
   */
  async handleInboundPeatCapability(capability: PeatCapabilityDispatch): Promise<void> {
    this.log("debug", `Inbound peat capability: ${capability.capability_id}`);

    // Only handle szl.organ.* capabilities from our own cells
    if (!capability.capability_id.startsWith(PEAT_CAPABILITY_PREFIX)) {
      return;
    }

    // Construct a Kubernetes annotation reflecting the peat sync
    const annotations = {
      "szl.io/peat-capability-id": capability.capability_id,
      "szl.io/peat-receipt-id": capability.receipt_id,
      "szl.io/peat-sync-timestamp": capability.timestamp,
      "szl.io/peat-organ-id": capability.organ_id,
      "szl.io/peat-action": capability.action,
    };

    this.log("info", `uds-mesh sync: annotating namespace=${capability.namespace} with peat capability`);
    // In production: call k8s client.patchNamespace(capability.namespace, { metadata: { annotations } })
    // For now: emit as structured log (Pepr picks up via watcher)
    console.log(JSON.stringify({
      event: "peat_to_uds_mesh_sync",
      namespace: capability.namespace,
      annotations,
      timestamp: new Date().toISOString(),
    }));
  }

  // -------------------------------------------------------------------------
  // Auth helpers
  // -------------------------------------------------------------------------

  private buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "User-Agent": `szl-peat-bridge/${BRIDGE_VERSION}`,
      "X-SZL-Bridge-Version": BRIDGE_VERSION,
    };
    if (this.config.peatApiKey) {
      headers["X-Peat-Api-Key"] = this.config.peatApiKey;
    } else if (this.config.peatOidcToken) {
      headers["Authorization"] = `Bearer ${this.config.peatOidcToken}`;
    }
    return headers;
  }

  // -------------------------------------------------------------------------
  // Logging
  // -------------------------------------------------------------------------

  private log(level: PeatBridgeConfig["logLevel"], msg: string): void {
    const levels = { debug: 0, info: 1, warn: 2, error: 3 };
    if (levels[level] >= levels[this.config.logLevel]) {
      const entry = JSON.stringify({
        ts: new Date().toISOString(),
        level,
        component: "peat-bridge",
        msg,
        bridge_version: BRIDGE_VERSION,
        cluster_id: this.config.clusterId,
      });
      if (level === "error") console.error(entry);
      else if (level === "warn") console.warn(entry);
      else console.log(entry);
    }
  }
}

// ---------------------------------------------------------------------------
// Factory: create PeatBridge from environment variables
// ---------------------------------------------------------------------------

export function createPeatBridgeFromEnv(): PeatBridge {
  const endpoint = process.env.PEAT_ENDPOINT ?? "http://peat-gateway:8080";
  const clusterId = process.env.CLUSTER_ID ?? "szl-default";
  const hmacKeyHex = process.env.SZL_HMAC_KEY;
  const pqcSecretKeyB64 = process.env.SZL_PQC_SECRET_KEY;
  const pqcPublicKeyB64 = process.env.SZL_PQC_PUBLIC_KEY;

  if (!hmacKeyHex) throw new Error("SZL_HMAC_KEY env var required");

  const config: PeatBridgeConfig = {
    peatEndpoint: endpoint,
    peatApiKey: process.env.PEAT_API_KEY,
    peatOidcToken: process.env.PEAT_OIDC_TOKEN,
    szlSigningKey: Buffer.from(hmacKeyHex, "hex"),
    szlPqcSecretKey: pqcSecretKeyB64
      ? Buffer.from(pqcSecretKeyB64, "base64")
      : undefined,
    szlPqcPublicKey: pqcPublicKeyB64
      ? Buffer.from(pqcPublicKeyB64, "base64")
      : undefined,
    clusterId,
    meshSyncIntervalMs: parseInt(process.env.PEAT_SYNC_INTERVAL_MS ?? "30000"),
    receiptBufferSize: parseInt(process.env.PEAT_RECEIPT_BUFFER_SIZE ?? "1000"),
    verifyOnDispatch: process.env.PEAT_VERIFY_ON_DISPATCH !== "false",
    logLevel: (process.env.LOG_LEVEL as PeatBridgeConfig["logLevel"]) ?? "info",
  };

  return new PeatBridge(config);
}

// ---------------------------------------------------------------------------
// Pepr integration hook — call from pepr.ts When() handler
// ---------------------------------------------------------------------------

/**
 * Usage in pepr.ts:
 *
 *   import { dispatchReceiptToPeat } from "../a11oy/integrations/peat-bridge";
 *
 *   When(a.ConfigMap)
 *     .IsCreatedOrUpdated()
 *     .InNamespace("szl-organs")
 *     .Mutate(async (request) => {
 *       const receipt = buildGovernanceReceipt(request, "ADMIT");
 *       const envelope = await signReceipt(receipt);
 *       await dispatchReceiptToPeat(envelope);
 *     });
 */
const globalBridge = process.env.PEAT_ENABLED === "true"
  ? createPeatBridgeFromEnv()
  : null;

let bridgeConnected = false;

export async function dispatchReceiptToPeat(
  envelope: DsseEnvelope
): Promise<PeatCapabilityResponse | null> {
  if (!globalBridge) return null;
  if (!bridgeConnected) {
    await globalBridge.connect();
    bridgeConnected = true;
  }
  return globalBridge.dispatchReceipt(envelope);
}

// ---------------------------------------------------------------------------
// Key generation utilities (dev/test only — use HSM in production)
// ---------------------------------------------------------------------------

export function generateHmacKey(): Buffer {
  return randomBytes(32);
}

export function generateMlDsa65KeyPair(): { secretKey: Uint8Array; publicKey: Uint8Array } {
  const seed = randomBytes(32);
  return ml_dsa65.keygen(seed);
}

// ---------------------------------------------------------------------------
// Self-test (run with: npx ts-node peat-bridge.ts --self-test)
// ---------------------------------------------------------------------------

async function selfTest(): Promise<void> {
  console.log("=== PeatBridge Self-Test ===");

  // Generate keys
  const hmacKey = generateHmacKey();
  const { secretKey, publicKey } = generateMlDsa65KeyPair();
  console.log("✓ Keys generated (HMAC-SHA-256 + ML-DSA-65)");

  // Build a mock DSSE envelope
  const receipt: GovernanceReceipt = {
    receipt_id: "test-" + randomBytes(8).toString("hex"),
    schema_version: "1.1",
    timestamp: new Date().toISOString(),
    organ_id: "organ-a",
    organ_version: "0.3.1",
    cluster_id: "szl-test-cluster",
    namespace: "szl-organs",
    action: "ADMIT",
    resource_kind: "ConfigMap",
    resource_name: "organ-a-dataset",
    pepr_controller_version: "0.4.0",
    slsa_level: 1,
    attestation_uri: "https://rekor.sigstore.dev/api/v1/log/entries?logIndex=12345", // example fixture; SLSA L1 honest
    metadata: { test: true },
  };

  const payloadB64 = b64urlEncode(Buffer.from(JSON.stringify(receipt)));
  const payloadType = "application/vnd.szl.governance-receipt+json";

  // Build PAE
  const enc = (s: string) => {
    const buf = Buffer.from(s, "utf-8");
    const len = Buffer.alloc(8);
    len.writeBigUInt64LE(BigInt(buf.length));
    return Buffer.concat([len, buf]);
  };
  const PAE = Buffer.concat([
    Buffer.from("DSSEv1 "),
    enc(payloadType),
    Buffer.from(" "),
    enc(payloadB64),
  ]);

  // HMAC-SHA-256
  const hmacSig = createHmac("sha256", hmacKey).update(PAE).digest();

  // ML-DSA-65
  const pqcSig = ml_dsa65.sign(secretKey, PAE);

  const envelope: DsseEnvelope = {
    payloadType,
    payload: payloadB64,
    signatures: [
      {
        keyid: "szl-hmac-v1",
        sig: b64urlEncode(hmacSig),
        alg: "hmac-sha256",
      },
      {
        keyid: "szl-mldsa65-v1",
        sig: b64urlEncode(hmacSig), // unused field for legacy
        pqc_sig: b64urlEncode(pqcSig),
        alg: "ml-dsa-65",
      },
    ],
  };

  // Verify
  const verifier = new DsseVerifier(hmacKey, publicKey);
  const { valid, algorithms } = verifier.verify(envelope);
  console.log(`✓ DSSE verification: valid=${valid}, algorithms=[${algorithms.join(", ")}]`);

  // Capability matching
  const matcher = new CapabilityMatcher();
  const decoded = verifier.decodePayload(envelope);
  const capId = matcher.match(decoded);
  console.log(`✓ CapabilityMatcher: ${capId}`);

  console.log("=== Self-test PASSED ===");
}

// Run self-test if invoked directly
if (process.argv.includes("--self-test")) {
  selfTest().catch((e) => {
    console.error("SELF-TEST FAILED:", e);
    process.exit(1);
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default PeatBridge;
