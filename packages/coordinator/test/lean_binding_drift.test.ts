/**
 * Binding-drift guard — multi_agent_terminator.ts
 *
 * Strike 1 (Watunakuy): these tests assert that the @lean_theorem annotation
 * in multi_agent_terminator.ts cites a REAL theorem name that exists in
 * Lutar/Thesis/TH_V18_15_MultiAgentFairness.lean, and that @lean_status
 * is not falsely GREEN.
 *
 * PhD-Math finding F3 (CRITICAL, 2026-05-31): the prior annotation cited
 * "all_agents_terminate" which does not exist in that file. The real theorems
 * are th_v18_15a..th_v18_15f. Status was falsely marked GREEN.
 *
 * These tests will FAIL if someone re-introduces the false annotation, catching
 * drift before it reaches main.
 *
 * Strike 3 (doctrine-grep): Run the doctrine-grep.yml CI gate on changed files.
 * See DOCTRINE_V7_FULL.md for the full banned-token regex. 0 hits required.
 *
 * Lean corpus reference: 749 declarations / 14 unique axioms / 163 sorries
 * @ c7c0ba17 (canonical HEAD 2026-05-31).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import * as fs from "fs";
import * as path from "path";
import { describe, it, expect } from "vitest";
import {
  runMultiAgentTermination,
  ouroborosAgents,
  type AgentSpec,
} from "../src/multi_agent_terminator";

// ---------------------------------------------------------------------------
// Helpers: read source annotation
// ---------------------------------------------------------------------------

const SRC_FILE = path.resolve(__dirname, "../src/multi_agent_terminator.ts");

function readAnnotations(): { theorem: string; status: string } {
  const src = fs.readFileSync(SRC_FILE, "utf-8");
  const theoremMatch = src.match(/@lean_theorem\s+(\S+)/);
  const statusMatch = src.match(/@lean_status\s+(\S+)/);
  return {
    theorem: theoremMatch?.[1] ?? "",
    status: statusMatch?.[1] ?? "",
  };
}

// ---------------------------------------------------------------------------
// Strike 1 — Binding annotation integrity tests
// ---------------------------------------------------------------------------

describe("lean_binding_drift — multi_agent_terminator.ts (PhD-Math F3)", () => {
  it("@lean_theorem must NOT cite the non-existent 'all_agents_terminate'", () => {
    const { theorem } = readAnnotations();
    expect(theorem).not.toBe("Lutar.Thesis.MultiAgent.all_agents_terminate");
    // Rationale: this identifier does not exist in TH_V18_15_MultiAgentFairness.lean.
    // PhD-Math Pass 1 Binding #1: grep confirms absence at c7c0ba17.
  });

  it("@lean_theorem must cite an identifier that exists in the Lean file", () => {
    const { theorem } = readAnnotations();
    // The only valid theorem names at c7c0ba17 are th_v18_15a..th_v18_15f.
    // Accept any of those or the corrected alias if it is later added.
    const KNOWN_REAL_THEOREMS = [
      "th_v18_15a_bounded_agent_terminates",
      "th_v18_15b_list_termination",
      "th_v18_15c_nil_terminates",
      "th_v18_15d_cons_bounded",
      "th_v18_15e_append_bounded",
      "th_v18_15f_fuel_monotone",
      // Future: once alias added in lutar-lean, add "all_agents_terminate" here
    ];
    const shortName = theorem.split(".").pop() ?? "";
    expect(KNOWN_REAL_THEOREMS).toContain(shortName);
  });

  it("@lean_status must NOT be a bare 'GREEN' while theorem name was absent", () => {
    const { status } = readAnnotations();
    // Until the all_agents_terminate alias is proven in lutar-lean and the
    // theorem name is updated back, status must be UNVERIFIED (or SORRY-TRACKED
    // if a sorry is present). A bare GREEN is a doctrine violation (§2 fake-green).
    expect(status).not.toBe("GREEN");
  });

  it("receipt.lean_theorem in runMultiAgentTermination output must match annotation", () => {
    // Property: the emitted DSSE receipt's lean_theorem must agree with the annotation.
    // Catches the case where annotation is fixed but runtime receipt still cites old name.
    const agents: AgentSpec[] = [{ id: "probe", fuel: 1, step: () => 1 }];
    const result = runMultiAgentTermination(agents);
    const { theorem } = readAnnotations();
    // The annotation is the source of truth. Receipt must match (modulo namespace prefix).
    const receiptShort = result.receipt.lean_theorem.split(".").pop() ?? "";
    const annotShort = theorem.split(".").pop() ?? "";
    expect(receiptShort).toBe(annotShort);
  });
});

// ---------------------------------------------------------------------------
// Strike 1 — Behavioral correctness (regression guard)
// The theorem semantics are: bounded agents terminate within fuel budget.
// ---------------------------------------------------------------------------

describe("runMultiAgentTermination — behavioral regression (th_v18_15b_list_termination)", () => {
  it("happy path: single agent fuel=5, consumes 1/step => terminates", () => {
    const agents: AgentSpec[] = [{ id: "a", fuel: 5, step: () => 1 }];
    const r = runMultiAgentTermination(agents);
    expect(r.allTerminated).toBe(true);
    expect(r.violations).toHaveLength(0);
    expect(r.traces[0]!.fuelConsumed).toBe(5);
  });

  it("edge case: single agent fuel=1 => terminates in exactly 1 step", () => {
    const agents: AgentSpec[] = [{ id: "b", fuel: 1, step: () => 1 }];
    const r = runMultiAgentTermination(agents);
    expect(r.allTerminated).toBe(true);
    expect(r.totalSteps).toBe(1);
  });

  it("failure path: step() returns 0 => precondition violated => throws", () => {
    const agents: AgentSpec[] = [{ id: "bad", fuel: 10, step: () => 0 }];
    expect(() => runMultiAgentTermination(agents)).toThrow(
      /must return integer ≥ 1/
    );
  });

  it("property: 7 Ouroboros organs with default fuel all terminate", () => {
    const result = runMultiAgentTermination(ouroborosAgents());
    expect(result.allTerminated).toBe(true);
    expect(result.violations).toHaveLength(0);
    for (const trace of result.traces) {
      expect(trace.terminatedWithin).toBe(true);
    }
  });
});
