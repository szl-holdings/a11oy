// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: ouroboros/bekenstein  Thesis: TH6 (Bekenstein Entropy Budget)
// Doctrine V6 preflight: ✓

// ---------------------------------------------------------------------------
// Shannon entropy calculation
// ---------------------------------------------------------------------------

/**
 * Compute Shannon entropy H(X) in bits for a discrete distribution
 * derived from an arbitrary byte buffer.
 *
 * Algorithm: count byte-value frequencies, derive probability vector,
 * apply H = -Σ p_i log₂(p_i).
 */
export function shannonEntropy(buf: Uint8Array): number {
  if (buf.length === 0) return 0;
  const freq = new Map<number, number>();
  for (const byte of buf) {
    freq.set(byte, (freq.get(byte) ?? 0) + 1);
  }
  let H = 0;
  for (const count of freq.values()) {
    const p = count / buf.length;
    H -= p * Math.log2(p);
  }
  return H; // bits per symbol
}

/** Convenience: Shannon entropy of a UTF-8 string. */
export function stringEntropy(s: string): number {
  return shannonEntropy(new TextEncoder().encode(s));
}

// ---------------------------------------------------------------------------
// Bekenstein bound
// ---------------------------------------------------------------------------

/**
 * Bekenstein bound approximation for an information system:
 *   I_max = (2π * E * R) / (ℏ * c * ln 2)
 *
 * For a software/informational analogy we use a normalised heuristic:
 *   bound = sizeBytes * 8   (bits)  — every byte contributes ≤ 8 bits
 *
 * This is a conservative upper bound: a system of `sizeBytes` bytes
 * cannot encode more than `sizeBytes * 8` bits.
 */
export function bekensteinBound(sizeBytes: number): number {
  return sizeBytes * 8; // bits
}

// ---------------------------------------------------------------------------
// Budget tracker
// ---------------------------------------------------------------------------

export interface EntropyRecord {
  receiptHash:     string;
  inputEntropy:    number; // bits per symbol, input payload
  outputEntropy:   number; // bits per symbol, output payload
  inputSizeBytes:  number;
  outputSizeBytes: number;
  inputBits:       number; // total bits: entropy * sizeBytes
  outputBits:      number;
  bound:           number; // Bekenstein bound (bits) based on output size
  withinBudget:    boolean;
  timestamp:       string;
}

const ledger: EntropyRecord[] = [];

/**
 * Record an entropy transit and assert it is within the Bekenstein budget.
 * Throws if the total output bits exceed the Bekenstein bound.
 */
/** Optional clock injection enables byte-identical replay. */
export interface TrackTransitOptions {
  now?: () => string;
}
const defaultNow = (): string => new Date().toISOString();

export function trackTransit(
  receiptHash: string,
  inputPayload: string,
  outputPayload: string,
  opts: TrackTransitOptions = {},
): EntropyRecord {
  const now = opts.now ?? defaultNow;
  const inputBuf  = new TextEncoder().encode(inputPayload);
  const outputBuf = new TextEncoder().encode(outputPayload);

  const inputEntropy  = shannonEntropy(inputBuf);
  const outputEntropy = shannonEntropy(outputBuf);
  const inputBits     = inputEntropy  * inputBuf.length;
  const outputBits    = outputEntropy * outputBuf.length;
  const bound         = bekensteinBound(outputBuf.length);

  const withinBudget = outputBits <= bound;

  if (!withinBudget) {
    throw new Error(
      `Bekenstein budget exceeded: outputBits=${outputBits.toFixed(2)} > bound=${bound} for receipt ${receiptHash.slice(0, 16)}`,
    );
  }

  const record: EntropyRecord = {
    receiptHash,
    inputEntropy,
    outputEntropy,
    inputSizeBytes: inputBuf.length,
    outputSizeBytes: outputBuf.length,
    inputBits,
    outputBits,
    bound,
    withinBudget,
    timestamp: now(),
  };
  ledger.push(record);
  return record;
}

export function getLedger(): EntropyRecord[] {
  return [...ledger];
}

export function getLedgerEntry(receiptHash: string): EntropyRecord | undefined {
  return ledger.find((e) => e.receiptHash === receiptHash);
}

// ---------------------------------------------------------------------------
// Budget summary
// ---------------------------------------------------------------------------

export interface BudgetSummary {
  totalTransits:     number;
  totalInputBits:    number;
  totalOutputBits:   number;
  totalBound:        number;
  budgetUsedPercent: number;
}

export function budgetSummary(): BudgetSummary {
  const totalInputBits  = ledger.reduce((s, e) => s + e.inputBits, 0);
  const totalOutputBits = ledger.reduce((s, e) => s + e.outputBits, 0);
  const totalBound      = ledger.reduce((s, e) => s + e.bound, 0);
  return {
    totalTransits:     ledger.length,
    totalInputBits,
    totalOutputBits,
    totalBound,
    budgetUsedPercent: totalBound > 0 ? (totalOutputBits / totalBound) * 100 : 0,
  };
}
