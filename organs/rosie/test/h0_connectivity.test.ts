/**
 * Tests for Persistent Homology H₀ Connectivity Gate
 * Lean theorem: Lutar.Topology.PersistentHomologyChain.h0_at_lambda_threshold (GREEN)
 *
 * Property: β₀ = |V| − |{MST edges with weight ≤ Λ}| = number of connected components.
 */

import { describe, it, expect } from "vitest";
import {
  h0BettiNumber,
  h0FromPoints,
  h0PersistenceDiagram,
  type WeightedEdge,
} from "../src/topology/h0_connectivity";

// ---------------------------------------------------------------------------
// Deterministic cases
// ---------------------------------------------------------------------------

describe("h0BettiNumber — GREEN theorem h0_at_lambda_threshold", () => {
  it("single vertex: β₀ = 1 for any lambda", () => {
    const r = h0BettiNumber(1, [], 0);
    expect(r.betti0).toBe(1);
  });

  it("two vertices, edge weight 1.0, lambda=1.0: β₀ = 1", () => {
    const r = h0BettiNumber(2, [{ u: 0, v: 1, weight: 1.0 }], 1.0);
    expect(r.betti0).toBe(1);
  });

  it("two vertices, edge weight 2.0, lambda=1.0: β₀ = 2 (disconnected)", () => {
    const r = h0BettiNumber(2, [{ u: 0, v: 1, weight: 2.0 }], 1.0);
    expect(r.betti0).toBe(2);
  });

  it("complete triangle lambda=10: β₀ = 1", () => {
    const edges: WeightedEdge[] = [
      { u: 0, v: 1, weight: 1.0 },
      { u: 1, v: 2, weight: 1.5 },
      { u: 0, v: 2, weight: 2.0 },
    ];
    const r = h0BettiNumber(3, edges, 10);
    expect(r.betti0).toBe(1);
  });

  it("3 isolated vertices (no edges), any lambda: β₀ = 3", () => {
    const r = h0BettiNumber(3, [], 100);
    expect(r.betti0).toBe(3);
  });

  it("path graph 4 vertices, lambda=1.5: β₀ = 1", () => {
    // 0—1—2—3 all weight 1.0
    const edges: WeightedEdge[] = [
      { u: 0, v: 1, weight: 1.0 },
      { u: 1, v: 2, weight: 1.0 },
      { u: 2, v: 3, weight: 1.0 },
    ];
    const r = h0BettiNumber(4, edges, 1.5);
    expect(r.betti0).toBe(1);
    expect(r.activeMstEdges).toBe(3);
  });

  it("path graph 4 vertices, lambda=0.5: β₀ = 4 (all isolated)", () => {
    const edges: WeightedEdge[] = [
      { u: 0, v: 1, weight: 1.0 },
      { u: 1, v: 2, weight: 1.0 },
      { u: 2, v: 3, weight: 1.0 },
    ];
    const r = h0BettiNumber(4, edges, 0.5);
    expect(r.betti0).toBe(4);
    expect(r.activeMstEdges).toBe(0);
  });

  it("receipt contains correct lean_theorem", () => {
    const r = h0BettiNumber(2, [{ u: 0, v: 1, weight: 1.0 }], 1.0);
    expect(r.receipt.lean_theorem).toBe(
      "Lutar.Topology.PersistentHomologyChain.h0_at_lambda_threshold"
    );
    expect(r.receipt.formula).toBe("h0_at_lambda_threshold");
    expect(r.receipt.lean_file).toBe("Lutar/Topology/PersistentHomologyChain.lean");
    expect(r.receipt.inputs_hash).toHaveLength(64);
  });

  it("theorem: betti0 + activeMstEdges = vertexCount always", () => {
    const cases: Array<[number, WeightedEdge[], number]> = [
      [4, [{ u: 0, v: 1, weight: 1 }, { u: 1, v: 2, weight: 2 }, { u: 2, v: 3, weight: 3 }], 2.5],
      [5, [], 10],
      [3, [{ u: 0, v: 1, weight: 0.5 }, { u: 1, v: 2, weight: 1.5 }], 1.0],
    ];
    for (const [n, edges, lambda] of cases) {
      const r = h0BettiNumber(n, edges, lambda);
      expect(r.betti0 + r.activeMstEdges).toBe(r.vertexCount);
    }
  });
});

// ---------------------------------------------------------------------------
// h0FromPoints
// ---------------------------------------------------------------------------

describe("h0FromPoints", () => {
  it("4 points at corners of unit square, lambda=1.5: β₀ = 1", () => {
    const points: Array<[number, number]> = [
      [0, 0], [1, 0], [1, 1], [0, 1],
    ];
    const r = h0FromPoints(points, 1.5);
    expect(r.betti0).toBe(1);
  });

  it("4 widely-separated points, lambda=0.1: β₀ = 4", () => {
    const points: Array<[number, number]> = [
      [0, 0], [100, 0], [100, 100], [0, 100],
    ];
    const r = h0FromPoints(points, 0.1);
    expect(r.betti0).toBe(4);
  });

  it("2 points at distance 5.0, lambda=5.0: β₀ = 1", () => {
    const r = h0FromPoints([[0, 0], [5, 0]], 5.0);
    expect(r.betti0).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// h0PersistenceDiagram
// ---------------------------------------------------------------------------

describe("h0PersistenceDiagram", () => {
  it("path 0-1-2 with weights 1,2: diagram has 2 steps", () => {
    const diag = h0PersistenceDiagram(3, [
      { u: 0, v: 1, weight: 1.0 },
      { u: 1, v: 2, weight: 2.0 },
    ]);
    expect(diag[0]!.betti0).toBe(3);
    expect(diag[1]!.betti0).toBe(2);
    expect(diag[2]!.betti0).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Fuzz: 500 random graphs
// ---------------------------------------------------------------------------

describe("h0BettiNumber — 500 random graphs (theorem fuzz)", () => {
  it("β₀ + activeMstEdges = vertexCount for 500 random graphs", () => {
    let failures = 0;
    for (let i = 0; i < 500; i++) {
      const n = Math.floor(Math.random() * 10) + 2;
      const edges: WeightedEdge[] = [];
      for (let u = 0; u < n; u++) {
        for (let v = u + 1; v < n; v++) {
          if (Math.random() > 0.4) {
            edges.push({ u, v, weight: Math.random() * 10 });
          }
        }
      }
      const lambda = Math.random() * 10;
      const r = h0BettiNumber(n, edges, lambda);
      if (r.betti0 + r.activeMstEdges !== r.vertexCount) failures++;
      if (r.betti0 < 1) failures++; // always ≥ 1 connected component
    }
    expect(failures).toBe(0);
  });

  it("β₀ monotone non-increasing as lambda increases (persistence)", () => {
    let violations = 0;
    for (let i = 0; i < 200; i++) {
      const n = Math.floor(Math.random() * 8) + 2;
      const edges: WeightedEdge[] = [];
      for (let u = 0; u < n; u++) {
        for (let v = u + 1; v < n; v++) {
          edges.push({ u, v, weight: Math.random() * 10 });
        }
      }
      const lambdas = [1, 2, 4, 7, 10].map((l) => l as number);
      let prev = n;
      for (const lam of lambdas) {
        const r = h0BettiNumber(n, edges, lam);
        if (r.betti0 > prev) violations++;
        prev = r.betti0;
      }
    }
    expect(violations).toBe(0);
  });
});
