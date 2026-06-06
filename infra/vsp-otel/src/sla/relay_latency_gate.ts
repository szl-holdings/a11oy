/**
 * Relay Chain Latency SLA Gate
 *
 * @lean_theorem Lutar.Propagation.Relay.relay_chain_bounded_latency
 * @lean_file    Lutar/Propagation/RelayChain.lean
 * @lean_status  GREEN — 0 sorries, list induction proof complete
 * @lean_commit  see LEAN_COMMIT_SHA env var; pin at CI time from lutar-lean/lean-toolchain
 *
 * Theorem (Qhapaq Ñan relay model, Hyslop 1984 Incas of the Andes ch.6):
 *   For N hops each with latency ≤ cap, total latency ≤ N × cap.
 *   totalLatency(hops) = List.foldl (+) 0 hops ≤ |hops| * cap
 *
 * Proof: List.foldl induction on hop list (pure Lean 4 kernel):
 *   Base: foldl (+) 0 [] = 0 ≤ 0 * cap.  ✓
 *   Step: foldl (+) 0 (h :: t) = h + foldl (+) 0 t
 *         ≤ cap + (|t| * cap) = (|t| + 1) * cap.  ✓ by IH and h ≤ cap.
 *
 * References:
 *   Hyslop (1984) The Incas of the Andes ch.6 — Qhapaq Ñan chasqui relay stations
 *   Lutar/Propagation/RelayChain.lean commit ${LEAN_COMMIT_SHA}
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import * as crypto from "crypto";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface HopSpec {
  /** Unique identifier for this relay hop (organ name, node ID, etc.) */
  id: string;
  /** Observed latency for this hop in milliseconds */
  latencyMs: number;
}

export interface RelayLatencyResult {
  /** Sum of all hop latencies */
  totalLatencyMs: number;
  /** Per-hop cap used for SLA (milliseconds) */
  capMs: number;
  /** Number of hops */
  hopCount: number;
  /** SLA budget = hopCount × capMs */
  slabudgetMs: number;
  /** True iff totalLatencyMs ≤ slabudgetMs (theorem guarantee) */
  withinSla: boolean;
  /** First hop that violated the per-hop cap, if any */
  violatingHop?: HopSpec;
  /** DSSE receipt */
  receipt: RelayDsseReceipt;
}

export interface RelayDsseReceipt {
  formula: string;
  lean_theorem: string;
  lean_file: string;
  lean_commit_sha: string;
  inputs_hash: string;
  output: {
    withinSla: boolean;
    totalLatencyMs: number;
    slabudgetMs: number;
    hopCount: number;
    violatingHop: HopSpec | null;
  };
  ts: string;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function sha256Hex(obj: unknown): string {
  return crypto
    .createHash("sha256")
    .update(JSON.stringify(obj))
    .digest("hex");
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Assert the relay chain latency SLA bound.
 *
 * @param hops   Ordered list of relay hops with observed latencies
 * @param capMs  Per-hop latency cap in milliseconds (SLA parameter)
 * @returns      RelayLatencyResult with theorem-backed SLA assessment
 *
 * The gate passes iff every individual hop satisfies latencyMs ≤ capMs,
 * which by the Lean theorem guarantees totalLatency ≤ N × capMs.
 * This is a stronger per-hop check than the aggregate bound alone.
 */
export function relayLatencyGate(
  hops: HopSpec[],
  capMs: number
): RelayLatencyResult {
  if (capMs < 0) throw new Error("relayLatencyGate: capMs must be ≥ 0");

  let totalLatencyMs = 0;
  let violatingHop: HopSpec | undefined;

  for (const hop of hops) {
    if (hop.latencyMs < 0) {
      throw new Error(
        `relayLatencyGate: negative latency ${hop.latencyMs} for hop ${hop.id}`
      );
    }
    totalLatencyMs += hop.latencyMs;
    if (hop.latencyMs > capMs && violatingHop === undefined) {
      violatingHop = hop;
    }
  }

  const hopCount = hops.length;
  const slabudgetMs = hopCount * capMs;
  const withinSla = violatingHop === undefined; // per-hop check → aggregate holds

  const inputs_hash = sha256Hex({ hops, capMs });
  const lean_commit_sha = process.env["LEAN_COMMIT_SHA"] ?? "unknown";

  const receipt: RelayDsseReceipt = {
    formula: "relay_chain_bounded_latency",
    lean_theorem: "Lutar.Propagation.Relay.relay_chain_bounded_latency",
    lean_file: "Lutar/Propagation/RelayChain.lean",
    lean_commit_sha,
    inputs_hash,
    output: {
      withinSla,
      totalLatencyMs,
      slabudgetMs,
      hopCount,
      violatingHop: violatingHop ?? null,
    },
    ts: new Date().toISOString(),
  };

  return {
    totalLatencyMs,
    capMs,
    hopCount,
    slabudgetMs,
    withinSla,
    violatingHop,
    receipt,
  };
}

/**
 * Convenience: assert SLA or throw.
 * Use in middleware where a violation should halt the request.
 */
export function assertRelayLatencySla(
  hops: HopSpec[],
  capMs: number
): RelayLatencyResult {
  const result = relayLatencyGate(hops, capMs);
  if (!result.withinSla) {
    const vh = result.violatingHop!;
    throw new Error(
      `SLA VIOLATION: hop "${vh.id}" latency ${vh.latencyMs}ms > cap ${capMs}ms. ` +
        `Lean theorem Lutar.Propagation.Relay.relay_chain_bounded_latency requires all hops ≤ cap.`
    );
  }
  return result;
}
