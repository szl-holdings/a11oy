/**
 * Copyright 2026 SZL Holdings
 * SPDX-License-Identifier: Apache-2.0
 *
 * szl-receipt-on-deploy.ts
 *
 * Pepr capability that emits a DSSE-wrapped HMAC-SHA-256 governance receipt
 * for every Kubernetes Deployment and Job admission event, then annotates the
 * resource with the receipt SHA-256 ID.
 *
 * DSSE envelope format (simplified, https://github.com/secure-systems-lab/dsse):
 * {
 *   "payload":     "<base64(JSON payload)>",
 *   "payloadType": "application/vnd.szl.receipt.v1+json",
 *   "signatures":  [{ "keyid": "<keyid>", "sig": "<base64(HMAC-SHA-256)>" }]
 * }
 *
 * The payload JSON contains:
 * {
 *   "_type":       "https://szlholdings.com/receipt/v1",
 *   "subject":     "<namespace>/<kind>/<name>",
 *   "specHash":    "<sha256 of the resource spec JSON>",
 *   "clusterUID":  "<kube-system namespace UID>",
 *   "timestamp":   "<ISO-8601>",
 *   "admissionOp": "CREATE|UPDATE|DELETE"
 * }
 *
 * This is NOT a replacement for OPA/Gatekeeper or uds-core policy enforcement.
 * It is an audit trail layer that adds receipts; it does not block workloads.
 *
 * References:
 *   Pepr Capability API: https://docs.pepr.dev/capabilities
 *   DSSE spec:           https://github.com/secure-systems-lab/dsse
 */

import { Capability, a, Log } from "pepr";
import * as crypto from "crypto";
import * as fs from "fs";

// ── Configuration ─────────────────────────────────────────────────────────────

/**
 * Ed25519 private key (PKCS#8 PEM, base64) from the szl-receipts-ed25519 Secret.
 * Mounted at /etc/szl-receipts-key/key.priv (preferred) OR injected via SZL_HMAC_KEY
 * env var for HMAC-SHA-256 fallback. The Secret must be created by running:
 *   bash scripts/generate-receipt-key.sh
 * and applying the output before deploying (see k8s/secrets/szl-receipts-ed25519.yaml).
 */
/** Load Ed25519 private key PEM from mounted Secret (preferred path). */
function loadEd25519Key(): string | null {
  const MOUNT_PATH = "/etc/szl-receipts-key/key.priv";
  try {
    const pem = fs.readFileSync(MOUNT_PATH, "utf8");
    if (pem && pem.includes("PRIVATE KEY")) {
      Log.info("[szl] Ed25519 key loaded from mounted Secret (production mode)");
      return pem;
    }
  } catch {
    // Secret not mounted — fall through to env var / demo mode
  }
  return null;
}

/** Base64-encoded HMAC-SHA-256 key. Injected via environment variable (legacy fallback). */
const HMAC_KEY_B64 = process.env.SZL_HMAC_KEY ?? "";

/** URL of the in-cluster SZL receipts server. */
const RECEIPTS_URL =
  process.env.SZL_RECEIPTS_URL ??
  "http://szl-receipts-server.szl-receipts.svc.cluster.local:8080/receipt";

/** Key ID embedded in the DSSE signature block. */
const KEY_ID = process.env.SZL_KEY_ID ?? "szl-dev-hmac-sha256-2026";

/** If true, failures to POST receipts are logged but do not block admission. */
const FAIL_OPEN = process.env.SZL_RECEIPT_FAIL_OPEN !== "false";

// ── Helpers ───────────────────────────────────────────────────────────────────

/** SHA-256 of an object serialized as stable JSON. */
function sha256(obj: unknown): string {
  const serialized = JSON.stringify(obj, Object.keys(obj as object).sort());
  return crypto.createHash("sha256").update(serialized).digest("hex");
}

/**
 * Build a DSSE envelope.
 *
 * Signing priority:
 *   1. Ed25519 private key from mounted Secret (/etc/szl-receipts-key/key.priv)
 *      — provisioned via szl-receipts-ed25519 Secret (see k8s/secrets/ and scripts/)
 *   2. HMAC-SHA-256 from SZL_HMAC_KEY env var (legacy fallback, symmetric)
 *   3. UNSIGNED sentinel — explicit "UNSIGNED-NO-KEY-CONFIGURED" (not a fake signature)
 *
 * The Ed25519 path uses Node.js crypto.sign() with a DER-imported private key.
 * The HMAC path is retained for backward compatibility with existing receipt consumers.
 */
function buildDSSEEnvelope(payload: object): {
  payload: string;
  payloadType: string;
  signatures: { keyid: string; sig: string }[];
} {
  const payloadBytes = Buffer.from(JSON.stringify(payload));
  const payloadB64 = payloadBytes.toString("base64");

  // Try Ed25519 first (production path — mounted Secret)
  const ed25519Pem = loadEd25519Key();
  if (ed25519Pem) {
    try {
      const sig = crypto
        .sign(null, payloadBytes, { key: ed25519Pem, dsaEncoding: "ieee-p1363" })
        .toString("base64");
      Log.info("[szl] Receipt signed with Ed25519 (production mode)");
      return {
        payload: payloadB64,
        payloadType: "application/vnd.szl.receipt.v1+json",
        signatures: [{ keyid: "szl-receipts-ed25519", sig }],
      };
    } catch (err) {
      Log.warn({ err }, "[szl] Ed25519 sign failed — falling back to HMAC");
    }
  }

  // HMAC-SHA-256 fallback (legacy — env var path)
  if (HMAC_KEY_B64) {
    try {
      const keyBytes = Buffer.from(HMAC_KEY_B64, "base64");
      const sig = crypto
        .createHmac("sha256", keyBytes)
        .update(payloadBytes)
        .digest("base64");
      Log.info("[szl] Receipt signed with HMAC-SHA-256 (legacy env var path)");
      return {
        payload: payloadB64,
        payloadType: "application/vnd.szl.receipt.v1+json",
        signatures: [{ keyid: KEY_ID, sig }],
      };
    } catch (err) {
      Log.warn({ err }, "[szl] HMAC sign failed — emitting unsigned receipt");
    }
  } else {
    // No key configured: emit explicit unsigned sentinel (not a fake signature)
    Log.warn(
      "[szl] No signing key configured — receipts will be unsigned. " +
      "Run scripts/generate-receipt-key.sh and apply szl-receipts-ed25519 Secret. " +
      "See k8s/secrets/szl-receipts-ed25519.yaml for instructions."
    );
  }

  // Explicit unsigned sentinel — never a fabricated signature
  return {
    payload: payloadB64,
    payloadType: "application/vnd.szl.receipt.v1+json",
    signatures: [{ keyid: "unsigned", sig: "UNSIGNED-NO-KEY-CONFIGURED" }],
  };
}

/**
 * POST the DSSE envelope to the receipts server.
 * Returns the receipt ID on success, or null on failure (fail-open).
 */
async function postReceipt(envelope: object): Promise<string | null> {
  const body = JSON.stringify(envelope);
  try {
    const resp = await fetch(RECEIPTS_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      // 2-second timeout — admission webhooks have a hard deadline
      signal: AbortSignal.timeout(2000),
    });
    if (!resp.ok) {
      Log.warn(`[szl] Receipts server responded ${resp.status}`);
      return null;
    }
    const result = (await resp.json()) as { id?: string };
    return result.id ?? null;
  } catch (err) {
    if (FAIL_OPEN) {
      Log.warn({ err }, "[szl] Failed to POST receipt (fail-open — admitting anyway)");
      return null;
    }
    throw err;
  }
}

// ── Capability ────────────────────────────────────────────────────────────────

export const szlReceiptPolicy = new Capability({
  name: "szl-receipt-policy",
  description:
    "Emit DSSE-wrapped HMAC-SHA-256 governance receipts for every Deployment and Job " +
    "applied to the cluster, and annotate the resource with the receipt SHA-256 ID.",
  namespaces: [], // cluster-wide; alwaysIgnore in package.json filters system namespaces
});

const { When } = szlReceiptPolicy;

// ── Deployment handler ────────────────────────────────────────────────────────

When(a.Deployment)
  .IsCreatedOrUpdated()
  .Mutate(async (deploy) => {
    const name      = deploy.Raw.metadata?.name      ?? "(unnamed)";
    const namespace = deploy.Raw.metadata?.namespace ?? "default";
    const op        = deploy.Raw.metadata?.annotations?.["kubectl.kubernetes.io/last-applied-configuration"]
      ? "UPDATE"
      : "CREATE";

    Log.info(`[szl] Processing Deployment ${namespace}/${name} op=${op}`);

    const specHash = sha256(deploy.Raw.spec ?? {});

    const payload = {
      _type:       "https://szlholdings.com/receipt/v1",
      subject:     `${namespace}/Deployment/${name}`,
      specHash,
      timestamp:   new Date().toISOString(),
      admissionOp: op,
      resourceVersion: deploy.Raw.metadata?.resourceVersion ?? "0",
    };

    const envelope   = buildDSSEEnvelope(payload);
    const receiptId  = sha256(envelope);
    const receiptSha = crypto
      .createHash("sha256")
      .update(JSON.stringify(envelope))
      .digest("hex");

    // Annotate the Deployment before it lands in etcd
    deploy.SetAnnotation("szl.receipt.id",  receiptSha);
    deploy.SetAnnotation("szl.receipt.ts",  payload.timestamp);
    deploy.SetAnnotation("szl.receipt.key", KEY_ID);

    // Async fire-and-forget to the receipts server (fail-open)
    void postReceipt(envelope).then((id) => {
      if (id) {
        Log.info(`[szl] Receipt accepted by server: ${id.slice(0, 16)}…`);
      }
    });
  });

// ── Job handler ───────────────────────────────────────────────────────────────

When(a.Job)
  .IsCreatedOrUpdated()
  .Mutate(async (job) => {
    const name      = job.Raw.metadata?.name      ?? "(unnamed)";
    const namespace = job.Raw.metadata?.namespace ?? "default";

    Log.info(`[szl] Processing Job ${namespace}/${name}`);

    const specHash = sha256(job.Raw.spec ?? {});

    const payload = {
      _type:       "https://szlholdings.com/receipt/v1",
      subject:     `${namespace}/Job/${name}`,
      specHash,
      timestamp:   new Date().toISOString(),
      admissionOp: "CREATE",
    };

    const envelope  = buildDSSEEnvelope(payload);
    const receiptSha = crypto
      .createHash("sha256")
      .update(JSON.stringify(envelope))
      .digest("hex");

    job.SetAnnotation("szl.receipt.id", receiptSha);
    job.SetAnnotation("szl.receipt.ts", payload.timestamp);
    job.SetAnnotation("szl.receipt.key", KEY_ID);

    void postReceipt(envelope).then((id) => {
      if (id) {
        Log.info(`[szl] Job receipt: ${id.slice(0, 16)}…`);
      }
    });
  });
