/**
 * @file packages/rae1/src/dsse-pae.ts
 * @description Canonical DSSE v1 Pre-Authentication Encoding (PAE).
 *
 * Per https://github.com/secure-systems-lab/dsse/blob/master/protocol.md
 *   PAE = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
 *   SP  = 0x20 (single ASCII space)
 *   LEN = ASCII decimal byte-length of the following field (no leading zeros,
 *         no negatives)
 *   type, body are UTF-8 bytes; body is the RAW envelope body, NOT base64.
 *
 * This is the single source of truth for PAE across all SZL consumers
 * (rae1/hmac.ts, vessels/pepr/*). Any change here is a wire-format change and
 * must be mirrored byte-for-byte in vessels/pepr/dsse-pae.ts until the module
 * is deduplicated via npm publish.
 *
 * Source of truth frozen against the DSSE spec example: for type
 * "http://example.com/HelloWorld" and body "hello world", the canonical PAE is
 *   "DSSEv1 29 http://example.com/HelloWorld 11 hello world"
 * (see protocol.md "Test vectors").
 */

/** Concatenate a list of byte arrays into a single Uint8Array. */
function concat(arrs: Uint8Array[]): Uint8Array {
  let total = 0;
  for (const a of arrs) total += a.length;
  const out = new Uint8Array(total);
  let off = 0;
  for (const a of arrs) {
    out.set(a, off);
    off += a.length;
  }
  return out;
}

/**
 * Compute the canonical DSSE v1 PAE over a payload type and a raw payload body.
 *
 * @param payloadType - the DSSE payloadType (e.g. "application/vnd.szl.receipt.v1+json")
 * @param payload     - the RAW body bytes (NOT base64)
 * @returns the PAE byte string
 */
export function dsseV1Pae(payloadType: string, payload: Uint8Array): Uint8Array {
  const enc = new TextEncoder();
  const typeBytes = enc.encode(payloadType);
  const sp = new Uint8Array([0x20]);
  const prefix = enc.encode("DSSEv1");
  const lenType = enc.encode(String(typeBytes.length));
  const lenBody = enc.encode(String(payload.length));
  return concat([prefix, sp, lenType, sp, typeBytes, sp, lenBody, sp, payload]);
}

/**
 * Convenience: compute the canonical DSSE v1 PAE when the body is supplied as a
 * base64 (standard or base64url) string, as it is in a DSSE envelope's
 * `payload` field. The PAE is computed over the RAW decoded body bytes, per the
 * spec — the base64 form is never fed into the PAE.
 *
 * @param payloadType - the DSSE payloadType
 * @param payloadB64  - the envelope `payload` field (base64 or base64url)
 * @returns the PAE byte string
 */
export function dsseV1PaeFromBase64Body(
  payloadType: string,
  payloadB64: string
): Uint8Array {
  const raw = base64ToBytes(payloadB64);
  return dsseV1Pae(payloadType, raw);
}

/**
 * Decode a base64 or base64url string to raw bytes.
 * Tolerates missing padding and the URL-safe alphabet.
 */
export function base64ToBytes(s: string): Uint8Array {
  const normalized = s.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  // Buffer is available in Node; fall back to atob in browser/edge runtimes.
  if (typeof Buffer !== "undefined") {
    return new Uint8Array(Buffer.from(padded, "base64"));
  }
  const bin = atob(padded);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
