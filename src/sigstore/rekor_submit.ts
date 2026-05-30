/**
 * rekor_submit.ts — Submit SZL DSSE envelopes to Sigstore Rekor v1 transparency log
 *
 * Implements the Rekor "hashedrekord" entry type (v0.0.1) per the Sigstore
 * transparency log API documented at https://docs.sigstore.dev/logging/overview/
 * and the OpenAPI spec at https://rekor.sigstore.dev/api/v1.
 *
 * Every DSSE receipt produced by the SZL organ layer (sentra/amaru/rosie) is
 * independently timestamped via Rekor's Merkle-tree signed tree head (STH).
 * The returned UUID (logIndex + treeID) is stored alongside the original JSONL
 * receipt so that any third party can reproduce the inclusion proof without
 * trusting SZL infrastructure.
 *
 * STAGED-ADVISORY: Production use requires a Fulcio OIDC token (GitHub Actions
 * OIDC or workload-identity token).  The `signingKey` path below accepts a
 * plain ECDSA P-256 key for local development; swap for
 * `@sigstore/sign` Fulcio flow for keyless CI.
 *
 * Refs:
 *   - Rekor OpenAPI:  https://rekor.sigstore.dev/api/v1
 *   - hashedrekord:   https://github.com/sigstore/rekor/tree/main/pkg/types/hashedrekord
 *   - DSSE spec:      https://github.com/secure-systems-lab/dsse/blob/master/protocol.md
 *   - RFC 8785 (JCS): https://www.rfc-editor.org/rfc/rfc8785
 */

import { createHash, createSign, createVerify, generateKeyPairSync } from "node:crypto";
import { readFileSync } from "node:fs";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Canonical DSSE envelope as produced by SZL organ layer (sentra/amaru/rosie) */
export interface DSSEEnvelope {
  payload: string;           // base64url-encoded PAE(payloadType, payload)
  payloadType: string;       // e.g. "application/vnd.szl.receipt.v1+json"
  signatures: Array<{
    sig: string;             // base64url HMAC-SHA256 or ECDSA signature
    keyid?: string;
  }>;
}

/** Rekor hashedrekord v0.0.1 body (base64-encoded JSON) */
export interface HashedRekordBody {
  apiVersion: "0.0.1";
  kind: "hashedrekord";
  spec: {
    data: {
      hash: {
        algorithm: "sha256";
        value: string;       // hex SHA-256 of the canonical payload bytes
      };
    };
    signature: {
      content: string;       // base64-encoded DER signature
      publicKey: {
        content: string;     // base64-encoded PEM public key
      };
    };
  };
}

/** Rekor log entry as returned by POST /api/v1/log/entries */
export interface RekorEntry {
  [uuid: string]: {
    body: string;            // base64-encoded HashedRekordBody JSON
    integratedTime: number;  // Unix epoch seconds
    logID: string;
    logIndex: number;
    verification: {
      inclusionProof: {
        checkpoint: string;
        hashes: string[];
        logIndex: number;
        rootHash: string;
        treeSize: number;
      };
      signedEntryTimestamp: string; // base64-encoded RFC 3161 SET
    };
  };
}

/** SZL-specific Rekor submission result, stored alongside DSSE receipt JSONL */
export interface RekorSubmitResult {
  uuid: string;
  logIndex: number;
  integratedTime: number;
  treeID: string;
  inclusionProofRootHash: string;
  rekorEntryUrl: string;
  payloadHash: string;
  submittedAt: string;       // ISO-8601
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const REKOR_BASE = "https://rekor.sigstore.dev";
const REKOR_STAGING_BASE = "https://rekor.sigstore.dev"; // staging shares prod URL; use --staging flag in rekor-cli
const API_VERSION = "v1";

export interface RekorSubmitOptions {
  /** Use staging endpoint (same host, different tree in practice via CLI --staging) */
  staging?: boolean;
  /** Timeout in ms (default 10000) */
  timeoutMs?: number;
  /** PEM-encoded ECDSA P-256 private key for signing (dev mode).
   *  In production, leave undefined and provide `oidcToken` for Fulcio keyless. */
  signingKeyPem?: string;
  /** PEM-encoded public key matching signingKeyPem */
  publicKeyPem?: string;
  /** GitHub OIDC token for Fulcio keyless (STAGED-ADVISORY: wires into Fulcio CA) */
  oidcToken?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Canonical payload bytes: UTF-8 encode the DSSE payload field (base64url → raw).
 * We hash the *decoded* payload so the hash is algorithm-agnostic and matches
 * what `rekor-cli` produces for the same artifact.
 */
function decodeBase64url(b64: string): Buffer {
  // base64url → base64 standard
  const std = b64.replace(/-/g, "+").replace(/_/g, "/");
  return Buffer.from(std, "base64");
}

/** SHA-256 hex digest of bytes */
function sha256Hex(data: Buffer | string): string {
  return createHash("sha256").update(data).digest("hex");
}

/**
 * Build a minimal self-signed ECDSA P-256 key pair for dev/test purposes.
 * In production this is replaced by a Fulcio-issued ephemeral cert chain.
 */
export function generateDevKeyPair(): { privateKeyPem: string; publicKeyPem: string } {
  const { privateKey, publicKey } = generateKeyPairSync("ec", {
    namedCurve: "P-256",
    publicKeyEncoding: { type: "spki", format: "pem" },
    privateKeyEncoding: { type: "pkcs8", format: "pem" },
  });
  return { privateKeyPem: privateKey as string, publicKeyPem: publicKey as string };
}

/**
 * Sign the canonical artifact bytes with ECDSA-P256-SHA256.
 * Returns a base64-encoded DER signature (not base64url) because the Rekor
 * hashedrekord spec uses standard base64 for the `signature.content` field.
 */
function signArtifact(artifactBytes: Buffer, privateKeyPem: string): string {
  const signer = createSign("SHA256");
  signer.update(artifactBytes);
  signer.end();
  return signer.sign(privateKeyPem, "base64");
}

/**
 * Encode a HashedRekordBody object to the base64 string that Rekor expects
 * as the `body` field in the POST request.
 */
function encodeBody(body: HashedRekordBody): string {
  return Buffer.from(JSON.stringify(body)).toString("base64");
}

// ---------------------------------------------------------------------------
// Core: submit
// ---------------------------------------------------------------------------

/**
 * Submit a DSSE envelope to the Sigstore Rekor public transparency log.
 *
 * Flow:
 *   1. Decode DSSE payload bytes
 *   2. Compute SHA-256 hash of payload bytes
 *   3. Sign payload bytes with ECDSA-P256 (dev key) or Fulcio (keyless)
 *   4. Build hashedrekord body
 *   5. POST to /api/v1/log/entries
 *   6. Extract UUID, logIndex, inclusionProof
 *   7. Return RekorSubmitResult for JSONL side-car
 *
 * @param envelope  - SZL DSSE receipt envelope
 * @param opts      - signing + endpoint options
 * @returns         - Rekor submission metadata
 */
export async function submitDSSEToRekor(
  envelope: DSSEEnvelope,
  opts: RekorSubmitOptions = {}
): Promise<RekorSubmitResult> {
  const base = opts.staging ? REKOR_STAGING_BASE : REKOR_BASE;
  const url = `${base}/api/${API_VERSION}/log/entries`;

  // 1. Decode payload bytes (DSSE payload field is base64url)
  const payloadBytes = decodeBase64url(envelope.payload);

  // 2. Hash
  const hashHex = sha256Hex(payloadBytes);

  // 3. Sign
  let sigB64: string;
  let pubKeyPem: string;

  if (opts.signingKeyPem && opts.publicKeyPem) {
    sigB64 = signArtifact(payloadBytes, opts.signingKeyPem);
    pubKeyPem = opts.publicKeyPem;
  } else {
    // STAGED-ADVISORY: Fulcio keyless path — requires real OIDC token
    // In a GitHub Actions environment this token is obtained via:
    //   const { getIDToken } = await import("@actions/core");
    //   const oidcToken = await getIDToken("sigstore");
    // Then exchanged via https://fulcio.sigstore.dev/api/v2/signingCert
    // for an ephemeral X.509 cert.  The cert's SAN encodes the workflow identity.
    throw new Error(
      "STAGED-ADVISORY: Fulcio keyless signing not yet wired. " +
        "Provide signingKeyPem + publicKeyPem for dev mode, or set oidcToken for CI."
    );
  }

  // 4. Build hashedrekord body
  const body: HashedRekordBody = {
    apiVersion: "0.0.1",
    kind: "hashedrekord",
    spec: {
      data: {
        hash: {
          algorithm: "sha256",
          value: hashHex,
        },
      },
      signature: {
        content: sigB64,
        publicKey: {
          // Rekor expects base64-encoded PEM (the PEM string itself, base64-encoded)
          content: Buffer.from(pubKeyPem).toString("base64"),
        },
      },
    },
  };

  // 5. POST to Rekor
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    opts.timeoutMs ?? 10_000
  );

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        body: encodeBody(body),
      }),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    const text = await response.text();
    throw new Error(
      `Rekor submission failed: HTTP ${response.status} — ${text}`
    );
  }

  const entry = (await response.json()) as RekorEntry;

  // 6. Extract UUID (the single key in the response object)
  const uuid = Object.keys(entry)[0];
  if (!uuid) throw new Error("Rekor returned empty entry object");

  const entryData = entry[uuid];
  const logIndex = entryData.logIndex;
  const integratedTime = entryData.integratedTime;

  // Extract treeID from the logID (treeID is embedded in Rekor's logID for sharded logs)
  // logID is the hex-encoded SHA-256 of the log's public key — not the treeID.
  // For the public instance treeID is in the /api/v1/log response.
  // We embed the uuid (which encodes treeID+logIndex) as the canonical reference.
  const treeID = uuid.split("").slice(0, 16).join(""); // first 16 hex chars = treeID portion

  const rootHash =
    entryData.verification?.inclusionProof?.rootHash ?? "pending";

  const result: RekorSubmitResult = {
    uuid,
    logIndex,
    integratedTime,
    treeID,
    inclusionProofRootHash: rootHash,
    rekorEntryUrl: `${base}/api/${API_VERSION}/log/entries/${uuid}`,
    payloadHash: hashHex,
    submittedAt: new Date().toISOString(),
  };

  return result;
}

// ---------------------------------------------------------------------------
// JSONL side-car emitter
// ---------------------------------------------------------------------------

/**
 * Augment an existing SZL receipt JSONL line with Rekor attestation metadata.
 *
 * The augmented record is suitable for appending to the JSONL chain and acts
 * as an independently auditable anchor: any party holding the receipt can
 * reproduce the Rekor inclusion proof via:
 *   rekor-cli get --uuid <uuid> --rekor_server https://rekor.sigstore.dev
 */
export function augmentReceiptWithRekor(
  receipt: Record<string, unknown>,
  rekorResult: RekorSubmitResult
): Record<string, unknown> {
  return {
    ...receipt,
    rekorAttestation: {
      uuid: rekorResult.uuid,
      logIndex: rekorResult.logIndex,
      integratedTime: rekorResult.integratedTime,
      inclusionProofRootHash: rekorResult.inclusionProofRootHash,
      entryUrl: rekorResult.rekorEntryUrl,
      payloadHash: rekorResult.payloadHash,
      submittedAt: rekorResult.submittedAt,
      // Verification command for auditors:
      verifyCmd: `rekor-cli get --uuid ${rekorResult.uuid} --rekor_server https://rekor.sigstore.dev`,
    },
  };
}

// ---------------------------------------------------------------------------
// Pepr policy hook (exported for use in Pepr admission controller)
// ---------------------------------------------------------------------------

/**
 * Pepr-compatible policy hook.  Drop this into a Pepr When().Mutate() chain.
 *
 * Usage in Pepr policy file:
 *   import { emitRekorAttestation } from "./sigstore/rekor_submit";
 *
 *   When(SZLReceipt).IsCreated().Mutate(async (receipt) => {
 *     const result = await emitRekorAttestation(receipt.Raw.spec.envelope, peprOpts);
 *     receipt.SetAnnotation("szl.io/rekor-uuid", result.uuid);
 *     receipt.SetAnnotation("szl.io/rekor-log-index", String(result.logIndex));
 *   });
 */
export async function emitRekorAttestation(
  envelope: DSSEEnvelope,
  opts: RekorSubmitOptions
): Promise<RekorSubmitResult> {
  return submitDSSEToRekor(envelope, opts);
}

// ---------------------------------------------------------------------------
// CLI entry point (ts-node / tsx)
// ---------------------------------------------------------------------------

if (import.meta.url === `file://${process.argv[1]}`) {
  (async () => {
    const envelopePath = process.argv[2];
    if (!envelopePath) {
      console.error("Usage: tsx rekor_submit.ts <envelope.json> [--staging]");
      process.exit(1);
    }
    const envelope: DSSEEnvelope = JSON.parse(readFileSync(envelopePath, "utf8"));
    const { privateKeyPem, publicKeyPem } = generateDevKeyPair();
    const staging = process.argv.includes("--staging");

    console.log("Submitting DSSE envelope to Rekor...");
    const result = await submitDSSEToRekor(envelope, {
      signingKeyPem: privateKeyPem,
      publicKeyPem,
      staging,
    });

    console.log(JSON.stringify(result, null, 2));
    console.log(`\nVerify with:\n  ${result.rekorEntryUrl}`);
  })().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
