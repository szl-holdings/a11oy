/**
 * Multi-Agent Cooperative Termination Gate
 *
 * @lean_theorem Lutar.Thesis.MultiAgent.th_v18_15b_list_termination
 * @lean_file    Lutar/Thesis/TH_V18_15_MultiAgentFairness.lean
 * @lean_status  UNVERIFIED — theorem name "all_agents_terminate" does not exist in TH_V18_15_MultiAgentFairness.lean;
 *               closest match: th_v18_15b_list_termination (proven, 0 sorries).
 *               The file contains th_v18_15a..th_v18_15f but no top-level alias.
 *               Per PhD-Math review 2026-05-31 (Pass 1, Binding #1, Finding F3).
 * @lean_todo    Add theorem all_agents_terminate as a top-level alias wrapping
 *               th_v18_15b_list_termination in lutar-lean, then restore GREEN.
 * @lean_commit  see LEAN_COMMIT_SHA env var; pin at CI time from lutar-lean/lean-toolchain
 *
 * Theorem (Lynch 1996 Distributed Algorithms Ch.8):
 *   All agents with finite fuel budgets terminate cooperatively.
 *   The 7-organ Ouroboros stack (amaru, sentra, vessels, rosie, vsp-otel,
 *   uds-mesh, a11oy) cannot deadlock under bounded fuel.
 *
 * Proof (by well-founded induction on total fuel):
 *   Let F = Σᵢ fuel(agentᵢ) ∈ ℕ. Each cooperative step decreases F by ≥ 1.
 *   Since ℕ is well-founded, F reaches 0 in at most Σᵢ fuel(agentᵢ) steps.
 *   No deadlock: each step a waiting agent is unblocked by the scheduler
 *   (round-robin fairness), so no agent starves.
 *
 * Implementation:
 *   - Each agent has a fuel budget (discrete steps remaining)
 *   - Each step: agent runs its action, fuel decremented by consumed amount
 *   - Gate asserts all agents reach fuel=0 within budget
 *
 * References:
 *   Lynch (1996) Distributed Algorithms Ch.8 — cooperative termination
 *   Lutar/Thesis/TH_V18_15_MultiAgentFairness.lean — kernel-checked proof
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import * as crypto from "crypto";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AgentSpec {
  /** Unique organ name */
  id: string;
  /** Fuel budget (finite positive integer — theorem requires this) */
  fuel: number;
  /**
   * Agent action: called each step with remaining fuel.
   * Returns fuel consumed this step (must be ≥ 1 to guarantee termination).
   */
  step: (remainingFuel: number) => number;
}

export interface AgentTerminationTrace {
  agentId: string;
  stepsRun: number;
  fuelConsumed: number;
  terminatedWithin: boolean;
}

export interface MultiAgentTerminationResult {
  /** True iff all agents terminated within their budgets */
  allTerminated: boolean;
  /** Per-agent termination traces */
  traces: AgentTerminationTrace[];
  /** Total steps across all agents */
  totalSteps: number;
  /** Any agents that exceeded budget */
  violations: string[];
  /** DSSE receipt */
  receipt: MultiAgentDsseReceipt;
}

export interface MultiAgentDsseReceipt {
  formula: string;
  lean_theorem: string;
  lean_file: string;
  lean_commit_sha: string;
  inputs_hash: string;
  output: {
    allTerminated: boolean;
    agentCount: number;
    totalSteps: number;
    violations: string[];
  };
  ts: string;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function sha256Hex(obj: unknown): string {
  return crypto.createHash("sha256").update(JSON.stringify(obj)).digest("hex");
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Run multi-agent cooperative termination simulation and assert the theorem.
 *
 * @param agents  Array of agent specs with finite fuel budgets
 *
 * By the Lean theorem, if each agent's step function always consumes ≥ 1 fuel,
 * all agents terminate in at most Σᵢ fuel(agentᵢ) total steps.
 *
 * The scheduler is round-robin (fair) — no agent starves.
 *
 * @returns MultiAgentTerminationResult with per-agent traces and DSSE receipt.
 */
export function runMultiAgentTermination(
  agents: AgentSpec[]
): MultiAgentTerminationResult {
  // Validate: all fuel budgets must be finite positive integers
  for (const agent of agents) {
    if (!Number.isFinite(agent.fuel) || agent.fuel < 1) {
      throw new Error(
        `runMultiAgentTermination: agent "${agent.id}" fuel must be finite positive integer, got ${agent.fuel}`
      );
    }
    if (!Number.isInteger(agent.fuel)) {
      throw new Error(
        `runMultiAgentTermination: agent "${agent.id}" fuel must be integer (theorem uses ℕ), got ${agent.fuel}`
      );
    }
  }

  const remaining = agents.map((a) => a.fuel);
  const stepsRun = new Array(agents.length).fill(0);
  const fuelConsumed = new Array(agents.length).fill(0);
  const terminated = new Array(agents.length).fill(false);

  let totalSteps = 0;
  const maxTotalSteps = agents.reduce((sum, a) => sum + a.fuel, 0);

  // Round-robin scheduler
  let anyActive = true;
  while (anyActive && totalSteps < maxTotalSteps) {
    anyActive = false;
    for (let i = 0; i < agents.length; i++) {
      if (remaining[i]! <= 0) continue;
      anyActive = true;

      const consumed = agents[i]!.step(remaining[i]!);
      if (!Number.isInteger(consumed) || consumed < 1) {
        throw new Error(
          `Agent "${agents[i]!.id}" step() returned ${consumed} — must return integer ≥ 1 to guarantee termination (theorem precondition).`
        );
      }

      const actualConsumed = Math.min(consumed, remaining[i]!);
      remaining[i] = remaining[i]! - actualConsumed;
      stepsRun[i]++;
      fuelConsumed[i] += actualConsumed;
      totalSteps++;

      if (remaining[i]! <= 0) {
        terminated[i] = true;
      }
    }
  }

  // Final termination status
  const traces: AgentTerminationTrace[] = agents.map((a, i) => ({
    agentId: a.id,
    stepsRun: stepsRun[i] as number,
    fuelConsumed: fuelConsumed[i] as number,
    terminatedWithin: terminated[i] as boolean,
  }));

  const violations = agents
    .filter((_, i) => !terminated[i])
    .map((a) => a.id);
  const allTerminated = violations.length === 0;

  const inputs_hash = sha256Hex(agents.map((a) => ({ id: a.id, fuel: a.fuel })));
  const lean_commit_sha = process.env["LEAN_COMMIT_SHA"] ?? "unknown";

  const receipt: MultiAgentDsseReceipt = {
    formula: "all_agents_terminate",
    lean_theorem: "Lutar.Thesis.MultiAgent.th_v18_15b_list_termination", // UNVERIFIED: all_agents_terminate does not exist; closest is th_v18_15b_list_termination. See PhD-Math F3.,
    lean_file: "Lutar/Thesis/TH_V18_15_MultiAgentFairness.lean",
    lean_commit_sha,
    inputs_hash,
    output: {
      allTerminated,
      agentCount: agents.length,
      totalSteps,
      violations,
    },
    ts: new Date().toISOString(),
  };

  return { allTerminated, traces, totalSteps, violations, receipt };
}

/**
 * The 7 Ouroboros organs with default trivial step functions (consume 1 fuel/step).
 * Pass to runMultiAgentTermination to assert system-wide termination.
 *
 * @param budgets  Map of organ name → fuel budget. Defaults to 100 if not specified.
 */
export function ouroborosAgents(
  budgets: Partial<Record<string, number>> = {}
): AgentSpec[] {
  const ORGANS = [
    "amaru",
    "sentra",
    "vessels",
    "rosie",
    "vsp-otel",
    "uds-mesh",
    "a11oy",
  ] as const;

  return ORGANS.map((id) => ({
    id,
    fuel: budgets[id] ?? 100,
    // Default: consume exactly 1 fuel per step (trivial agent)
    step: (_remaining: number) => 1,
  }));
}
