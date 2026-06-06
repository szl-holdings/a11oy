/**
 * Tests for Relay Chain Latency SLA Gate
 * Lean theorem: Lutar.Propagation.Relay.relay_chain_bounded_latency (GREEN)
 *
 * 1000+ random hop arrays; all within-SLA chains pass, violating ones detected.
 */

import { describe, it, expect } from "vitest";
import {
  relayLatencyGate,
  assertRelayLatencySla,
  type HopSpec,
} from "../src/sla/relay_latency_gate";

// ---------------------------------------------------------------------------
// Deterministic cases
// ---------------------------------------------------------------------------

describe("relayLatencyGate — GREEN theorem relay_chain_bounded_latency", () => {
  it("single hop within cap: withinSla = true", () => {
    const r = relayLatencyGate([{ id: "h0", latencyMs: 10 }], 20);
    expect(r.withinSla).toBe(true);
    expect(r.totalLatencyMs).toBe(10);
    expect(r.slabudgetMs).toBe(20);
  });

  it("single hop at exact cap: withinSla = true", () => {
    const r = relayLatencyGate([{ id: "h0", latencyMs: 50 }], 50);
    expect(r.withinSla).toBe(true);
  });

  it("single hop over cap: withinSla = false, violatingHop set", () => {
    const r = relayLatencyGate([{ id: "h0", latencyMs: 51 }], 50);
    expect(r.withinSla).toBe(false);
    expect(r.violatingHop?.id).toBe("h0");
  });

  it("empty hop list: withinSla = true, total = 0", () => {
    const r = relayLatencyGate([], 100);
    expect(r.withinSla).toBe(true);
    expect(r.totalLatencyMs).toBe(0);
    expect(r.hopCount).toBe(0);
  });

  it("3-hop chain all within cap: total ≤ N × cap", () => {
    const hops: HopSpec[] = [
      { id: "a", latencyMs: 10 },
      { id: "b", latencyMs: 15 },
      { id: "c", latencyMs: 5 },
    ];
    const r = relayLatencyGate(hops, 20);
    expect(r.withinSla).toBe(true);
    expect(r.totalLatencyMs).toBe(30);
    expect(r.slabudgetMs).toBe(60);
    expect(r.totalLatencyMs).toBeLessThanOrEqual(r.slabudgetMs);
  });

  it("receipt contains correct lean_theorem", () => {
    const r = relayLatencyGate([{ id: "x", latencyMs: 1 }], 10);
    expect(r.receipt.lean_theorem).toBe(
      "Lutar.Propagation.Relay.relay_chain_bounded_latency"
    );
    expect(r.receipt.formula).toBe("relay_chain_bounded_latency");
    expect(r.receipt.lean_file).toBe("Lutar/Propagation/RelayChain.lean");
    expect(r.receipt.inputs_hash).toHaveLength(64);
  });

  it("assertRelayLatencySla throws on violation", () => {
    expect(() =>
      assertRelayLatencySla([{ id: "overloaded", latencyMs: 200 }], 100)
    ).toThrow(/SLA VIOLATION/);
  });

  it("assertRelayLatencySla returns result on pass", () => {
    const r = assertRelayLatencySla([{ id: "fast", latencyMs: 5 }], 100);
    expect(r.withinSla).toBe(true);
  });

  it("throws on negative capMs", () => {
    expect(() => relayLatencyGate([], -1)).toThrow(/capMs must be/);
  });

  it("throws on negative hop latency", () => {
    expect(() =>
      relayLatencyGate([{ id: "bad", latencyMs: -1 }], 100)
    ).toThrow(/negative latency/);
  });
});

// ---------------------------------------------------------------------------
// Fuzz: 1000 random hop arrays
// ---------------------------------------------------------------------------

describe("relayLatencyGate — 1000 random within-SLA chains (theorem fuzz)", () => {
  it("all within-SLA chains report withinSla=true", () => {
    let failures = 0;
    for (let i = 0; i < 1000; i++) {
      const n = Math.floor(Math.random() * 50) + 1;
      const cap = Math.random() * 100 + 1; // 1–101 ms
      const hops: HopSpec[] = Array.from({ length: n }, (_, k) => ({
        id: `h${k}`,
        latencyMs: Math.random() * cap, // always ≤ cap
      }));
      const r = relayLatencyGate(hops, cap);
      if (!r.withinSla) failures++;
      // theorem guarantee: total ≤ N × cap
      if (r.totalLatencyMs > r.slabudgetMs + 1e-6) failures++;
    }
    expect(failures).toBe(0);
  });

  it("chains with one over-cap hop are detected", () => {
    let detected = 0;
    for (let i = 0; i < 200; i++) {
      const n = Math.floor(Math.random() * 10) + 2;
      const cap = 50;
      const hops: HopSpec[] = Array.from({ length: n }, (_, k) => ({
        id: `h${k}`,
        latencyMs: k === 0 ? cap + 1 + Math.random() * 50 : Math.random() * cap,
      }));
      const r = relayLatencyGate(hops, cap);
      if (!r.withinSla && r.violatingHop !== undefined) detected++;
    }
    expect(detected).toBe(200);
  });
});
