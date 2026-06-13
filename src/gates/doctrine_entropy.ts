/**
 * doctrine_entropy.ts
 *
 * Runtime instillation of Lean theorem:
 *   Lutar.Shannon (DoctrineEntropy module)
 *   File: Lutar/Shannon/DoctrineEntropy.lean
 *   Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * Lean theorems formalised here:
 *   - `doctrine_alphabet_size_4` (line ~80): |DoctrineLabel| = 4.
 *   - `shannon_roundtrip` (line ~97): encoder–decoder round-trip is lossless.
 *   - `shannon_code_in_2_bits` (line ~103): every codeword fits in 2 bits.
 *   - `doctrine_average_codeword_length` (line ~116): all labels → length 2.
 *   - `kraft_inequality_doctrine` (line ~131): Kraft sum = 1 (equality).
 *   - `doctrine_uniform_code_length_2_bits` (line ~146): ∀ l, length(l) = 2.
 *   - `channel_rate_bound` (line ~157): rate * 2 ≤ B → rate ≤ B/2.
 *
 * Runtime contract:
 *   Encodes/decodes DoctrineLabel values using the Shannon-optimal 2-bit code.
 *   Verifies code properties and emits DSSE receipts asserting correctness.
 *
 * Citations (from Lean file):
 *   - Shannon (1948) DOI 10.1002/j.1538-7305.1948.tb01338.x
 *   - Cover & Thomas (2006) ISBN 978-0-471-24195-9 (Kraft inequality)
 *
 * Doctrine v11: No new axioms. No sorries. STAGED label: FULLY WIRED.
 */

import { createHash } from "crypto";

// ---------------------------------------------------------------------------
// Domain types
// ---------------------------------------------------------------------------

/** Doctrine label — 4-level lattice. Mirrors Lean `DoctrineLabel`. */
export type DoctrineLabel = "Bot" | "L1" | "L2" | "Top";

/** All labels in canonical order. */
export const ALL_LABELS: ReadonlyArray<DoctrineLabel> = ["Bot", "L1", "L2", "Top"];

/** DSSE-shaped receipt. */
export interface DSSEReceipt {
  theorem: string;
  lean_commit_sha: string;
  inputs_hash: string;
  output: boolean;
  ts: string;
  sig: string;
}

export type Signer = (payload: string) => string;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LEAN_THEOREM = "Lutar.Shannon.doctrine_uniform_code_length_2_bits";
const LEAN_FILE_LINE = "Lutar/Shannon/DoctrineEntropy.lean:146";
const LEAN_COMMIT_SHA = "c4d13795689601324fce0236351bfe0ade990a43";

/** Shannon-optimal codeword length for the 4-symbol doctrine alphabet. */
export const DOCTRINE_CODEWORD_LENGTH = 2;

/** Size of the doctrine alphabet. Lean: `doctrine_alphabet_size_4`. */
export const DOCTRINE_ALPHABET_SIZE = 4;

// ---------------------------------------------------------------------------
// Core functions — mirror Lean definitions
// ---------------------------------------------------------------------------

/**
 * Shannon encoder for doctrine labels.
 * Mirrors Lean `shannonCode`:
 *   Bot→0, L1→1, L2→2, Top→3
 *
 * @param label - Doctrine label.
 * @returns 2-bit codeword (0–3).
 */
export function shannonCode(label: DoctrineLabel): number {
  switch (label) {
    case "Bot": return 0;
    case "L1":  return 1;
    case "L2":  return 2;
    case "Top": return 3;
  }
}

/**
 * Shannon decoder for doctrine labels.
 * Mirrors Lean `shannonDecode`:
 *   0→Bot, 1→L1, 2→L2, 3→Top, else→null
 *
 * @param codeword - 2-bit codeword (0–3).
 * @returns DoctrineLabel or null for invalid codewords.
 */
export function shannonDecode(codeword: number): DoctrineLabel | null {
  switch (codeword) {
    case 0: return "Bot";
    case 1: return "L1";
    case 2: return "L2";
    case 3: return "Top";
    default: return null;
  }
}

/**
 * Verifies the encoder-decoder round-trip for all labels.
 * Lean theorem `shannon_roundtrip`: shannonDecode(shannonCode(l)) = some l.
 *
 * @returns true iff all 4 labels round-trip correctly.
 */
export function verifyRoundtrip(): boolean {
  return ALL_LABELS.every((l) => shannonDecode(shannonCode(l)) === l);
}

/**
 * Verifies all codewords fit in 2 bits (< 4).
 * Lean theorem `shannon_code_in_2_bits`.
 *
 * @returns true iff all codewords < 4.
 */
export function verifyCodeIn2Bits(): boolean {
  return ALL_LABELS.every((l) => shannonCode(l) < DOCTRINE_ALPHABET_SIZE);
}

/**
 * Verifies the Kraft inequality at equality.
 * Lean theorem `kraft_inequality_doctrine`:
 *   4 * 2^(2-2) = 2^2 → 4 * 1 = 4.
 *
 * @returns true iff Kraft sum = 1 (expressed as 4 * 1 = 4).
 */
export function verifyKraftEquality(): boolean {
  const codewordLengths = ALL_LABELS.map(() => DOCTRINE_CODEWORD_LENGTH);
  const L = Math.max(...codewordLengths);
  const kraftSum = codewordLengths.reduce(
    (acc, li) => acc + Math.pow(2, L - li),
    0
  );
  return kraftSum === Math.pow(2, L);
}

/**
 * Channel rate bound: rate * 2 ≤ B → rate ≤ floor(B / 2).
 * Lean theorem `channel_rate_bound`.
 *
 * @param B    - Bit-rate budget (bits/second).
 * @param rate - Claimed receipt rate (receipts/second).
 * @returns true iff `rate * 2 ≤ B`.
 */
export function channelRateBound(B: number, rate: number): boolean {
  return rate * DOCTRINE_CODEWORD_LENGTH <= B;
}

// ---------------------------------------------------------------------------
// Inputs hash helper
// ---------------------------------------------------------------------------

function hashInputs(): string {
  return createHash("sha256")
    .update("doctrine_entropy_code_verification")
    .digest("hex");
}

// ---------------------------------------------------------------------------
// DSSE receipt emitter
// ---------------------------------------------------------------------------

/**
 * Verifies all Shannon code properties and emits a DSSE receipt.
 *
 * Lean theorem: `Lutar.Shannon.doctrine_uniform_code_length_2_bits`
 * File: Lutar/Shannon/DoctrineEntropy.lean:146
 * Commit: c4d13795689601324fce0236351bfe0ade990a43
 *
 * The `output` field is `true` iff all code properties are verified.
 *
 * @param signer - Signing function.
 * @returns DSSEReceipt.
 */
export function emitDoctrineEntropyReceipt(signer: Signer): DSSEReceipt {
  const output =
    verifyRoundtrip() &&
    verifyCodeIn2Bits() &&
    verifyKraftEquality();

  const inputs_hash = hashInputs();
  const ts = new Date().toISOString();

  const sigPayload = JSON.stringify({
    theorem: LEAN_THEOREM,
    lean_commit_sha: LEAN_COMMIT_SHA,
    inputs_hash,
    output,
    ts,
  });

  return {
    theorem: LEAN_THEOREM,
    lean_commit_sha: LEAN_COMMIT_SHA,
    inputs_hash,
    output,
    ts,
    sig: signer(sigPayload),
  };
}

/**
 * Gate entry point for Lutar.Shannon.DoctrineEntropy.
 */
export function doctrineEntropyGate(signer: Signer): {
  alphabetSize: number;
  codewordLength: number;
  kraftEqualityHolds: boolean;
  receipt: DSSEReceipt;
} {
  const receipt = emitDoctrineEntropyReceipt(signer);
  return {
    alphabetSize: DOCTRINE_ALPHABET_SIZE,
    codewordLength: DOCTRINE_CODEWORD_LENGTH,
    kraftEqualityHolds: verifyKraftEquality(),
    receipt,
  };
}
