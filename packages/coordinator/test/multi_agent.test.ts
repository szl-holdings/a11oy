/**
 * Tests for Multi-Agent Cooperative Termination Gate
 * Lean theorem: Lutar.Thesis.MultiAgent.all_agents_terminate (GREEN)
 *
 * Property: 7 organs each with finite fuel budget terminate within budget steps.
 */

import { describe, it, expect } from "vitest";
import {
  runMultiAgentTermination,
  ouroborosAgents,
  type AgentSpec,
} from "../src/multi_agent_terminator";

// ---------------------------------------------------------------------------
// Deterministic cases
// ---------------------------------------------------------------------------

describe("runMultiAgentTermination — GREEN theorem all_agents_terminate", () => {
  it("single agent with fuel=1: terminates in 1 step", () => {
    const agents: AgentSpec[] = [
      { id: "test", fuel: 1, step: () => 1 },
    ];
    const r = runMultiAgentTermination(agents);
    expect(r.allTerminated).toBe(true);
    expect(r.traces[0]!.terminatedWithin).toBe(true);
    expect(r.traces[0]!.stepsRun).toBe(1);
  });

  it("single agent with fuel=10, consuming 2/step: terminates in 5 steps", () => {
    const agents: AgentSpec[] = [
      { id: "fast", fuel: 10, step: () => 2 },
    ];
    const r = runMultiAgentTermination(agents);
    expect(r.allTerminated).toBe(true);
    expect(r.traces[0]!.fuelConsumed).toBe(10);
  });

  it("7 Ouroboros organs with fuel 100 each: all terminate", () => {
    const agents = ouroborosAgents();
    const r = runMultiAgentTermination(agents);
    expect(r.allTerminated).toBe(true);
    expect(r.violations).toHaveLength(0);
    expect(r.traces).toHaveLength(7);
    for (const trace of r.traces) {
      expect(trace.terminatedWithin).toBe(true);
    }
  });

  it("3 agents, mixed budgets: all terminate", () => {
    const agents: AgentSpec[] = [
      { id: "a", fuel: 5, step: () => 1 },
      { id: "b", fuel: 10, step: () => 3 },
      { id: "c", fuel: 7, step: () => 2 },
    ];
    const r = runMultiAgentTermination(agents);
    expect(r.allTerminated).toBe(true);
    expect(r.receipt.lean_theorem).toBe(
      "Lutar.Thesis.MultiAgent.all_agents_terminate"
    );
  });

  it("receipt fields are correct", () => {
    const agents = ouroborosAgents({ amaru: 5, sentra: 5 });
    const r = runMultiAgentTermination([agents[0]!, agents[1]!]);
    expect(r.receipt.formula).toBe("all_agents_terminate");
    expect(r.receipt.lean_file).toBe(
      "Lutar/Thesis/TH_V18_15_MultiAgentFairness.lean"
    );
    expect(r.receipt.inputs_hash).toHaveLength(64);
    expect(typeof r.receipt.ts).toBe("string");
  });

  it("throws on non-integer fuel", () => {
    expect(() =>
      runMultiAgentTermination([{ id: "x", fuel: 1.5, step: () => 1 }])
    ).toThrow(/integer/);
  });

  it("throws on zero fuel", () => {
    expect(() =>
      runMultiAgentTermination([{ id: "x", fuel: 0, step: () => 1 }])
    ).toThrow(/finite positive integer/);
  });

  it("step returning 0 throws (violates termination precondition)", () => {
    expect(() =>
      runMultiAgentTermination([
        { id: "bad", fuel: 10, step: () => 0 },
      ])
    ).toThrow(/must return integer ≥ 1/);
  });

  it("ouroborosAgents produces 7 named organs", () => {
    const agents = ouroborosAgents();
    const ids = agents.map((a) => a.id).sort();
    expect(ids).toEqual(
      ["a11oy", "amaru", "rosie", "sentra", "uds-mesh", "vessels", "vsp-otel"]
    );
  });

  it("ouroborosAgents respects custom budgets", () => {
    const agents = ouroborosAgents({ amaru: 42, sentra: 17 });
    const amaru = agents.find((a) => a.id === "amaru")!;
    const sentra = agents.find((a) => a.id === "sentra")!;
    expect(amaru.fuel).toBe(42);
    expect(sentra.fuel).toBe(17);
  });
});

// ---------------------------------------------------------------------------
// Fuzz: 1000 random agent configs
// ---------------------------------------------------------------------------

describe("runMultiAgentTermination — 1000 random configs (theorem fuzz)", () => {
  it("7 organs each with random budget [1,100]: all terminate", () => {
    let failures = 0;
    for (let i = 0; i < 1000; i++) {
      const budgets: Record<string, number> = {};
      for (const organ of ["amaru", "sentra", "vessels", "rosie", "vsp-otel", "uds-mesh", "a11oy"]) {
        budgets[organ] = Math.floor(Math.random() * 100) + 1;
      }
      const agents = ouroborosAgents(budgets);
      const r = runMultiAgentTermination(agents);
      if (!r.allTerminated) failures++;
    }
    expect(failures).toBe(0);
  });

  it("random agents 1–10 with random budgets 1–50: all terminate", () => {
    let failures = 0;
    for (let i = 0; i < 200; i++) {
      const n = Math.floor(Math.random() * 10) + 1;
      const agents: AgentSpec[] = Array.from({ length: n }, (_, k) => ({
        id: `agent-${k}`,
        fuel: Math.floor(Math.random() * 50) + 1,
        step: () => Math.floor(Math.random() * 3) + 1, // consume 1–3 per step
      }));
      const r = runMultiAgentTermination(agents);
      if (!r.allTerminated) failures++;
    }
    expect(failures).toBe(0);
  });
});
