/**
 * @file packages/rae1/src/hmac.ts
 * @description RAE-1 DSSE HMAC-SHA-256 signature gate.
 *
 * Implements HMAC-SHA-256 verification over the canonical DSSE v1
 * Pre-Authentication Encoding (PAE) for DSSE envelopes, per RAE_1_PROTOCOL.md
 * §5.3 and the DSSE spec
 * (https://github.com/secure-systems-lab/dsse/blob/master/protocol.md).
 *
 * Canonical PAE formula (the ONLY one used across SZL — see ./dsse-pae.ts):
 *   PAE = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
 *   SP  = 0x20, LEN = ASCII decimal byte length, body = RAW envelope body.
 *
 * The DSSE envelope `payload` field is base64url of the raw body, so the PAE is
 * computed over the base64-DECODED body (dsseV1PaeFromBase64Body).
 *
 * The signature in each DSSEEnvelope.signatures[i].sig is:
 *   base64url(HMAC-SHA-256(key, dsseV1PaeFromBase64Body(payloadType, payload)))
 *
 * NOTE: prior to PR fix(rae1) this file used the old in-toto LE64 binary PAE,
 * which has no "DSSEv1" prefix and is not DSSEv1-compatible
 * (PhD_CRYPTO_VERDICT.md Finding A1, hmac.ts:53-76).
 *
 * Lean ref:  SZL.AGI.PACBayes.capability_improvement_rate_bound
 * Lean file: Lutar/PACBayes/CapabilityImprovementRate.lean
 * Lean commit: c4d1379568
 *
 * Doctrine v6 — no fake green, real HMAC-SHA-256.
 * Signed-off-by: SZL Engineering <eng@szl-holdings.com>
 */

import { createHmac, timingSafeEqual } from "crypto";
import { dsseV1Pae, dsseV1PaeFromBase64Body } from "./dsse-pae.js";

// ─── PAE (Pre-Authentication Encoding) ───────────────────────────────────────

/**
 * Canonical DSSE v1 PAE for an [payloadType, base64Body] item pair.
 *
 * Backward-compatible call shape: callers historically invoked
 *   pae([payloadType, base64Payload])
 * where the second item is the envelope's base64url `payload` field. The PAE is
 * now computed over the RAW (base64-decoded) body, per the DSSE spec.
 *
 * @param items - exactly [payloadType, base64Body]
 * @returns Buffer containing the canonical DSSE v1 PAE
 *
 * @example
 * ```typescript
 * const encoded = pae(["application/vnd.szl.rae1+json", base64urlPayload]);
 * const sig = createHmac("sha256", key).update(encoded).digest("base64url");
 * ```
 */
export function pae(items: string[]): Buffer {
  if (items.length !== 2) {
    throw new Error(
      `DSSE v1 PAE requires exactly [payloadType, base64Body]; got ${items.length} items`
    );
  }
  const [payloadType, base64Body] = items;
  return Buffer.from(dsseV1PaeFromBase64Body(payloadType, base64Body));
}

/**
 * Canonical DSSE v1 PAE over a payload type and RAW body bytes.
 * Re-exported convenience for callers that already hold raw bytes.
 */
export function paeRaw(payloadType: string, body: Uint8Array): Buffer {
  return Buffer.from(dsseV1Pae(payloadType, body));
}

// ─── HMAC Verification ───────────────────────────────────────────────────────

/**
 * Verifies the DSSE HMAC-SHA-256 signature on a single RAE-1 receipt envelope.
 *
 * Checks all signatures in the envelope; returns true if any signature matches
 * the provided key (following the DSSE multi-signer model).
 *
 * Algorithm:
 *   1. Compute PAE([envelope.payloadType, envelope.payload])
 *   2. Compute expected = HMAC-SHA-256(key, PAE_result) → base64url
 *   3. Return true if any signature in envelope.signatures has sig === expected
 *
 * Lean ref: SZL.AGI.PACBayes.capability_improvement_rate_bound
 *           file: Lutar/PACBayes/CapabilityImprovementRate.lean
 *           commit: c4d1379568
 *
 * @param envelope - DSSE envelope with payloadType, payload, and signatures
 * @param key      - Raw HMAC key as a Buffer
 * @returns True if at least one signature is valid for the provided key
 *
 * @example
 * ```typescript
 * const key = Buffer.from(process.env.RAE1_HMAC_KEY!, "base64url");
 * const valid = verifyHMAC(envelope, key);
 * if (!valid) throw new Error("Receipt signature verification failed");
 * ```
 */
export function verifyHMAC(
  envelope: {
    payloadType: string;
    payload: string;
    signatures: Array<{ keyid: string; sig: string }>;
  },
  key: Buffer
): boolean {
  const message = pae([envelope.payloadType, envelope.payload]);
  const expected = createHmac("sha256", key).update(message).digest();
  // Timing-safe comparison over the raw MAC bytes (PhD_CRYPTO_VERDICT.md
  // "Positive" nit: hmac.ts:116 previously used `===` string compare on the
  // public tag). Decode each candidate signature and compare in constant time.
  return envelope.signatures.some((s) => {
    let actual: Buffer;
    try {
      actual = Buffer.from(s.sig, "base64url");
    } catch {
      return false;
    }
    if (actual.length !== expected.length) return false;
    return timingSafeEqual(actual, expected);
  });
}

/**
 * Signs a DSSE envelope with HMAC-SHA-256, adding a signature entry.
 *
 * Returns a new envelope with the signature appended; does not mutate the input.
 *
 * @param envelope - Existing envelope (with or without prior signatures)
 * @param key      - Raw HMAC key as a Buffer
 * @param keyid    - Key identifier in format "hmac-sha256:<sha256-of-key-material>"
 * @returns New envelope with the HMAC signature added to signatures array
 */
export function signEnvelope<T extends {
  payloadType: string;
  payload: string;
  signatures: Array<{ keyid: string; sig: string }>;
}>(
  envelope: T,
  key: Buffer,
  keyid: string
): T {
  const message = pae([envelope.payloadType, envelope.payload]);
  const sig = createHmac("sha256", key).update(message).digest("base64url");
  return {
    ...envelope,
    signatures: [...envelope.signatures, { keyid, sig }],
  };
}

/**
 * Generates a key ID string for an HMAC key.
 *
 * Format per RAE-1 §2.1: "hmac-sha256:<sha256-of-key-material>"
 * where the sha256 is the hex digest of the raw key bytes.
 *
 * @param key - Raw HMAC key as a Buffer
 * @returns keyid string
 */
export function makeKeyId(key: Buffer): string {
  const { createHash } = require("crypto");
  const keyHash = createHash("sha256").update(key).digest("hex");
  return `hmac-sha256:${keyHash}`;
}
