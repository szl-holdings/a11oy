/**
 * dsse_verify.ts - DSSE v1.0.2 Pre-Authentication Encoding and fail-closed
 * envelope verification.
 *
 * Why: wrap_dsse.ts and rekor_submit.ts build and carry DSSE envelopes but the
 * repo had no verifier that follows the DSSE protocol (and src/rae1/schema.ts and
 * a11oy/integrations/peat-bridge.ts describe/implement a different, non-standard
 * PAE). A signature made over a non-standard PAE cannot be checked by cosign,
 * in-toto, SLSA verifiers or any other DSSE implementation.
 *
 * Spec: https://github.com/secure-systems-lab/dsse/blob/master/protocol.md (v1.0.2)
 *   PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
 *   LEN = ASCII decimal byte length, no leading zeros.
 *
 * Verification rules implemented (protocol.md "Protocol" and "Multi-signature
 * Verification"):
 *   - either standard or URL-safe base64 is accepted, strictly (no mixed alphabets);
 *   - keyid is an unauthenticated hint and is NOT used for any security decision;
 *   - a (t, n) envelope is valid only if signatures verify under >= t UNIQUE
 *     trusted keys;
 *   - the payload type must be in the caller's allow-list (there is no default);
 *   - the verified payload bytes are returned; callers must use these bytes and
 *     must not re-parse the envelope.
 *
 * Self-contained (node:crypto only). Verifies only; it holds no signing code.
 */
import { createHmac, createPublicKey, timingSafeEqual, verify, type KeyObject } from "node:crypto";

export type DsseKeyAlgorithm = "ecdsa-p256-sha256-p1363" | "ecdsa-p256-sha256-der" | "ed25519" | "hmac-sha256";

export interface DsseTrustedKey {
  /** Caller's own identifier for the key; counted for uniqueness. Not taken from the envelope. */
  readonly id: string;
  readonly algorithm: DsseKeyAlgorithm;
  /** Public key (KeyObject or PEM) for the asymmetric algorithms. */
  readonly publicKey?: KeyObject | string;
  /** Shared secret for hmac-sha256 (caller-supplied; never logged here). */
  readonly secret?: Buffer;
}

export interface DsseVerifyOptions {
  readonly keys: readonly DsseTrustedKey[];
  /** Exact, case-sensitive payload types the caller is willing to accept. Required. */
  readonly acceptedPayloadTypes: readonly string[];
  /** t in a (t, n) envelope. Default 1. */
  readonly threshold?: number;
}

export interface DsseVerifyResult {
  readonly valid: boolean;
  readonly errors: readonly string[];
  readonly payloadType?: string;
  /** The exact bytes that were verified. */
  readonly payload?: Buffer;
  readonly acceptedKeyIds: readonly string[];
}

/** DSSE v1 Pre-Authentication Encoding over UTF-8 type and raw body bytes. */
export function dssePAE(payloadType: string, body: Buffer): Buffer {
  if (typeof payloadType !== "string" || !Buffer.isBuffer(body)) throw new Error("dssePAE: type must be a string and body a Buffer");
  if (!payloadType.isWellFormed()) throw new Error("dssePAE: payload type is not valid UTF-8");
  const type = Buffer.from(payloadType, "utf8");
  return Buffer.concat([
    Buffer.from(`DSSEv1 ${type.length} `, "ascii"),
    type,
    Buffer.from(` ${body.length} `, "ascii"),
    body,
  ]);
}

/** Strict base64 decode accepting either the standard or the URL-safe alphabet (not both), padded or not. */
export function decodeDsseBase64(text: unknown): Buffer | null {
  if (typeof text !== "string" || text.length === 0) return null;
  const hasStd = /[+/]/.test(text);
  const hasUrl = /[-_]/.test(text);
  if (hasStd && hasUrl) return null;
  const body = text.replace(/=+$/, "");
  const pad = text.length - body.length;
  if (pad > 2 || !/^[A-Za-z0-9+/\-_]+$/.test(body)) return null;
  if (body.length % 4 === 1) return null;
  if (pad > 0 && (body.length + pad) % 4 !== 0) return null;
  const decoded = Buffer.from(body.replace(/-/g, "+").replace(/_/g, "/"), "base64");
  // reject non-canonical trailing bits
  const canonical = decoded.toString("base64").replace(/=+$/, "");
  return canonical === body.replace(/-/g, "+").replace(/_/g, "/") ? decoded : null;
}

function verifyOne(key: DsseTrustedKey, signed: Buffer, signature: Buffer): boolean {
  try {
    switch (key.algorithm) {
      case "ecdsa-p256-sha256-p1363":
        return (
          signature.length === 64 &&
          key.publicKey !== undefined &&
          verify("sha256", signed, { key: typeof key.publicKey === "string" ? createPublicKey(key.publicKey) : key.publicKey, dsaEncoding: "ieee-p1363" }, signature)
        );
      case "ecdsa-p256-sha256-der":
        return (
          key.publicKey !== undefined &&
          verify("sha256", signed, { key: typeof key.publicKey === "string" ? createPublicKey(key.publicKey) : key.publicKey, dsaEncoding: "der" }, signature)
        );
      case "ed25519":
        return (
          signature.length === 64 &&
          key.publicKey !== undefined &&
          verify(null, signed, typeof key.publicKey === "string" ? createPublicKey(key.publicKey) : key.publicKey, signature)
        );
      case "hmac-sha256": {
        if (!key.secret || key.secret.length === 0) return false;
        const expected = createHmac("sha256", key.secret).update(signed).digest();
        return expected.length === signature.length && timingSafeEqual(expected, signature);
      }
      default:
        return false;
    }
  } catch {
    return false;
  }
}

/** Verify a DSSE JSON envelope. Never throws; any malformed input is a failed verification. */
export function verifyDSSEEnvelope(envelope: unknown, options: DsseVerifyOptions): DsseVerifyResult {
  const fail = (...errors: string[]): DsseVerifyResult => ({ valid: false, errors, acceptedKeyIds: [] });
  try {
    if (!options || !Array.isArray(options.keys) || !Array.isArray(options.acceptedPayloadTypes) || options.acceptedPayloadTypes.length === 0) {
      return fail("verifier misconfigured: keys and a non-empty acceptedPayloadTypes allow-list are required");
    }
    const threshold = options.threshold ?? 1;
    if (!Number.isInteger(threshold) || threshold < 1) return fail("threshold must be a positive integer");
    const uniqueConfigured = new Set(options.keys.map((k) => k.id));
    if (uniqueConfigured.size !== options.keys.length) return fail("trusted key ids must be unique");
    if (threshold > uniqueConfigured.size) return fail("threshold exceeds the number of trusted keys");

    if (envelope === null || typeof envelope !== "object" || Array.isArray(envelope)) return fail("envelope must be an object");
    const env = envelope as Record<string, unknown>;
    if (typeof env.payloadType !== "string" || env.payloadType.length === 0) return fail("payloadType must be a non-empty string");
    const payload = decodeDsseBase64(env.payload);
    if (payload === null) return fail("payload is not valid base64");
    if (!Array.isArray(env.signatures) || env.signatures.length === 0) return fail("signatures must be a non-empty array");

    const signed = dssePAE(env.payloadType, payload);
    const accepted = new Set<string>();
    for (const entry of env.signatures) {
      if (entry === null || typeof entry !== "object") continue;
      const signature = decodeDsseBase64((entry as Record<string, unknown>).sig);
      if (signature === null) continue; // skip undecodable entries, as the multi-signature procedure skips failures
      for (const key of options.keys) {
        if (accepted.has(key.id)) continue;
        if (verifyOne(key, signed, signature)) accepted.add(key.id);
      }
      if (accepted.size >= threshold) break;
    }
    if (accepted.size < threshold) return fail(`only ${accepted.size} of the required ${threshold} trusted signatures verified`);
    // The payload type check comes after signature verification, as in the spec,
    // but is still mandatory.
    if (!options.acceptedPayloadTypes.includes(env.payloadType)) return fail("payloadType is not in the accepted list");
    return { valid: true, errors: [], payloadType: env.payloadType, payload, acceptedKeyIds: [...accepted] };
  } catch (error) {
    return fail(error instanceof Error ? error.message : String(error));
  }
}
