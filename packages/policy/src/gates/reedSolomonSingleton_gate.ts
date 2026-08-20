// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for ReedSolomonSingletonBound (G40)
//
// Policy rationale:
//   A receipt chain that claims to use Reed-Solomon erasure coding for shard
//   resilience must declare valid RS parameters [n, k, d, q] that satisfy:
//     (1) n ≤ q  (valid parameter range over field GF(q))
//     (2) 1 ≤ k ≤ n
//     (3) d = n - k + 1  (MDS condition — Singleton bound achieved with equality)
//     (4) claimed_erasure_capacity ≤ n - k
//   If any condition fails, the resilience claim is unsubstantiated and the gate denies.
//
//   Lean theorem cited: `reedSolomonMDSProperty`
//   Lean file: Lutar/CodingTheory/ReedSolomonSingleton.lean
//   Lean commit SHA: b675cd84caa17080671570c153484c817f8769ac
//   Lean status: gate-level arithmetic (`reedSolomonMDSProperty`) has 0 sorries;
//                MDS achievability proof has 1 sorry (sorry₁ — discharge route documented).
//   Severity: ENFORCED
//
// References:
//   Reed & Solomon (1960). DOI:10.1137/0108018
//   Singleton (1964). "Maximum Distance q-nary Codes."
//   IEEE Trans. Inf. Theory 10(2), 116–118. DOI:10.1109/TIT.1964.1053661
//   MacWilliams & Sloane (1977). Theory of Error-Correcting Codes. Ch.11.

// ── Inline formula ─────────────────────────────────────────────────────────────
// G40: Singleton bound: d ≤ n - k + 1  [Singleton 1964, DOI:10.1109/TIT.1964.1053661]
//      MDS (RS) condition: d = n - k + 1  [Reed & Solomon 1960, DOI:10.1137/0108018]
//      Gate passes iff d == n - k + 1 AND t_claimed ≤ n - k.

export interface ReedSolomonSingletonGateConfig {
  /**
   * Whether to enforce strict MDS check (d must equal Singleton bound exactly).
   * Default: true.
   */
  requireMDS?: boolean;
}

export interface ReedSolomonSingletonGateOpts {
  /** Code length n ≥ 1. */
  rs_n: number;
  /** Code dimension k: 1 ≤ k ≤ n. */
  rs_k: number;
  /** Declared minimum distance d ≥ 1. */
  rs_d: number;
  /** Field size q (prime power). Must satisfy n ≤ q. */
  rs_q: number;
  /**
   * Declared erasure correction capacity t_era ≤ n - k.
   * An RS code can correct up to n - k erasures.
   */
  claimed_erasure_capacity: number;
}

export interface ReedSolomonSingletonDecision {
  allow:                      boolean;
  rationale:                  string;
  formula:                    string;
  leanTheorem:                string;
  leanFile:                   string;
  leanCommitSha:              string;
  rs_n:                       number;
  rs_k:                       number;
  rs_d:                       number;
  rs_q:                       number;
  singleton_bound:            number;
  is_mds:                     boolean;
  error_correction_capacity:  number;
  erasure_correction_capacity: number;
  claimed_erasure_capacity:   number;
  capacity_valid:             boolean;
  failures:                   string[];
  dsse_extension: {
    erasure_coding: {
      scheme:                       string;
      rs_n:                         number;
      rs_k:                         number;
      rs_d:                         number;
      rs_q:                         number;
      singleton_bound:              number;
      is_mds:                       boolean;
      error_correction_capacity:    number;
      erasure_correction_capacity:  number;
      claimed_erasure_capacity:     number;
      capacity_valid:               boolean;
      lean_theorem_sha:             string;
    };
  };
}

const LEAN_THEOREM = "reedSolomonMDSProperty";
const LEAN_FILE    = "Lutar/CodingTheory/ReedSolomonSingleton.lean";
const LEAN_COMMIT  = "b675cd84caa17080671570c153484c817f8769ac";
const FORMULA_STR  =
  "d = n−k+1 (MDS); t_era ≤ n−k  " +
  "[Reed & Solomon 1960 DOI:10.1137/0108018; Singleton 1964 DOI:10.1109/TIT.1964.1053661]";

/**
 * ReedSolomonSingletonBound (G40) policy gate.
 *
 * Validates that declared RS code parameters satisfy the Singleton bound
 * (d = n − k + 1 for MDS codes) and that the claimed erasure correction
 * capacity does not exceed the theoretical maximum n − k.
 *
 * Lean theorem: `reedSolomonMDSProperty` (Lutar/CodingTheory/ReedSolomonSingleton.lean)
 * References: Reed & Solomon (1960); Singleton (1964).
 */
export function reedSolomonSingletonGate(
  config: ReedSolomonSingletonGateConfig = {}
): (opts: ReedSolomonSingletonGateOpts) => ReedSolomonSingletonDecision {
  const requireMDS = config.requireMDS ?? true;

  return (opts: ReedSolomonSingletonGateOpts): ReedSolomonSingletonDecision => {
    const { rs_n, rs_k, rs_d, rs_q, claimed_erasure_capacity } = opts;

    // --- Input type checks ---
    for (const [name, val] of [
      ["rs_n", rs_n], ["rs_k", rs_k], ["rs_d", rs_d],
      ["rs_q", rs_q], ["claimed_erasure_capacity", claimed_erasure_capacity]
    ] as [string, number][]) {
      if (!Number.isInteger(val) || val < 0) {
        throw new Error(`ReedSolomonSingletonGate: ${name} must be a non-negative integer; got ${val}`);
      }
    }

    const failures: string[] = [];

    // Condition 1: 1 ≤ k ≤ n
    if (rs_k < 1 || rs_k > rs_n) {
      failures.push(`k=${rs_k} violates 1 ≤ k ≤ n=${rs_n}`);
    }
    // Condition 2: n ≤ q (valid RS parameter range)
    if (rs_n > rs_q) {
      failures.push(`n=${rs_n} > q=${rs_q}: RS requires n ≤ q (field size)`);
    }

    // Core calculations
    const singleton_bound = rs_n - rs_k + 1;                    // n - k + 1
    const is_mds = rs_d === singleton_bound;                     // d == Singleton bound
    const erasure_correction_capacity = rs_n - rs_k;            // max erasures correctable
    const error_correction_capacity = Math.floor(erasure_correction_capacity / 2);

    // Condition 3: MDS check d = n - k + 1
    if (requireMDS && !is_mds) {
      failures.push(
        `d=${rs_d} ≠ n−k+1=${singleton_bound}: not an MDS code (RS requires d = n−k+1)`
      );
    }
    // Condition 4: claimed erasure capacity ≤ true capacity
    const capacity_valid = claimed_erasure_capacity <= erasure_correction_capacity;
    if (!capacity_valid) {
      failures.push(
        `claimed_erasure_capacity=${claimed_erasure_capacity} > n−k=${erasure_correction_capacity}`
      );
    }

    const allow = failures.length === 0;
    const rationale = allow
      ? `Lean:${LEAN_THEOREM} — RS[${rs_n},${rs_k},${rs_d}]_${rs_q} is MDS (d=n−k+1=${singleton_bound}). Erasure capacity t_era=${erasure_correction_capacity} ≥ claimed ${claimed_erasure_capacity}. Receipt chain resilience claim verified.`
      : `Lean:${LEAN_THEOREM} — DENY: ${failures.join("; ")}`;

    return {
      allow,
      rationale,
      formula:                    FORMULA_STR,
      leanTheorem:                LEAN_THEOREM,
      leanFile:                   LEAN_FILE,
      leanCommitSha:              LEAN_COMMIT,
      rs_n,
      rs_k,
      rs_d,
      rs_q,
      singleton_bound,
      is_mds,
      error_correction_capacity,
      erasure_correction_capacity,
      claimed_erasure_capacity,
      capacity_valid,
      failures,
      dsse_extension: {
        erasure_coding: {
          scheme:                       "Reed-Solomon",
          rs_n,
          rs_k,
          rs_d,
          rs_q,
          singleton_bound,
          is_mds,
          error_correction_capacity,
          erasure_correction_capacity,
          claimed_erasure_capacity,
          capacity_valid,
          lean_theorem_sha:             LEAN_COMMIT,
        },
      },
    };
  };
}
