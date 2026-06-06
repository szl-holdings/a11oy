/**
 * @file packages/api/src/lib/dsse-pae.ts
 * @description Canonical DSSE v1 Pre-Authentication Encoding (PAE).
 *
 * This is the SAME unified PAE that PhD Crypto verdict finding A1 mandates and
 * that lives canonically at @szl-holdings/a11oy (packages/rae1/src/dsse-pae.ts).
 * It is vendored byte-for-byte here so the API has no runtime dependency on an
 * unpublished package; any divergence is a wire-format bug.
 *
 *   PAE = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
 *   SP  = 0x20 (single ASCII space)
 *   LEN = ASCII decimal byte-length of the following field
 *
 * Spec: https://github.com/secure-systems-lab/dsse/blob/master/protocol.md
 * Do NOT re-invent. See PhD Crypto verdict findings A1 + I.
 */

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

/** Compute the canonical DSSE v1 PAE over a payload type and a RAW body. */
export function dsseV1Pae(payloadType: string, payload: Uint8Array): Uint8Array {
  const enc = new TextEncoder();
  const typeBytes = enc.encode(payloadType);
  const sp = new Uint8Array([0x20]);
  const prefix = enc.encode('DSSEv1');
  const lenType = enc.encode(String(typeBytes.length));
  const lenBody = enc.encode(String(payload.length));
  return concat([prefix, sp, lenType, sp, typeBytes, sp, lenBody, sp, payload]);
}

/** Decode a base64 or base64url string to raw bytes (tolerant of padding). */
export function base64ToBytes(s: string): Uint8Array {
  const normalized = s.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4);
  if (typeof Buffer !== 'undefined') {
    return new Uint8Array(Buffer.from(padded, 'base64'));
  }
  const bin = atob(padded);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/** Compute the canonical PAE when the body is supplied as a base64 envelope field. */
export function dsseV1PaeFromBase64Body(payloadType: string, payloadB64: string): Uint8Array {
  return dsseV1Pae(payloadType, base64ToBytes(payloadB64));
}
