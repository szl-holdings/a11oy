/**
 * uds/pepr/governance-receipts-pqc.ts
 *
 * SZL Holdings — PQC-upgraded governance receipt signing
 * ML-DSA-65 (FIPS 204) + HMAC-SHA-256 dual-sign transition
 *
 * STAGED-ADVISORY: v0.4.0-alpha.1
 * Doctrine v6 | DoD NSM-10 / CNSA 2.0 aligned
 *
 * Install: npm install @noble/post-quantum
 *
 * Usage:
 *   const { envelope, receiptDigest } = await signReceiptDualSign(receipt, hmacKey, pqcSecretKey);
 *   const { hmacValid, pqcValid } = verifyReceiptDualSign(envelope, hmacKey, pqcPublicKey);
 */

import { createHmac, createHash, timingSafeEqual } from "node:crypto";
import { ml_dsa65 } from "@noble/post-quantum/ml-dsa.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface GovernanceReceiptV1 {
  receipt_id: string;
  schema_version: "1.0";
  timestamp: string;
  organ_id: string;
  organ_version: string;
  cluster_id: string;
  namespace: string;
  action: "ADMIT" | "DENY" | "MUTATE";
  resource_kind: string;
  resource_name: string;
  pepr_controller_version: string;
  slsa_level: 1 | 3;
  attestation_uri?: string;
  metadata?: Record<string, unknown>;
}

export interface GovernanceReceiptV11 extends Omit<GovernanceReceiptV1, "schema_version"> {
  schema_version: "1.1";
  pqc_signed: true;                    // always true for v1.1
  pqc_algorithm: "ml-dsa-65";
  pqc_fips_standard: "FIPS-204";
  pqc_public_key_id: string;           // keyid matching the signing key
}

export type GovernanceReceipt = GovernanceReceiptV1 | GovernanceReceiptV11;

export interface DsseSignature {
  keyid: string;
  sig: string;                         // base64url
  pqc_sig?: string;                    // base64url ML-DSA-65 sig (v0.4.0+)
  alg: "hmac-sha256" | "ml-dsa-65";
  pqc_alg?: "ml-dsa-65";
  pqc_public_key_uri?: string;
  fips_standard?: "FIPS-204";
}

export interface DsseEnvelopeV11 {
  payloadType: "application/vnd.szl.governance-receipt+json";
  payload: string;                     // base64url
  signatures: DsseSignature[];
  schema_version: "1.1";
}

export interface VerificationResult {
  hmacValid: boolean;
  pqcValid: boolean;
  bothValid: boolean;
  algorithms: string[];
  receipt: GovernanceReceipt;
  receiptDigest: string;               // SHA-256 hex of raw envelope
}

// ---------------------------------------------------------------------------
// Pre-Authentication Encoding (DSSE spec)
// ---------------------------------------------------------------------------

function buildPAE(payloadType: string, payloadB64: string): Buffer {
  const encodeWithLength = (s: string): Buffer => {
    const content = Buffer.from(s, "utf-8");
    const lenBuf = Buffer.alloc(8);
    lenBuf.writeBigUInt64LE(BigInt(content.length));
    return Buffer.concat([lenBuf, content]);
  };

  return Buffer.concat([
    Buffer.from("DSSEv1 ", "utf-8"),
    encodeWithLength(payloadType),
    Buffer.from(" ", "utf-8"),
    encodeWithLength(payloadB64),
  ]);
}

// ---------------------------------------------------------------------------
// base64url helpers
// ---------------------------------------------------------------------------

function b64urlEncode(buf: Buffer | Uint8Array): string {
  return Buffer.from(buf)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function b64urlDecode(s: string): Buffer {
  const padded = s + "==".slice(0, (4 - (s.length % 4)) % 4);
  return Buffer.from(padded.replace(/-/g, "+").replace(/_/g, "/"), "base64");
}

// ---------------------------------------------------------------------------
// Sign: HMAC-SHA-256 (legacy)
// ---------------------------------------------------------------------------

function signHmac(pae: Buffer, hmacKey: Uint8Array): string {
  return b64urlEncode(
    createHmac("sha256", hmacKey).update(pae).digest()
  );
}

// ---------------------------------------------------------------------------
// Sign: ML-DSA-65 (FIPS 204)
// ---------------------------------------------------------------------------

function signMlDsa65(pae: Buffer, secretKey: Uint8Array): string {
  const sig = ml_dsa65.sign(secretKey, pae);
  return b64urlEncode(sig);
}

// ---------------------------------------------------------------------------
// Verify: HMAC-SHA-256 (timing-safe)
// ---------------------------------------------------------------------------

function verifyHmac(pae: Buffer, sig: string, hmacKey: Uint8Array): boolean {
  try {
    const expected = createHmac("sha256", hmacKey).update(pae).digest();
    const actual = b64urlDecode(sig);
    if (expected.length !== actual.length) return false;
    return timingSafeEqual(expected, actual);
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Verify: ML-DSA-65 (FIPS 204)
// ---------------------------------------------------------------------------

function verifyMlDsa65(pae: Buffer, pqcSig: string, publicKey: Uint8Array): boolean {
  try {
    const sigBytes = b64urlDecode(pqcSig);
    return ml_dsa65.verify(publicKey, pae, sigBytes);
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Public API: Dual-sign (v0.4.0 transition)
// ---------------------------------------------------------------------------

/**
 * Sign a governance receipt with BOTH HMAC-SHA-256 AND ML-DSA-65.
 * Backward-compatible with v0.3.1 verifiers (they see the HMAC signature).
 * v0.4.0+ verifiers can also verify the ML-DSA-65 signature.
 */
export async function signReceiptDualSign(
  receipt: GovernanceReceiptV11,
  hmacKey: Uint8Array,
  pqcSecretKey: Uint8Array,
  opts?: {
    hmacKeyId?: string;
    pqcKeyId?: string;
    pqcPublicKeyUri?: string;
  }
): Promise<{ envelope: DsseEnvelopeV11; receiptDigest: string }> {
  const payloadType = "application/vnd.szl.governance-receipt+json";
  const payloadJson = JSON.stringify(receipt);
  const payloadB64 = b64urlEncode(Buffer.from(payloadJson, "utf-8"));
  const pae = buildPAE(payloadType, payloadB64);

  const hmacSig = signHmac(pae, hmacKey);
  const pqcSig = signMlDsa65(pae, pqcSecretKey);

  const envelope: DsseEnvelopeV11 = {
    payloadType,
    payload: payloadB64,
    schema_version: "1.1",
    signatures: [
      {
        keyid: opts?.hmacKeyId ?? "szl-hmac-v1",
        sig: hmacSig,
        alg: "hmac-sha256",
      },
      {
        keyid: opts?.pqcKeyId ?? "szl-mldsa65-v1",
        sig: "",                    // legacy field unused for PQC
        pqc_sig: pqcSig,
        alg: "ml-dsa-65",
        pqc_alg: "ml-dsa-65",
        pqc_public_key_uri: opts?.pqcPublicKeyUri ?? "k8s://szl-organs/szl-pqc-pubkeys-v1",
        fips_standard: "FIPS-204",
      },
    ],
  };

  const envelopeJson = JSON.stringify(envelope);
  const receiptDigest = createHash("sha256").update(envelopeJson).digest("hex");

  return { envelope, receiptDigest };
}

/**
 * Sign a governance receipt with ML-DSA-65 ONLY (v0.5.0 PQC-primary path).
 * Use ONLY after all consumers are updated to support ML-DSA-65 verification.
 */
export async function signReceiptPqcOnly(
  receipt: GovernanceReceiptV11,
  pqcSecretKey: Uint8Array,
  opts?: {
    pqcKeyId?: string;
    pqcPublicKeyUri?: string;
  }
): Promise<{ envelope: DsseEnvelopeV11; receiptDigest: string }> {
  const payloadType = "application/vnd.szl.governance-receipt+json";
  const payloadJson = JSON.stringify(receipt);
  const payloadB64 = b64urlEncode(Buffer.from(payloadJson, "utf-8"));
  const pae = buildPAE(payloadType, payloadB64);

  const pqcSig = signMlDsa65(pae, pqcSecretKey);

  const envelope: DsseEnvelopeV11 = {
    payloadType,
    payload: payloadB64,
    schema_version: "1.1",
    signatures: [
      {
        keyid: opts?.pqcKeyId ?? "szl-mldsa65-v1",
        sig: "",
        pqc_sig: pqcSig,
        alg: "ml-dsa-65",
        pqc_alg: "ml-dsa-65",
        pqc_public_key_uri: opts?.pqcPublicKeyUri ?? "k8s://szl-organs/szl-pqc-pubkeys-v1",
        fips_standard: "FIPS-204",
      },
    ],
  };

  const envelopeJson = JSON.stringify(envelope);
  const receiptDigest = createHash("sha256").update(envelopeJson).digest("hex");

  return { envelope, receiptDigest };
}

// ---------------------------------------------------------------------------
// Public API: Verify
// ---------------------------------------------------------------------------

/**
 * Verify a dual-sign envelope against both HMAC and ML-DSA-65.
 * Returns detailed result — caller decides policy (require both? either?).
 */
export function verifyReceiptDualSign(
  envelope: DsseEnvelopeV11,
  hmacKey: Uint8Array,
  pqcPublicKey: Uint8Array
): VerificationResult {
  const payloadType = envelope.payloadType;
  const pae = buildPAE(payloadType, envelope.payload);
  const validAlgorithms: string[] = [];

  let hmacValid = false;
  let pqcValid = false;

  for (const sig of envelope.signatures) {
    if (sig.alg === "hmac-sha256") {
      hmacValid = verifyHmac(pae, sig.sig, hmacKey);
      if (hmacValid) validAlgorithms.push("hmac-sha256");
    } else if (sig.alg === "ml-dsa-65" && sig.pqc_sig) {
      pqcValid = verifyMlDsa65(pae, sig.pqc_sig, pqcPublicKey);
      if (pqcValid) validAlgorithms.push("ml-dsa-65");
    }
  }

  const payloadJson = b64urlDecode(envelope.payload).toString("utf-8");
  const receipt = JSON.parse(payloadJson) as GovernanceReceipt;

  const envelopeJson = JSON.stringify(envelope);
  const receiptDigest = createHash("sha256").update(envelopeJson).digest("hex");

  return {
    hmacValid,
    pqcValid,
    bothValid: hmacValid && pqcValid,
    algorithms: validAlgorithms,
    receipt,
    receiptDigest,
  };
}

/**
 * Legacy verifier: only checks HMAC-SHA-256.
 * Use this to confirm backward-compat during transition.
 */
export function verifyReceiptLegacy(
  envelope: DsseEnvelopeV11,
  hmacKey: Uint8Array
): boolean {
  const pae = buildPAE(envelope.payloadType, envelope.payload);
  for (const sig of envelope.signatures) {
    if (sig.alg === "hmac-sha256") {
      return verifyHmac(pae, sig.sig, hmacKey);
    }
  }
  return false; // No HMAC signature present
}

// ---------------------------------------------------------------------------
// Key Management Helpers
// ---------------------------------------------------------------------------

/**
 * Generate a fresh ML-DSA-65 keypair.
 * In production: use HSM. This is for CI/dev use only.
 */
export function generateMlDsa65KeyPair(seed?: Uint8Array): {
  secretKey: Uint8Array;
  publicKey: Uint8Array;
  seedHex: string;
} {
  const { randomBytes } = require("node:crypto") as typeof import("node:crypto");
  const actualSeed = seed ?? randomBytes(32);
  const keys = ml_dsa65.keygen(actualSeed);
  return {
    secretKey: keys.secretKey,
    publicKey: keys.publicKey,
    seedHex: Buffer.from(actualSeed).toString("hex"),
  };
}

/**
 * Load ML-DSA-65 keypair from Kubernetes secret env vars.
 * Expects:
 *   SZL_PQC_SECRET_KEY=<base64 secret key>
 *   SZL_PQC_PUBLIC_KEY=<base64 public key>
 */
export function loadPqcKeysFromEnv(): {
  secretKey: Uint8Array | null;
  publicKey: Uint8Array | null;
} {
  const secretB64 = process.env.SZL_PQC_SECRET_KEY;
  const publicB64 = process.env.SZL_PQC_PUBLIC_KEY;

  return {
    secretKey: secretB64 ? Buffer.from(secretB64, "base64") : null,
    publicKey: publicB64 ? Buffer.from(publicB64, "base64") : null,
  };
}

/**
 * Load HMAC key from Kubernetes secret env var.
 * Expects: SZL_HMAC_KEY=<hex-encoded 32-byte key>
 */
export function loadHmacKeyFromEnv(): Uint8Array {
  const hex = process.env.SZL_HMAC_KEY;
  if (!hex) throw new Error("SZL_HMAC_KEY env var not set");
  return Buffer.from(hex, "hex");
}

// ---------------------------------------------------------------------------
// Receipt builder helpers (moved from governance-receipts.ts)
// ---------------------------------------------------------------------------

let receiptCounter = 0;

export function buildGovernanceReceipt(
  organ_id: string,
  organ_version: string,
  cluster_id: string,
  namespace: string,
  action: GovernanceReceipt["action"],
  resource_kind: string,
  resource_name: string,
  pepr_version: string,
  slsa_level: 1 | 3,
  attestation_uri?: string,
  metadata?: Record<string, unknown>
): GovernanceReceiptV11 {
  const pqcKeyId = "szl-mldsa65-v1";
  return {
    receipt_id: `szl-${Date.now()}-${++receiptCounter}-${Math.random().toString(36).slice(2, 8)}`,
    schema_version: "1.1",
    timestamp: new Date().toISOString(),
    organ_id,
    organ_version,
    cluster_id,
    namespace,
    action,
    resource_kind,
    resource_name,
    pepr_controller_version: pepr_version,
    slsa_level,
    attestation_uri,
    metadata,
    pqc_signed: true,
    pqc_algorithm: "ml-dsa-65",
    pqc_fips_standard: "FIPS-204",
    pqc_public_key_id: pqcKeyId,
  };
}

// ---------------------------------------------------------------------------
// Self-test
// ---------------------------------------------------------------------------

export async function runSelfTest(): Promise<void> {
  console.log("=== governance-receipts-pqc.ts self-test ===");

  const { randomBytes } = await import("node:crypto");

  // Keys
  const hmacKey = randomBytes(32);
  const { secretKey, publicKey, seedHex } = generateMlDsa65KeyPair();
  console.log(`✓ ML-DSA-65 keypair generated (seed: ${seedHex.slice(0, 16)}...)`);

  // Build receipt
  const receipt = buildGovernanceReceipt(
    "organ-a", "0.3.1", "test-cluster", "szl-organs",
    "ADMIT", "ConfigMap", "organ-a-dataset",
    "0.4.0", 3,
    "https://rekor.sigstore.dev/api/v1/log/entries?logIndex=99999"
  );
  console.log(`✓ Receipt built: ${receipt.receipt_id}`);

  // Dual-sign
  const { envelope, receiptDigest } = await signReceiptDualSign(receipt, hmacKey, secretKey);
  console.log(`✓ Dual-signed. Digest: ${receiptDigest.slice(0, 16)}...`);
  console.log(`  Algorithms: ${envelope.signatures.map(s => s.alg).join(", ")}`);

  // Full verification
  const result = verifyReceiptDualSign(envelope, hmacKey, publicKey);
  console.log(`✓ Full verify: hmac=${result.hmacValid} pqc=${result.pqcValid} both=${result.bothValid}`);
  if (!result.bothValid) throw new Error("Verification failed!");

  // Legacy verification (backward-compat check)
  const legacyValid = verifyReceiptLegacy(envelope, hmacKey);
  console.log(`✓ Legacy (HMAC-only) verify: ${legacyValid}`);
  if (!legacyValid) throw new Error("Legacy verification failed!");

  // Tamper detection
  const tampered = JSON.parse(JSON.stringify(envelope)) as DsseEnvelopeV11;
  tampered.payload = b64urlEncode(
    Buffer.from(JSON.stringify({ ...receipt, action: "DENY" }), "utf-8")
  );
  const tamperedResult = verifyReceiptDualSign(tampered, hmacKey, publicKey);
  console.log(`✓ Tamper detection: hmac=${tamperedResult.hmacValid} pqc=${tamperedResult.pqcValid} (both should be false)`);
  if (tamperedResult.hmacValid || tamperedResult.pqcValid) throw new Error("Tamper NOT detected!");

  // PQC-only (v0.5.0 path preview)
  const { envelope: pqcEnv } = await signReceiptPqcOnly(receipt, secretKey);
  const pqcOnlyVerify = verifyMlDsa65(
    buildPAE(pqcEnv.payloadType, pqcEnv.payload),
    pqcEnv.signatures[0].pqc_sig!,
    publicKey
  );
  console.log(`✓ PQC-only verify (v0.5.0 preview): ${pqcOnlyVerify}`);

  console.log("=== SELF-TEST PASSED ===");
}

function b64urlEncode(buf: Buffer | Uint8Array): string {
  return Buffer.from(buf).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

if (process.argv.includes("--self-test")) {
  runSelfTest().catch((e) => { console.error("SELF-TEST FAILED:", e); process.exit(1); });
}
