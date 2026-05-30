/**
 * @file packages/rae1/src/hmac.ts
 * @description RAE-1 DSSE HMAC-SHA-256 signature gate.
 *
 * Implements the PAE (Pre-Authentication Encoding) function and HMAC verification
 * for DSSE envelopes per RAE_1_PROTOCOL.md §5.3 and the DSSE spec
 * (github.com/secure-systems-lab/dsse).
 *
 * PAE formula:
 *   PAE(type, payload) = LE64(2) || LE64(len(type)) || type
 *                      || LE64(len(payload)) || payload
 *
 * where LE64(x) is x encoded as a little-endian 64-bit unsigned integer.
 *
 * The signature in each DSSEEnvelope.signatures[i].sig is:
 *   base64url(HMAC-SHA-256(key, PAE(payloadType, payload)))
 *
 * Lean ref:  SZL.AGI.PACBayes.capability_improvement_rate_bound
 * Lean file: Lutar/PACBayes/CapabilityImprovementRate.lean
 * Lean commit: c4d1379568
 *
 * Doctrine v6 — no fake green, real HMAC-SHA-256.
 * Signed-off-by: SZL Engineering <eng@szl-holdings.com>
 */

import { createHmac } from "crypto";

// ─── PAE (Pre-Authentication Encoding) ───────────────────────────────────────

/**
 * DSSE Pre-Authentication Encoding (PAE).
 *
 * Encodes a variable number of byte strings into a single buffer for
 * use as HMAC input, preventing cross-type forgery attacks.
 *
 * For RAE-1, always called with exactly 2 items: [payloadType, payload].
 *
 * Layout (per DSSE spec v1):
 *   LE64(count)
 *   LE64(len(item_0)) || item_0
 *   LE64(len(item_1)) || item_1
 *   ...
 *
 * @param items - Array of string items to encode
 * @returns Buffer containing the PAE encoding
 *
 * @example
 * ```typescript
 * const encoded = pae(["application/vnd.szl.rae1+json", base64urlPayload]);
 * const sig = createHmac("sha256", key).update(encoded).digest("base64url");
 * ```
 */
export function pae(items: string[]): Buffer {
  const itemBuffers = items.map((item) => Buffer.from(item, "utf8"));

  // Total size: 8 (count) + sum_i(8 + len(item_i))
  const totalSize =
    8 + itemBuffers.reduce((acc, buf) => acc + 8 + buf.length, 0);

  const result = Buffer.alloc(totalSize);
  let offset = 0;

  // Write count as LE64
  result.writeBigUInt64LE(BigInt(items.length), offset);
  offset += 8;

  // Write each item: LE64(len) || bytes
  for (const buf of itemBuffers) {
    result.writeBigUInt64LE(BigInt(buf.length), offset);
    offset += 8;
    buf.copy(result, offset);
    offset += buf.length;
  }

  return result;
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
  const expected = createHmac("sha256", key).update(message).digest("base64url");
  return envelope.signatures.some((s) => s.sig === expected);
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
