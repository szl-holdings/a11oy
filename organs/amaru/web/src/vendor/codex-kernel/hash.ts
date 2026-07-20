// VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — packages/codex-kernel/src/hash.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/**
 * Deterministic content addressing for the Codex-Kernel.
 *
 * The kernel needs SYNCHRONOUS, browser+Node-portable hashing of arbitrary
 * JSON values for state-chain integrity. We use a 128-bit FNV-1a variant
 * (two 64-bit FNV streams concatenated) over a canonical JSON serialization.
 *
 * Properties:
 *  - Deterministic across runtimes
 *  - Fast (no allocations beyond the canonical string)
 *  - Order-stable for object keys (sorted lexicographically, recursively)
 *  - 32-hex-char output, sufficient for replay verification
 *
 * NOTE: this is a non-cryptographic mixing hash. It is sufficient for
 * tamper-evident *replay* (which is what EU AI Act Article 12 logging
 * actually requires). For tamper-resistance against an adversary, swap
 * to SHA-256 via WebCrypto in a wrapping layer; the kernel never assumes
 * the hash is collision-resistant against a motivated attacker.
 */

import type { Hex, Json } from './types.js';

/**
 * Canonicalize a JSON value for hashing.
 * - Objects: keys sorted lexicographically, recursively.
 * - Arrays: order preserved.
 * - undefined / functions: not allowed (will throw via JSON.stringify).
 * - Numbers: stringified by `JSON.stringify` defaults; NaN/Infinity become null.
 */
export function canonicalize(value: Json): string {
  return JSON.stringify(sortKeysDeep(value));
}

function sortKeysDeep(value: Json): Json {
  if (value === null || typeof value !== 'object') return value;
  if (Array.isArray(value)) return value.map(sortKeysDeep);
  const keys = Object.keys(value).sort();
  const out: Record<string, Json> = {};
  for (const k of keys) out[k] = sortKeysDeep(value[k] as Json);
  return out;
}

// ────────────────────────────────────────────────────────────────────────────
// FNV-1a 64-bit (two streams for 128-bit output).
//
// We use BigInt for the inner state. For a typical 1KB canonical state, this
// processes in well under a millisecond, which is fine for an interactive
// loop kernel.
// ────────────────────────────────────────────────────────────────────────────

const FNV_OFFSET_A = 0xcbf29ce484222325n;
const FNV_OFFSET_B = 0x84222325cbf29ce4n; // rotated seed for stream 2
const FNV_PRIME = 0x100000001b3n;
const MASK_64 = 0xffffffffffffffffn;

function fnv1a64(input: string, seed: bigint): bigint {
  let hash = seed;
  for (let i = 0; i < input.length; i++) {
    // For ASCII-safe canonical JSON, charCodeAt is sufficient. Non-BMP
    // characters get processed via their surrogate pair code units, which
    // is still deterministic.
    hash = (hash ^ BigInt(input.charCodeAt(i))) & MASK_64;
    hash = (hash * FNV_PRIME) & MASK_64;
  }
  return hash;
}

/** Hash a canonical string into a 32-char lowercase hex digest. */
export function hashString(canonical: string): Hex {
  const a = fnv1a64(canonical, FNV_OFFSET_A);
  const b = fnv1a64(canonical, FNV_OFFSET_B);
  return a.toString(16).padStart(16, '0') + b.toString(16).padStart(16, '0');
}

/** Hash an arbitrary JSON value. */
export function hashJson(value: Json): Hex {
  return hashString(canonicalize(value));
}

/**
 * Chain hash: H(prev_hash || delta_canonical || next_state_canonical).
 * Encodes "this transition is part of this chain" without privileging any
 * single component.
 */
export function chainHash(
  prevHash: Hex,
  delta: Json,
  nextState: Json,
): Hex {
  return hashString(`${prevHash}|${canonicalize(delta)}|${canonicalize(nextState)}`);
}

/** Convenience: short prefix for UI display. */
export function shortHash(hex: Hex): string {
  return `${hex.slice(0, 8)}…${hex.slice(-4)}`;
}
