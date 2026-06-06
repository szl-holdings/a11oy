/**
 * Persistent Homology H₀ Connectivity Gate
 *
 * @lean_theorem Lutar.Topology.PersistentHomologyChain.h0_at_lambda_threshold
 * @lean_file    Lutar/Topology/PersistentHomologyChain.lean
 * @lean_status  GREEN — 0 sorries
 * @lean_commit  see LEAN_COMMIT_SHA env var; pin at CI time from lutar-lean/lean-toolchain
 *
 * Theorem (Edelsbrunner, Letscher, Zomorodian 2002 DCG 28(4):511–533):
 *   β₀(Rips_Λ(P)) = |V| − |{spanning tree edges with weight ≤ Λ}|
 *   The number of connected components at threshold Λ equals the number of vertices
 *   minus the number of Kruskal MST edges with weight ≤ Λ.
 *
 * Algorithm:
 *   1. Build complete weighted graph G = (V, E) with edge weights = distances
 *   2. Compute Kruskal MST (Union-Find)
 *   3. Count MST edges with weight ≤ Λ → call this m(Λ)
 *   4. β₀ = |V| − m(Λ)
 *
 * This matches the Lean proof: each edge addition in MST reduces β₀ by 1
 * (merges two components), proved by induction on the edge list.
 *
 * References:
 *   Edelsbrunner, Letscher, Zomorodian (2002) DCG 28(4):511–533
 *   Lutar/Topology/PersistentHomologyChain.lean
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import * as crypto from "crypto";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WeightedEdge {
  u: number;    // vertex index
  v: number;    // vertex index
  weight: number;
}

export interface H0Result {
  /** β₀ = number of connected components at threshold lambda */
  betti0: number;
  /** Number of vertices */
  vertexCount: number;
  /** The threshold used */
  lambda: number;
  /** Number of MST edges active (weight ≤ lambda) */
  activeMstEdges: number;
  /** The full MST edge list sorted by weight */
  mstEdges: WeightedEdge[];
  /** DSSE receipt */
  receipt: H0DsseReceipt;
}

export interface H0DsseReceipt {
  formula: string;
  lean_theorem: string;
  lean_file: string;
  lean_commit_sha: string;
  inputs_hash: string;
  output: {
    betti0: number;
    vertexCount: number;
    lambda: number;
    activeMstEdges: number;
  };
  ts: string;
}

// ---------------------------------------------------------------------------
// Union-Find (Kruskal MST support)
// ---------------------------------------------------------------------------

class UnionFind {
  private parent: number[];
  private rank: number[];

  constructor(n: number) {
    this.parent = Array.from({ length: n }, (_, i) => i);
    this.rank = new Array(n).fill(0);
  }

  find(x: number): number {
    if (this.parent[x] !== x) {
      this.parent[x] = this.find(this.parent[x]!);
    }
    return this.parent[x]!;
  }

  union(x: number, y: number): boolean {
    const px = this.find(x);
    const py = this.find(y);
    if (px === py) return false; // already in same component
    if (this.rank[px]! < this.rank[py]!) {
      this.parent[px] = py;
    } else if (this.rank[px]! > this.rank[py]!) {
      this.parent[py] = px;
    } else {
      this.parent[py] = px;
      this.rank[px]!++;
    }
    return true;
  }
}

// ---------------------------------------------------------------------------
// Kruskal MST
// ---------------------------------------------------------------------------

function kruskalMst(n: number, edges: WeightedEdge[]): WeightedEdge[] {
  const sorted = [...edges].sort((a, b) => a.weight - b.weight);
  const uf = new UnionFind(n);
  const mst: WeightedEdge[] = [];
  for (const e of sorted) {
    if (uf.union(e.u, e.v)) {
      mst.push(e);
      if (mst.length === n - 1) break; // MST complete
    }
  }
  return mst;
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
 * Compute H₀ Betti number (connected components) for the Rips complex at threshold Λ.
 *
 * @param vertexCount  Number of vertices in the graph
 * @param edges        Weighted edge list (need not be complete; missing edges = ∞ weight)
 * @param lambda       Distance threshold Λ for Rips complex
 *
 * @returns H0Result with β₀ and DSSE receipt.
 *
 * By the Lean theorem: β₀ = vertexCount − |{MST edges with weight ≤ lambda}|.
 *
 * @example
 * ```typescript
 * // Complete graph on 4 vertices, all weights 1.0
 * const r = h0BettiNumber(4, [
 *   { u: 0, v: 1, weight: 1.0 }, { u: 1, v: 2, weight: 1.0 },
 *   { u: 2, v: 3, weight: 1.0 }, { u: 0, v: 2, weight: 1.5 },
 * ], 1.0);
 * assert(r.betti0 === 1); // fully connected at Λ=1.0
 * ```
 */
export function h0BettiNumber(
  vertexCount: number,
  edges: WeightedEdge[],
  lambda: number
): H0Result {
  if (vertexCount < 0) throw new Error("h0BettiNumber: vertexCount must be ≥ 0");
  if (vertexCount === 0) {
    const receipt = makeEmptyReceipt(vertexCount, lambda);
    return { betti0: 0, vertexCount: 0, lambda, activeMstEdges: 0, mstEdges: [], receipt };
  }

  // Filter edges within the Rips threshold before MST (optimization; MST result is same)
  // Actually: we compute MST on all edges and then filter by weight ≤ lambda.
  // This is correct: Kruskal MST uses the globally lightest edges first.
  const mstEdges = kruskalMst(vertexCount, edges);
  const activeMstEdges = mstEdges.filter((e) => e.weight <= lambda).length;
  const betti0 = vertexCount - activeMstEdges;

  const inputs_hash = sha256Hex({ vertexCount, edges, lambda });
  const lean_commit_sha = process.env["LEAN_COMMIT_SHA"] ?? "unknown";

  const receipt: H0DsseReceipt = {
    formula: "h0_at_lambda_threshold",
    lean_theorem: "Lutar.Topology.PersistentHomologyChain.h0_at_lambda_threshold",
    lean_file: "Lutar/Topology/PersistentHomologyChain.lean",
    lean_commit_sha,
    inputs_hash,
    output: { betti0, vertexCount, lambda, activeMstEdges },
    ts: new Date().toISOString(),
  };

  return { betti0, vertexCount, lambda, activeMstEdges, mstEdges, receipt };
}

function makeEmptyReceipt(vertexCount: number, lambda: number): H0DsseReceipt {
  const lean_commit_sha = process.env["LEAN_COMMIT_SHA"] ?? "unknown";
  return {
    formula: "h0_at_lambda_threshold",
    lean_theorem: "Lutar.Topology.PersistentHomologyChain.h0_at_lambda_threshold",
    lean_file: "Lutar/Topology/PersistentHomologyChain.lean",
    lean_commit_sha,
    inputs_hash: sha256Hex({ vertexCount, lambda }),
    output: { betti0: 0, vertexCount, lambda, activeMstEdges: 0 },
    ts: new Date().toISOString(),
  };
}

/**
 * Build a complete Euclidean graph from 2D points and compute H₀.
 *
 * @param points  Array of [x, y] coordinates
 * @param lambda  Distance threshold
 */
export function h0FromPoints(
  points: Array<[number, number]>,
  lambda: number
): H0Result {
  const n = points.length;
  const edges: WeightedEdge[] = [];
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const dx = points[i]![0] - points[j]![0];
      const dy = points[i]![1] - points[j]![1];
      edges.push({ u: i, v: j, weight: Math.sqrt(dx * dx + dy * dy) });
    }
  }
  return h0BettiNumber(n, edges, lambda);
}

/**
 * Compute the full β₀ persistence diagram (betti0 vs lambda for each MST edge weight).
 * Returns pairs [lambda_i, betti0_i] sorted by lambda.
 */
export function h0PersistenceDiagram(
  vertexCount: number,
  edges: WeightedEdge[]
): Array<{ lambda: number; betti0: number }> {
  const mstEdges = kruskalMst(vertexCount, edges).sort(
    (a, b) => a.weight - b.weight
  );
  const diagram: Array<{ lambda: number; betti0: number }> = [];
  let components = vertexCount;
  for (const e of mstEdges) {
    diagram.push({ lambda: e.weight, betti0: components });
    components--;
  }
  // At lambda = max weight, all vertices connected → betti0 = 1 (if connected graph)
  if (mstEdges.length > 0) {
    diagram.push({ lambda: Infinity, betti0: components });
  }
  return diagram;
}
