// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173

import { describe, it, expect } from "vitest";
import { validateEnvelope, makeEnvelope } from "../src/envelope.js";
import { REPLAY_ROOT } from "../../formulas/src/index.js";

// ---------------------------------------------------------------------------
// goodAxes — all 9 canonical axes at passing scores.
// makeEnvelope REQUIRES all 9 axes — do not omit any.
// ---------------------------------------------------------------------------

const goodAxes = {
  semanticCoherence:    0.95,
  empiricalGrounding:   0.92,
  logicalConsistency:   0.94,
  moralGrounding:       0.97,  // hard floor 0.95
  epistemicHumility:    0.91,
  measurabilityHonesty: 0.96,  // hard floor 0.95
  reversibility:        0.93,
  provenance:           0.92,
  replayability:        0.94,
} as const;

describe("M2M envelope", () => {
  it("clean envelope validates", () => {
    const e = makeEnvelope({
      agent: "claude",
      payload: { hello: "world" },
      claims: [{ text: "test", evidence: [{ kind: "i_dont_know" }] }],
      axes: goodAxes,
    });
    const r = validateEnvelope(e);
    expect(r.ok).toBe(true);
  });

  it("rejects mismatched replay root", () => {
    const e = makeEnvelope({ agent: "claude", payload: {}, claims: [{ text: "x", evidence: [{kind:"i_dont_know"}] }], axes: goodAxes });
    (e as any).replayRoot = "0000000000000000000000000000000000000000000000000000000000000000";
    const r = validateEnvelope(e);
    expect(r.ok).toBe(false);
    expect(r.rejections.some(s => s.startsWith("R1"))).toBe(true);
  });

  it("rejects claim with no evidence", () => {
    const e = makeEnvelope({
      agent: "claude",
      payload: {},
      claims: [{ text: "fabricated", evidence: [] }],
      axes: goodAxes,
    });
    const r = validateEnvelope(e);
    expect(r.ok).toBe(false);
    expect(r.rejections.some(s => s.startsWith("R2"))).toBe(true);
  });

  it("rejects self-citation from LLM domain", () => {
    const e = makeEnvelope({
      agent: "claude",
      payload: {},
      claims: [{ text: "x", evidence: [{ kind: "url", url: "https://chat.openai.com/foo" }] }],
      axes: goodAxes,
    });
    const r = validateEnvelope(e);
    expect(r.ok).toBe(false);
    expect(r.rejections.some(s => s.startsWith("R3"))).toBe(true);
  });

  it("rejects forbidden pattern in payload", () => {
    const e = makeEnvelope({
      agent: "claude",
      payload: { name: "AlloyScape rebrand" },
      claims: [{ text: "x", evidence: [{ kind: "i_dont_know" }] }],
      axes: goodAxes,
    });
    const r = validateEnvelope(e);
    expect(r.ok).toBe(false);
    expect(r.rejections.some(s => s.startsWith("R6"))).toBe(true);
  });

  it("rejects Claude Mythos Preview literal (no allowlist exemptions)", () => {
    const e = makeEnvelope({
      agent: "claude",
      payload: { model: "Claude Mythos Preview" },
      claims: [{ text: "x", evidence: [{ kind: "i_dont_know" }] }],
      axes: goodAxes,
    });
    const r = validateEnvelope(e);
    expect(r.ok).toBe(false);
    expect(r.rejections.some(s => s.startsWith("R6"))).toBe(true);
  });

  it("rejects nonce replay", () => {
    const e1 = makeEnvelope({ agent: "claude", payload: {}, claims: [{text:"x",evidence:[{kind:"i_dont_know"}]}], axes: goodAxes });
    expect(validateEnvelope(e1).ok).toBe(true);
    const e2 = { ...e1 };
    expect(validateEnvelope(e2).ok).toBe(false);
  });

  it("rejects lambda below 0.90", () => {
    const e = makeEnvelope({
      agent: "claude",
      payload: {},
      claims: [{ text: "x", evidence: [{ kind: "i_dont_know" }] }],
      axes: { ...goodAxes, semanticCoherence: 0.85 },
    });
    const r = validateEnvelope(e);
    expect(r.ok).toBe(false);
    expect(r.rejections.some(s => s.startsWith("R7"))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// P1 fixes: R4/R5/R7/R8/R10 surgical tests
// goodAxes provides all 9 canonical axes at passing scores.
// makeEnvelope now REQUIRES all 9 axes — do not omit any.
// ---------------------------------------------------------------------------

describe("M2M envelope — P1 rejection rules", () => {
  it("R4: agent=operator produces R4 rejection", () => {
    const e = makeEnvelope({
      agent: "operator" as any,
      payload: {},
      claims: [{ text: "x", evidence: [{ kind: "i_dont_know" }] }],
      axes: goodAxes,
    });
    const r = validateEnvelope(e);
    expect(r.ok).toBe(false);
    expect(r.rejections.some(s => s.startsWith("R4"))).toBe(true);
  });

  it("R5: forbiddenScanned=false produces R5 rejection", () => {
    const e = makeEnvelope({
      agent: "claude",
      payload: {},
      claims: [{ text: "x", evidence: [{ kind: "i_dont_know" }] }],
      axes: goodAxes,
    });
    // Bypass makeEnvelope's hardcoded true by mutating after construction
    (e as any).doctrine.forbiddenScanned = false;
    const r = validateEnvelope(e);
    expect(r.ok).toBe(false);
    expect(r.rejections.some(s => s.startsWith("R5"))).toBe(true);
  });

  it("R7: omitting doctrine.lambda produces R7 rejection", () => {
    const e = makeEnvelope({
      agent: "claude",
      payload: {},
      claims: [{ text: "x", evidence: [{ kind: "i_dont_know" }] }],
      axes: goodAxes,
    });
    delete (e as any).doctrine.lambda;
    const r = validateEnvelope(e);
    expect(r.ok).toBe(false);
    expect(r.rejections.some(s => s.startsWith("R7") && s.includes("doctrine.lambda is required"))).toBe(true);
  });

  it("R8: omitting doctrine.axes produces R8 rejection", () => {
    const e = makeEnvelope({
      agent: "claude",
      payload: {},
      claims: [{ text: "x", evidence: [{ kind: "i_dont_know" }] }],
      axes: goodAxes,
    });
    delete (e as any).doctrine.axes;
    const r = validateEnvelope(e);
    expect(r.ok).toBe(false);
    expect(r.rejections.some(s => s.startsWith("R8") && s.includes("doctrine.axes is required"))).toBe(true);
  });

  it("R10: ts 15 minutes in the past produces R10 rejection", () => {
    const pastTs = new Date(Date.now() - 15 * 60 * 1000).toISOString();
    const e = makeEnvelope({
      agent: "claude",
      payload: {},
      claims: [{ text: "x", evidence: [{ kind: "i_dont_know" }] }],
      axes: goodAxes,
      ts: pastTs,
    });
    const r = validateEnvelope(e);
    expect(r.ok).toBe(false);
    expect(r.rejections.some(s => s.startsWith("R10") && s.includes("ts > 10min in the past"))).toBe(true);
  });

  it("R10: ts 2 minutes in the future produces R10 rejection", () => {
    const futureTs = new Date(Date.now() + 2 * 60 * 1000).toISOString();
    const e = makeEnvelope({
      agent: "claude",
      payload: {},
      claims: [{ text: "x", evidence: [{ kind: "i_dont_know" }] }],
      axes: goodAxes,
      ts: futureTs,
    });
    const r = validateEnvelope(e);
    expect(r.ok).toBe(false);
    expect(r.rejections.some(s => s.startsWith("R10") && s.includes("ts > 60s in the future"))).toBe(true);
  });
});
