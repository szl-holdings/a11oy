/**
 * Λ-QL internal utilities — crypto-free polyfills + UUID
 * File: a11oy/src/protocol/lambda-ql/util.ts
 *
 * Doctrine v2. Zero external deps. Works in Node ≥ 18 and browser.
 */

/** Generate a UUID v4 using the platform crypto API. */
export function randomUUID(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for Node <19 without --experimental-global-webcrypto
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Compute a deterministic SHA-256 hex digest.
 * In Node ≥ 20: uses globalThis.crypto.subtle.digest.
 * Fallback: djb2 hash (weak — for testing only, tagged [UNVERIFIED_CRYPTO]).
 */
export async function sha256Hex(input: string): Promise<string> {
  if (typeof crypto !== "undefined" && crypto.subtle) {
    const enc = new TextEncoder();
    const buf = await crypto.subtle.digest("SHA-256", enc.encode(input));
    return Array.from(new Uint8Array(buf))
      .map(b => b.toString(16).padStart(2, "0"))
      .join("");
  }
  // [UNVERIFIED_CRYPTO] djb2 fallback — NOT cryptographically secure
  // Replace with node:crypto in production builds
  let hash = 5381;
  for (let i = 0; i < input.length; i++) {
    hash = ((hash << 5) + hash) ^ input.charCodeAt(i);
    hash = hash >>> 0;
  }
  return "djb2-" + hash.toString(16).padStart(8, "0") + "-INSECURE";
}

/** Synchronous djb2 hash — for non-crypto fingerprinting only */
export function djb2(input: string): string {
  let hash = 5381;
  for (let i = 0; i < input.length; i++) {
    hash = ((hash << 5) + hash) ^ input.charCodeAt(i);
    hash = hash >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

/** ISO 8601 UTC timestamp */
export function nowISO(): string {
  return new Date().toISOString();
}

/** Truncate string to max chars for receipt previews */
export function truncate(s: string, max: number): string {
  return s.length <= max ? s : s.slice(0, max - 3) + "...";
}
