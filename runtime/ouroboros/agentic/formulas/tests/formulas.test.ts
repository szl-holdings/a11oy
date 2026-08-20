// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173

import { describe, it, expect } from "vitest";
import {
  lambdaGate, mkAxisScore, mkReplaySha, mkDOI, mkLambda,
  doiBind, doiResolve, closure, compose, identity, confluence,
  bekensteinBound, bekensteinRespected, gradedNorm, linearReceipt,
  spanStart, spanEnd, fgDerive, fgSafety,
} from "../src/index.js";

const fullAxes = (overrides: Partial<Record<string, number>> = {}) => ({
  semanticCoherence:    mkAxisScore(overrides.semanticCoherence    ?? 0.95),
  empiricalGrounding:   mkAxisScore(overrides.empiricalGrounding   ?? 0.92),
  logicalConsistency:   mkAxisScore(overrides.logicalConsistency   ?? 0.94),
  moralGrounding:       mkAxisScore(overrides.moralGrounding       ?? 0.97),
  epistemicHumility:    mkAxisScore(overrides.epistemicHumility    ?? 0.91),
  measurabilityHonesty: mkAxisScore(overrides.measurabilityHonesty ?? 0.96),
  reversibility:        mkAxisScore(overrides.reversibility        ?? 0.93),
  provenance:           mkAxisScore(overrides.provenance           ?? 0.92),
  replayability:        mkAxisScore(overrides.replayability        ?? 0.94),
});

describe("TH1 lambda gate", () => {
  it("passes when all axes meet thresholds", () => {
    const r = lambdaGate(fullAxes());
    expect(r.pass).toBe(true);
    expect(r.failures).toHaveLength(0);
  });
  it("fails when moralGrounding < 0.95 hard floor", () => {
    const r = lambdaGate(fullAxes({ moralGrounding: 0.94 }));
    expect(r.pass).toBe(false);
    expect(r.failures[0].axis).toBe("moralGrounding");
  });
  it("fails when measurabilityHonesty < 0.95", () => {
    const r = lambdaGate(fullAxes({ measurabilityHonesty: 0.93 }));
    expect(r.pass).toBe(false);
  });
  it("fails when any single axis < 0.90", () => {
    const r = lambdaGate(fullAxes({ semanticCoherence: 0.89 }));
    expect(r.pass).toBe(false);
  });
  it("returns lambda as the min", () => {
    const r = lambdaGate(fullAxes({ semanticCoherence: 0.91 }));
    expect(r.lambda).toBe(0.91);
  });
});

describe("TH2 DOI bind", () => {
  const SHA = mkReplaySha("1ed4d253e876f428c6e182f8ed8a569585442556b339529bbf8ec2522581698b");
  it("binds valid DOIs", () => {
    const r = doiBind("10.5281/zenodo.20162352", SHA);
    expect(r.bound).toBe("10.5281/zenodo.20162352");
    expect(r.idempotent).toBe(false);
  });
  it("is idempotent for same SHA", () => {
    const r = doiBind("10.5281/zenodo.20162352", SHA);
    expect(r.idempotent).toBe(true);
  });
  it("rejects invalid DOIs", () => {
    expect(() => doiBind("not-a-doi", SHA)).toThrow();
  });
  it("resolves", () => {
    expect(doiResolve("10.5281/zenodo.20162352")).toBe(SHA);
  });
});

describe("TH3 closure", () => {
  it("converges on extensive monotone step", () => {
    const seed = new Set([1]);
    const step = (s: Set<number>) => {
      const n = new Set(s);
      for (const x of s) if (x < 10) n.add(x + 1);
      return n;
    };
    const out = closure(seed, step);
    expect(out.size).toBe(10);
  });
});

describe("TH4 category", () => {
  it("identity is neutral on the left", () => {
    const f = (x: number) => x * 2;
    expect(compose(identity, f)(3)).toBe(6);
  });
  it("identity is neutral on the right", () => {
    const f = (x: number) => x * 2;
    expect(compose(f, identity)(3)).toBe(6);
  });
  it("associativity holds", () => {
    const f = (x: number) => x + 1;
    const g = (x: number) => x * 2;
    const h = (x: number) => x - 3;
    const lhs = compose(h, compose(g, f))(5);
    const rhs = compose(compose(h, g), f)(5);
    expect(lhs).toBe(rhs);
  });
});

describe("TH5 confluence", () => {
  it("two rewrites converge", () => {
    const eq = (a: number, b: number) => a === b;
    const r = confluence(10, x => x - 1, x => x - 1, eq);
    expect(r.converged).toBe(true);
  });

  it("divergent rewrites converge to common normal form (start=16, halve vs subtract-8)", () => {
    // rewriteA: x => x / 2  (halve)
    // rewriteB: x => x - 8  (subtract 8)
    // start = 16 -> after one step: a=8, b=8 -> converged
    // Tests genuine convergence from structurally different reduction paths.
    const eq = (a: number, b: number) => a === b;
    const r = confluence(
      16,
      (x: number) => x / 2,
      (x: number) => x - 8,
      eq,
    );
    expect(r.converged).toBe(true);
    expect(r.steps).toBe(1);
    expect(r.normalForm).toBe(8);
  });
});

describe("TH6 Bekenstein", () => {
  it("returns positive bits for valid R, E", () => {
    const b = bekensteinBound(1, 1);
    expect(b).toBeGreaterThan(0);
  });
  it("respects bound at sane values", () => {
    expect(bekensteinRespected(1e10 as any, 1, 1)).toBe(true);
  });
  it("rejects R ≤ 0", () => {
    expect(() => bekensteinBound(0, 1)).toThrow();
  });
  it("rejects E ≤ 0", () => {
    expect(() => bekensteinBound(1, 0)).toThrow();
  });
});

describe("TH7 branded types", () => {
  it("mkLambda accepts 0..1", () => {
    expect(mkLambda(0.5)).toBe(0.5);
  });
  it("mkLambda rejects > 1", () => {
    expect(() => mkLambda(1.1)).toThrow();
  });
  it("mkReplaySha requires 64 hex", () => {
    expect(() => mkReplaySha("abc")).toThrow();
  });
  it("mkDOI requires proper format", () => {
    expect(() => mkDOI("not a doi")).toThrow();
    expect(mkDOI("10.5281/zenodo.1234")).toBe("10.5281/zenodo.1234");
  });
});

describe("TH8 graded norm + linear receipt", () => {
  it("graded norm scales by 2^-grade", () => {
    expect(gradedNorm({ grade: 0, value: 4 })).toBe(4);
    expect(gradedNorm({ grade: 1, value: 4 })).toBe(2);
    expect(gradedNorm({ grade: 2, value: 4 })).toBe(1);
  });
  it("linear receipt holds for simple combinations", () => {
    const r = linearReceipt(1, { grade: 1, value: 2 }, 1, { grade: 1, value: 3 });
    expect(r.linear).toBe(true);
  });
});

describe("VSP span", () => {
  it("opens and closes with replay-root stamp", () => {
    const s = spanStart("test", "TH1", { foo: "bar" });
    const e = spanEnd(s);
    expect(e.replayRoot).toMatch(/^1ed4d253/);
    expect(e.endNs).toBeDefined();
  });
});

describe("FG derive + safety", () => {
  it("derive produces 3 derived gauges in 0..1", () => {
    const g = {
      capability: 0.9, alignment: 0.92, replayHealth: 0.95,
      doctrineDrift: 0.05, testCoverage: 0.88, ciHealth: 0.95,
      scorecardScore: 0.78, deployFreshness: 0.9, depDrift: 0.1,
      vulnPressure: 0.05, latencyP95Ms: 120, errorRate: 0.01,
    };
    const d = fgDerive(g);
    expect(d.netHealth).toBeGreaterThanOrEqual(0);
    expect(d.netHealth).toBeLessThanOrEqual(1);
  });
  it("safety gates compute correctly", () => {
    const ok = fgSafety(fullAxes(), true);
    expect(ok.lambdaFloorOk).toBe(true);
    expect(ok.moralFloorOk).toBe(true);
    expect(ok.measureFloorOk).toBe(true);
    expect(ok.replayOk).toBe(true);
  });
  it("safety fails when moral floor breached", () => {
    const bad = fgSafety(fullAxes({ moralGrounding: 0.94 }), true);
    expect(bad.moralFloorOk).toBe(false);
  });
});
