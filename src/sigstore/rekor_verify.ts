/**
 * rekor_verify.ts — Verify Rekor entry round-trip for SZL DSSE receipts
 *
 * Fetches a previously submitted Rekor entry by UUID, re-validates the
 * inclusion proof against the current signed tree head (STH), and confirms
 * the payload hash in the entry matches the locally held DSSE envelope.
 *
 * Round-trip verification flow (per Rekor transparency log guarantees):
 *   1. Fetch entry by UUID from /api/v1/log/entries/<uuid>
 *   2. Decode the base64-encoded body and confirm `kind` + `apiVersion`
 *   3. Confirm SHA-256 hash in body matches local payload hash
 *   4. Verify the Signed Entry Timestamp (SET) signature against the
 *      Rekor public key — this is the cryptographic timestamp proof
 *   5. Optionally verify the Merkle inclusion proof against a fetched STH
 *
 * Refs:
 *   - Rekor verification: https://docs.sigstore.dev/logging/overview/
 *   - RFC 6962 (CT):      https://www.rfc-editor.org/rfc/rfc6962 (Merkle proofs)
 *   - Rekor public key:   https://rekor.sigstore.dev/api/v1/log/publicKey
 */

import { createHash, createVerify } from "node:crypto";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface VerifyOptions {
  /** Rekor base URL (default: https://rekor.sigstore.dev) */
  rekorBase?: string;
  /** Timeout in ms (default: 10000) */
  timeoutMs?: number;
  /** If true, also verify Merkle inclusion proof (requires fetching STH) */
  verifyMerkle?: boolean;
}

export interface VerifyResult {
  uuid: string;
  verified: boolean;
  logIndex: number;
  integratedTime: number;
  integratedTimeISO: string;
  payloadHashMatch: boolean;
  setSignatureValid: boolean;
  merkleProofValid: boolean | "skipped";
  errorMessage?: string;
  rekorEntryUrl: string;
}

interface RawRekorEntry {
  body: string;
  integratedTime: number;
  logID: string;
  logIndex: number;
  verification: {
    inclusionProof?: {
      checkpoint: string;
      hashes: string[];
      logIndex: number;
      rootHash: string;
      treeSize: number;
    };
    signedEntryTimestamp: string;
  };
}

interface HashedRekordSpec {
  data: { hash: { algorithm: string; value: string } };
  signature: { content: string; publicKey: { content: string } };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_REKOR_BASE = "https://rekor.sigstore.dev";

function decodeBase64(b64: string): Buffer {
  return Buffer.from(b64, "base64");
}

function decodeBase64url(b64: string): Buffer {
  return Buffer.from(b64.replace(/-/g, "+").replace(/_/g, "/"), "base64");
}

function sha256Hex(data: Buffer | string): string {
  return createHash("sha256").update(data).digest("hex");
}

async function fetchWithTimeout(
  url: string,
  opts: RequestInit,
  timeoutMs: number
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...opts, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Rekor public key fetcher
// ---------------------------------------------------------------------------

let _cachedRekorPublicKeyPem: string | null = null;

/**
 * Fetch the Rekor instance's ECDSA public key (used to verify SET signatures).
 * Cached in-process after first fetch.
 */
async function fetchRekorPublicKey(
  base: string,
  timeoutMs: number
): Promise<string> {
  if (_cachedRekorPublicKeyPem) return _cachedRekorPublicKeyPem;

  const resp = await fetchWithTimeout(
    `${base}/api/v1/log/publicKey`,
    { headers: { Accept: "application/x-pem-file" } },
    timeoutMs
  );
  if (!resp.ok) {
    throw new Error(
      `Failed to fetch Rekor public key: HTTP ${resp.status}`
    );
  }
  const pem = await resp.text();
  _cachedRekorPublicKeyPem = pem;
  return pem;
}

// ---------------------------------------------------------------------------
// SET signature verification
// ---------------------------------------------------------------------------

/**
 * Verify the Signed Entry Timestamp (SET) against Rekor's ECDSA public key.
 *
 * The SET is a base64-encoded signature over the canonical JSON of the entry
 * (body + integratedTime + logID + logIndex).  This is the primary
 * cryptographic timestamp proof — it proves Rekor's private key witnessed
 * the entry at `integratedTime`.
 *
 * SET format reference: https://github.com/sigstore/rekor/blob/main/pkg/api/entries.go
 */
async function verifySET(
  entry: RawRekorEntry,
  rekorPublicKeyPem: string
): Promise<boolean> {
  try {
    // Canonical bytes signed by Rekor to produce the SET:
    const canonicalEntry = {
      body: entry.body,
      integratedTime: entry.integratedTime,
      logID: entry.logID,
      logIndex: entry.logIndex,
    };
    const canonicalBytes = Buffer.from(JSON.stringify(canonicalEntry));

    const setBytes = decodeBase64(entry.verification.signedEntryTimestamp);

    const verifier = createVerify("SHA256");
    verifier.update(canonicalBytes);
    verifier.end();
    return verifier.verify(rekorPublicKeyPem, setBytes);
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Merkle inclusion proof verification (RFC 6962 §2.1.3)
// ---------------------------------------------------------------------------

/**
 * Verify a Merkle inclusion proof against the claimed root hash.
 *
 * Rekor provides the leaf hash and a sequence of sibling hashes
 * (audit path).  We reconstruct the root hash bottom-up using the
 * RFC 6962 node hashing rules:
 *   - Leaf node:  SHA-256(0x00 || leaf_data)
 *   - Inner node: SHA-256(0x01 || left_hash || right_hash)
 *
 * Ref: https://www.rfc-editor.org/rfc/rfc6962#section-2.1
 */
function verifyMerkleInclusionProof(
  leafHash: Buffer,
  auditPath: string[],
  leafIndex: number,
  treeSize: number,
  expectedRootHash: string
): boolean {
  try {
    let hash = leafHash;
    let idx = leafIndex;
    let lastNode = treeSize - 1;

    for (const sibling of auditPath) {
      const siblingBytes = Buffer.from(sibling, "hex");
      if (idx % 2 === 1 || idx === lastNode) {
        // Current node is on the right (or is the rightmost node at this level)
        if (idx % 2 === 1) {
          // Sibling is on the left
          hash = createHash("sha256")
            .update(Buffer.from([0x01]))
            .update(siblingBytes)
            .update(hash)
            .digest();
        } else {
          // Rightmost node: promote without sibling
          hash = createHash("sha256")
            .update(Buffer.from([0x01]))
            .update(hash)
            .update(siblingBytes)
            .digest();
        }
      } else {
        // Current node is on the left
        hash = createHash("sha256")
          .update(Buffer.from([0x01]))
          .update(hash)
          .update(siblingBytes)
          .digest();
      }
      idx = Math.floor(idx / 2);
      lastNode = Math.floor(lastNode / 2);
    }

    return hash.toString("hex") === expectedRootHash;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Core: verify
// ---------------------------------------------------------------------------

/**
 * Verify a Rekor entry round-trips correctly against a local DSSE envelope.
 *
 * @param uuid           - Rekor entry UUID (returned by rekor_submit.ts)
 * @param localPayloadB64 - base64url-encoded payload from the DSSE envelope
 *                          (envelope.payload field)
 * @param opts           - verification options
 */
export async function verifyRekorEntry(
  uuid: string,
  localPayloadB64: string,
  opts: VerifyOptions = {}
): Promise<VerifyResult> {
  const base = opts.rekorBase ?? DEFAULT_REKOR_BASE;
  const timeoutMs = opts.timeoutMs ?? 10_000;
  const entryUrl = `${base}/api/v1/log/entries/${uuid}`;

  const result: VerifyResult = {
    uuid,
    verified: false,
    logIndex: -1,
    integratedTime: -1,
    integratedTimeISO: "",
    payloadHashMatch: false,
    setSignatureValid: false,
    merkleProofValid: opts.verifyMerkle ? false : "skipped",
    rekorEntryUrl: entryUrl,
  };

  try {
    // 1. Fetch entry
    const resp = await fetchWithTimeout(
      entryUrl,
      { headers: { Accept: "application/json" } },
      timeoutMs
    );
    if (!resp.ok) {
      result.errorMessage = `HTTP ${resp.status} fetching entry`;
      return result;
    }

    const entryMap = (await resp.json()) as Record<string, RawRekorEntry>;
    const entry = entryMap[uuid];
    if (!entry) {
      result.errorMessage = "UUID not found in response";
      return result;
    }

    result.logIndex = entry.logIndex;
    result.integratedTime = entry.integratedTime;
    result.integratedTimeISO = new Date(entry.integratedTime * 1000).toISOString();

    // 2. Decode body and extract hashedrekord spec
    const bodyJson = JSON.parse(decodeBase64(entry.body).toString("utf8"));
    if (bodyJson.kind !== "hashedrekord" || bodyJson.apiVersion !== "0.0.1") {
      result.errorMessage = `Unexpected entry type: ${bodyJson.kind}@${bodyJson.apiVersion}`;
      return result;
    }
    const spec: HashedRekordSpec = bodyJson.spec;

    // 3. Compare payload hash
    const localPayloadBytes = decodeBase64url(localPayloadB64);
    const localHash = sha256Hex(localPayloadBytes);
    const rekorHash = spec.data.hash.value;
    result.payloadHashMatch = localHash === rekorHash;

    // 4. Verify SET
    const rekorPubKey = await fetchRekorPublicKey(base, timeoutMs);
    result.setSignatureValid = await verifySET(entry, rekorPubKey);

    // 5. Verify Merkle proof (optional but recommended for audit)
    if (opts.verifyMerkle && entry.verification?.inclusionProof) {
      const proof = entry.verification.inclusionProof;
      // Leaf hash = SHA-256(0x00 || base64-decode(body))
      const leafHash = createHash("sha256")
        .update(Buffer.from([0x00]))
        .update(decodeBase64(entry.body))
        .digest();

      result.merkleProofValid = verifyMerkleInclusionProof(
        leafHash,
        proof.hashes,
        proof.logIndex,
        proof.treeSize,
        proof.rootHash
      );
    }

    result.verified =
      result.payloadHashMatch &&
      result.setSignatureValid &&
      (result.merkleProofValid === "skipped" || result.merkleProofValid === true);
  } catch (e) {
    result.errorMessage = e instanceof Error ? e.message : String(e);
  }

  return result;
}

// ---------------------------------------------------------------------------
// Batch verifier — checks all Rekor UUIDs in a JSONL receipt chain
// ---------------------------------------------------------------------------

export interface BatchVerifyResult {
  totalReceipts: number;
  verified: number;
  failed: number;
  results: VerifyResult[];
}

/**
 * Verify all Rekor attestations in a parsed JSONL receipt array.
 * Each receipt must have a `rekorAttestation.uuid` and `envelope.payload` field.
 */
export async function batchVerifyReceipts(
  receipts: Array<{
    envelope?: DSSEEnvelopeRef;
    rekorAttestation?: { uuid: string };
  }>,
  opts: VerifyOptions = {}
): Promise<BatchVerifyResult> {
  const results: VerifyResult[] = [];

  for (const receipt of receipts) {
    if (!receipt.rekorAttestation?.uuid || !receipt.envelope?.payload) {
      continue;
    }
    const r = await verifyRekorEntry(
      receipt.rekorAttestation.uuid,
      receipt.envelope.payload,
      opts
    );
    results.push(r);
  }

  return {
    totalReceipts: results.length,
    verified: results.filter((r) => r.verified).length,
    failed: results.filter((r) => !r.verified).length,
    results,
  };
}

interface DSSEEnvelopeRef {
  payload: string;
  payloadType?: string;
}

// ---------------------------------------------------------------------------
// CLI entry point
// ---------------------------------------------------------------------------

if (import.meta.url === `file://${process.argv[1]}`) {
  (async () => {
    const uuid = process.argv[2];
    const payloadB64 = process.argv[3];

    if (!uuid || !payloadB64) {
      console.error("Usage: tsx rekor_verify.ts <uuid> <base64url-payload> [--merkle]");
      process.exit(1);
    }

    const verifyMerkle = process.argv.includes("--merkle");
    const result = await verifyRekorEntry(uuid, payloadB64, { verifyMerkle });

    console.log(JSON.stringify(result, null, 2));
    if (!result.verified) {
      process.exit(1);
    }
  })().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
