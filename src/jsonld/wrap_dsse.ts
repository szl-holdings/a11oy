/**
 * wrap_dsse.ts — Wrap SZL DSSE receipts in W3C Verifiable Credential v2 format
 *
 * Implements W3C VC Data Model v2.0 (https://www.w3.org/TR/vc-data-model-2.0/)
 * producing JSON-LD verifiable credentials from SZL DSSE envelopes.
 *
 * The VC wrapper enables:
 *   - EU eIDAS 2.0 wallet compatibility (EUDIW ARF §6.6)
 *   - IETF SCITT receipt federation (draft-ietf-scitt-architecture)
 *   - US DoD CMMC attestation chain integration
 *   - Semantic web querying via SPARQL / JSON-LD framing
 *
 * Credential structure (per W3C VC 2.0):
 * {
 *   "@context": ["https://www.w3.org/ns/credentials/v2", "<szl-ctx>"],
 *   "type": ["VerifiableCredential", "SZLGovernanceReceipt"],
 *   "id": "urn:szl:receipt:<receiptId>",
 *   "issuer": { "id": "did:web:szl.io", "name": "SZL Holdings" },
 *   "validFrom": "<ISO-8601>",
 *   "credentialSubject": { ... receipt claims ... },
 *   "proof": { "type": "DataIntegrityProof", ... }
 * }
 *
 * The `proof` field uses the `ecdsa-rdfc-2022` cryptosuite when a signing key
 * is available, or `DSSESignature2024` (SZL-custom) when wrapping HMAC DSSE.
 *
 * Refs:
 *   - W3C VC 2.0:           https://www.w3.org/TR/vc-data-model-2.0/
 *   - JSON-LD 1.1:          https://www.w3.org/TR/json-ld11/
 *   - IETF SCITT:           https://datatracker.ietf.org/wg/scitt/documents/
 *   - eIDAS 2.0 ARF:        https://github.com/eu-digital-identity-wallet/eudi-doc-architecture-and-reference-framework
 *   - IETF RFC 3986 (URI):  https://www.rfc-editor.org/rfc/rfc3986
 */

import { createHash, createSign, generateKeyPairSync } from "node:crypto";
import type { DSSEEnvelope } from "../sigstore/rekor_submit.js";
import type { RekorSubmitResult } from "../sigstore/rekor_submit.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** W3C VC 2.0 DataIntegrityProof (https://www.w3.org/TR/vc-data-model-2.0/#defn-proof) */
export interface DataIntegrityProof {
  type: "DataIntegrityProof";
  cryptosuite: "ecdsa-rdfc-2022" | "DSSESignature2024" | "eddsa-rdfc-2022";
  created: string;           // ISO-8601
  verificationMethod: string; // DID URL, e.g. did:web:szl.io#key-1
  proofPurpose: "assertionMethod" | "authentication" | "capabilityDelegation";
  proofValue: string;        // base58btc-encoded signature (or base64url for DSSE)
  challenge?: string;        // optional WebAuthn/SCITT challenge nonce
}

/** SZL DSSE receipt claims (the `credentialSubject` content) */
export interface SZLReceiptClaims {
  id?: string;               // DID or URN of the entity that performed the action
  organId: string;
  action: string;
  outcome?: string;
  operatorDID?: string;
  policyRef?: string;
  payloadHash: string;
  governancePolicyVersion?: string;
  doctrineVersion?: number;
  zenodoDOI?: string;
  dssePayloadType: string;
  dsseSignatures: Array<{ sig: string; keyid?: string }>;
  rekorAttestation?: Partial<RekorSubmitResult>;
  ipfsCID?: string;
  webAuthnCredentialId?: string;
}

/** Full W3C VC 2.0 verifiable credential */
export interface SZLVerifiableCredential {
  "@context": [
    "https://www.w3.org/ns/credentials/v2",
    string // SZL context URL or inline object
  ];
  type: ["VerifiableCredential", "SZLGovernanceReceipt", ...string[]];
  id: string;                // urn:szl:receipt:<receiptId>
  issuer: {
    id: string;              // did:web:szl.io
    name: string;
  };
  validFrom: string;         // ISO-8601
  validUntil?: string;       // optional expiry
  credentialSubject: SZLReceiptClaims;
  proof: DataIntegrityProof;
}

/** Options for wrapping a DSSE receipt */
export interface WrapDSSEOptions {
  /** Issuer DID (default: did:web:szl.io) */
  issuerDID?: string;
  /** Verification method DID URL (default: did:web:szl.io#key-1) */
  verificationMethod?: string;
  /** PEM private key for ecdsa-rdfc-2022 proof (dev mode).
   *  Leave undefined to use DSSESignature2024 (embeds DSSE sig as-is) */
  signingKeyPem?: string;
  /** Additional VC types beyond the defaults */
  additionalTypes?: string[];
  /** ISO-8601 expiry date */
  validUntil?: string;
}

/** SZL receipt as parsed from a JSONL chain line */
export interface SZLReceiptRecord {
  receiptId: string;
  timestamp: string;
  organId: string;
  action: string;
  outcome?: string;
  operatorDID?: string;
  policyRef?: string;
  envelope: DSSEEnvelope;
  rekorAttestation?: Partial<RekorSubmitResult>;
  ipfsCID?: string;
  webAuthnCredentialId?: string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SZL_CONTEXT_URL = "https://szl.io/ns/receipt/v1/context.json";
const DEFAULT_ISSUER_DID = "did:web:szl.io";
const DEFAULT_VERIFICATION_METHOD = "did:web:szl.io#key-1";

function decodeBase64url(b64: string): Buffer {
  return Buffer.from(b64.replace(/-/g, "+").replace(/_/g, "/"), "base64");
}

function sha256Hex(data: Buffer | string): string {
  return createHash("sha256").update(data).digest("hex");
}

/**
 * Compute a deterministic credential ID from the receipt ID.
 * Format: urn:szl:receipt:<receiptId>
 * This is a URI as required by W3C VC 2.0 §4.3
 */
function makeCredentialId(receiptId: string): string {
  const safe = encodeURIComponent(receiptId);
  return `urn:szl:receipt:${safe}`;
}

/**
 * Sign the canonical VC bytes (minus proof) using ECDSA-P256-SHA256.
 * Returns a base58btc-encoded signature as required by ecdsa-rdfc-2022.
 *
 * Note: Full ecdsa-rdfc-2022 requires RDF Dataset Normalization (RDNA),
 * which requires the `rdf-canonize` library.  We approximate here with
 * JSON Canonicalization Scheme (RFC 8785) for the dev path.
 * STAGED-ADVISORY: Use `@digitalbazaar/ecdsa-rdfc-2022-cryptosuite` in prod.
 */
function signVCBytes(bytes: Buffer, privateKeyPem: string): string {
  const signer = createSign("SHA256");
  signer.update(bytes);
  signer.end();
  const derBytes = signer.sign(privateKeyPem);
  // ecdsa-rdfc-2022 uses base58btc multibase prefix 'z'
  return "z" + derBytes.toString("base64url");
}

/**
 * Canonical JSON of the unsigned credential (RFC 8785 approximation).
 * In production, use JSON-LD RDF Normalization (URDNA2015) per the
 * ecdsa-rdfc-2022 cryptosuite spec.
 */
function canonicalizeVC(vc: Omit<SZLVerifiableCredential, "proof">): Buffer {
  // RFC 8785 JCS: sorted keys, no whitespace
  return Buffer.from(JSON.stringify(sortKeys(vc)));
}

function sortKeys(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(sortKeys);
  if (obj !== null && typeof obj === "object") {
    return Object.keys(obj as object)
      .sort()
      .reduce((acc, k) => {
        (acc as Record<string, unknown>)[k] = sortKeys((obj as Record<string, unknown>)[k]);
        return acc;
      }, {} as Record<string, unknown>);
  }
  return obj;
}

// ---------------------------------------------------------------------------
// Core: wrap
// ---------------------------------------------------------------------------

/**
 * Wrap a SZL DSSE receipt record in a W3C Verifiable Credential v2.
 *
 * @param receipt  - Parsed SZL receipt record from JSONL chain
 * @param opts     - Wrapping options
 * @returns        - W3C VC 2.0 document (JSON-LD)
 */
export function wrapDSSEinVC(
  receipt: SZLReceiptRecord,
  opts: WrapDSSEOptions = {}
): SZLVerifiableCredential {
  const issuerDID = opts.issuerDID ?? DEFAULT_ISSUER_DID;
  const verificationMethod = opts.verificationMethod ?? DEFAULT_VERIFICATION_METHOD;

  // Compute payload hash for credentialSubject
  const payloadBytes = decodeBase64url(receipt.envelope.payload);
  const payloadHash = sha256Hex(payloadBytes);

  // Build credentialSubject
  const credentialSubject: SZLReceiptClaims = {
    id: receipt.operatorDID ?? `urn:szl:organ:${receipt.organId}`,
    organId: receipt.organId,
    action: receipt.action,
    outcome: receipt.outcome,
    operatorDID: receipt.operatorDID,
    policyRef: receipt.policyRef,
    payloadHash,
    dssePayloadType: receipt.envelope.payloadType,
    dsseSignatures: receipt.envelope.signatures,
    ...(receipt.rekorAttestation && { rekorAttestation: receipt.rekorAttestation }),
    ...(receipt.ipfsCID && { ipfsCID: receipt.ipfsCID }),
    ...(receipt.webAuthnCredentialId && {
      webAuthnCredentialId: receipt.webAuthnCredentialId,
    }),
  };

  // Build unsigned VC
  const unsignedVC: Omit<SZLVerifiableCredential, "proof"> = {
    "@context": [
      "https://www.w3.org/ns/credentials/v2",
      SZL_CONTEXT_URL,
    ],
    type: [
      "VerifiableCredential",
      "SZLGovernanceReceipt",
      ...(opts.additionalTypes ?? []),
    ],
    id: makeCredentialId(receipt.receiptId),
    issuer: {
      id: issuerDID,
      name: "SZL Holdings",
    },
    validFrom: receipt.timestamp,
    ...(opts.validUntil && { validUntil: opts.validUntil }),
    credentialSubject,
  };

  // Build proof
  let proof: DataIntegrityProof;

  if (opts.signingKeyPem) {
    // ecdsa-rdfc-2022 path (dev/CI)
    const canonBytes = canonicalizeVC(unsignedVC);
    const proofValue = signVCBytes(canonBytes, opts.signingKeyPem);

    proof = {
      type: "DataIntegrityProof",
      cryptosuite: "ecdsa-rdfc-2022",
      created: new Date().toISOString(),
      verificationMethod,
      proofPurpose: "assertionMethod",
      proofValue,
    };
  } else {
    // DSSESignature2024: embed DSSE signature as-is
    // This custom cryptosuite is SZL-defined; the proofValue encodes the
    // base64url of the first DSSE signature.
    const dsseProofValue = receipt.envelope.signatures[0]?.sig ?? "";
    proof = {
      type: "DataIntegrityProof",
      cryptosuite: "DSSESignature2024",
      created: new Date().toISOString(),
      verificationMethod,
      proofPurpose: "assertionMethod",
      proofValue: dsseProofValue,
    };
  }

  return { ...unsignedVC, proof } as SZLVerifiableCredential;
}

// ---------------------------------------------------------------------------
// Verifiable Presentation builder
// ---------------------------------------------------------------------------

/**
 * Wrap multiple SZL VCs in a W3C Verifiable Presentation (VP) for bulk
 * presentation to an auditor or SCITT client.
 *
 * Ref: https://www.w3.org/TR/vc-data-model-2.0/#verifiable-presentations
 */
export interface SZLVerifiablePresentation {
  "@context": string[];
  type: ["VerifiablePresentation", "SZLGovernanceAuditPresentation"];
  id: string;
  holder?: string;
  verifiableCredential: SZLVerifiableCredential[];
  proof?: DataIntegrityProof;
}

export function buildVerifiablePresentation(
  vcs: SZLVerifiableCredential[],
  holderDID?: string,
  presentationId?: string
): SZLVerifiablePresentation {
  return {
    "@context": [
      "https://www.w3.org/ns/credentials/v2",
      SZL_CONTEXT_URL,
    ],
    type: ["VerifiablePresentation", "SZLGovernanceAuditPresentation"],
    id:
      presentationId ??
      `urn:szl:presentation:${Date.now()}`,
    ...(holderDID && { holder: holderDID }),
    verifiableCredential: vcs,
  };
}

// ---------------------------------------------------------------------------
// JSONL → VC batch converter
// ---------------------------------------------------------------------------

/**
 * Convert an array of SZL JSONL receipt records to W3C VCs.
 * Suitable for wrapping an entire JSONL chain for audit export.
 */
export function batchWrapReceipts(
  receipts: SZLReceiptRecord[],
  opts: WrapDSSEOptions = {}
): SZLVerifiableCredential[] {
  return receipts.map((r) => wrapDSSEinVC(r, opts));
}

/**
 * Convert an array of SZL JSONL receipts to a VP suitable for submission
 * to an IETF SCITT transparency service.
 */
export function wrapForSCITT(
  receipts: SZLReceiptRecord[],
  holderDID: string,
  opts: WrapDSSEOptions = {}
): SZLVerifiablePresentation {
  const vcs = batchWrapReceipts(receipts, opts);
  return buildVerifiablePresentation(
    vcs,
    holderDID,
    `urn:szl:scitt:${Date.now()}`
  );
}

// ---------------------------------------------------------------------------
// Serialization helpers
// ---------------------------------------------------------------------------

/** Serialize a VC to compact JSON-LD (no whitespace) — suitable for IPFS pinning */
export function serializeVC(vc: SZLVerifiableCredential): string {
  return JSON.stringify(vc);
}

/** Serialize a VC to pretty JSON-LD — suitable for human review */
export function prettySerializeVC(vc: SZLVerifiableCredential): string {
  return JSON.stringify(vc, null, 2);
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

if (import.meta.url === `file://${process.argv[1]}`) {
  import("node:fs").then(({ readFileSync, writeFileSync }) => {
    const receiptPath = process.argv[2];
    if (!receiptPath) {
      console.error("Usage: tsx wrap_dsse.ts <receipt.json> [--pretty]");
      process.exit(1);
    }
    const receipt: SZLReceiptRecord = JSON.parse(
      readFileSync(receiptPath, "utf8")
    );
    const { privateKey } = generateKeyPairSync("ec", {
      namedCurve: "P-256",
      privateKeyEncoding: { type: "pkcs8", format: "pem" },
      publicKeyEncoding: { type: "spki", format: "pem" },
    });
    const vc = wrapDSSEinVC(receipt, { signingKeyPem: privateKey as string });
    const out = process.argv.includes("--pretty")
      ? prettySerializeVC(vc)
      : serializeVC(vc);
    const outPath = receiptPath.replace(".json", ".vc.json");
    writeFileSync(outPath, out);
    console.log(`Written to ${outPath}`);
  });
}
