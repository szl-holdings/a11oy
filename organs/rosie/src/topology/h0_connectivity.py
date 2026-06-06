"""rosie.src.topology.h0_connectivity — H₀ Betti number computation.

Doctrine v6 | SPDX-License-Identifier: BSL-1.1
Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings

Computes the zeroth Betti number β₀ (number of connected components) of
the Vietoris–Rips complex of an organ graph at a given trust threshold Λ.

Formula:
    β₀(Rips_Λ) = |V| − |edges in MST with weight ≤ Λ|

which equals the number of connected components when edges with weight ≤ Λ
are admitted into the complex.

Lean theorem: Lutar.Topology.PersistentHomologyChain.h0_at_lambda_threshold
Lean file:    Lutar/Topology/PersistentHomologyChain.lean
Lean line:    ~80
Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
Status:       GREEN

Algorithm:
  1. Build an edge-weighted graph from (node, edge, weight) triples.
  2. At threshold Λ, include only edges with weight ≤ Λ.
  3. Use union-find to count connected components.
  4. β₀ = number of components.
  5. Emit a DSSE receipt per computation.

Reference:
  Edelsbrunner, H., Letscher, D., Zomorodian, A. (2002)
  "Topological Persistence and Simplification,"
  Discrete & Computational Geometry 28(4):511–533.
  DOI: 10.1007/s00454-002-2885-2

  Edelsbrunner, H. & Harer, J. (2010)
  "Computational Topology: An Introduction," AMS.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LUTAR_LEAN_HEAD_SHA: str = "c4d13795689601324fce0236351bfe0ade990a43"

H0_THEOREM: str = (
    "Lutar.Topology.PersistentHomologyChain.h0_at_lambda_threshold"
)
H0_LEAN_FILE: str = "Lutar/Topology/PersistentHomologyChain.lean"
H0_LEAN_LINE: int = 80
H0_STATUS: str = "GREEN"


# ---------------------------------------------------------------------------
# DSSE receipt helpers
# ---------------------------------------------------------------------------

def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _inputs_hash(inputs: dict[str, Any]) -> str:
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
    return _sha256_hex(canonical)


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _dsse_receipt(
    inputs: dict[str, Any],
    output: dict[str, Any],
    *,
    lean_commit_sha: str = LUTAR_LEAN_HEAD_SHA,
) -> dict[str, Any]:
    """Build a DSSE receipt for one H₀ computation.

    Lean theorem: Lutar.Topology.PersistentHomologyChain.h0_at_lambda_threshold
    Lean file:    Lutar/Topology/PersistentHomologyChain.lean:80
    Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
    Status:       GREEN
    """
    return {
        "theorem": H0_THEOREM,
        "lean_file": H0_LEAN_FILE,
        "lean_line": H0_LEAN_LINE,
        "lean_status": H0_STATUS,
        "lean_commit_sha": lean_commit_sha,
        "inputs_hash": _inputs_hash(inputs),
        "output": output,
        "ts": _iso_now(),
    }


# ---------------------------------------------------------------------------
# Union-Find (for connected-component counting)
# ---------------------------------------------------------------------------

class _UnionFind:
    """Path-compressed weighted union-find for component counting.

    This is the standard algorithm; component count starts at n and
    decreases by 1 on each successful union.
    """

    def __init__(self, nodes: list[str]) -> None:
        self._parent: dict[str, str] = {n: n for n in nodes}
        self._rank: dict[str, int] = {n: 0 for n in nodes}
        self._count: int = len(nodes)

    def find(self, x: str) -> str:
        """Return root of x with path compression."""
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])
        return self._parent[x]

    def union(self, x: str, y: str) -> bool:
        """Union x and y. Returns True if they were in different components."""
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False
        if self._rank[rx] < self._rank[ry]:
            rx, ry = ry, rx
        self._parent[ry] = rx
        if self._rank[rx] == self._rank[ry]:
            self._rank[rx] += 1
        self._count -= 1
        return True

    @property
    def component_count(self) -> int:
        return self._count


# ---------------------------------------------------------------------------
# Graph types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WeightedEdge:
    """An undirected weighted edge in the organ graph.

    Attributes:
        u:      Source node identifier.
        v:      Target node identifier.
        weight: Non-negative edge weight (trust distance between organs).
    """
    u: str
    v: str
    weight: float

    def __post_init__(self) -> None:
        if self.weight < 0:
            raise ValueError(f"Edge weight must be ≥ 0, got {self.weight!r}")


# ---------------------------------------------------------------------------
# H₀ computation
# ---------------------------------------------------------------------------

@dataclass
class H0Result:
    """Result of a single H₀ Betti number computation.

    Attributes:
        lambda_threshold: Trust threshold Λ used.
        h0:               β₀ = number of connected components.
        n_nodes:          Total number of nodes.
        n_edges_admitted: Number of edges with weight ≤ Λ.
        n_edges_total:    Total number of edges in the graph.
        fragmented:       True if β₀ > 1 (organ mesh fragmented at this Λ).
        components:       List of node sets (one per component).
        dsse_receipt:     DSSE receipt for this computation.
    """
    lambda_threshold: float
    h0: int
    n_nodes: int
    n_edges_admitted: int
    n_edges_total: int
    fragmented: bool
    components: list[list[str]]
    dsse_receipt: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_h0(
    nodes: list[str],
    edges: list[WeightedEdge],
    lambda_threshold: float,
    *,
    lean_commit_sha: str = LUTAR_LEAN_HEAD_SHA,
) -> H0Result:
    """Compute β₀ (number of connected components) at trust threshold Λ.

    Formula (Edelsbrunner 2002):
        β₀ = |V| − |MST edges with weight ≤ Λ|
           = number of connected components of Rips_Λ graph

    Implementation: admit all edges with weight ≤ Λ; count components with
    union-find. β₀ equals the number of distinct roots.

    Lean theorem: Lutar.Topology.PersistentHomologyChain.h0_at_lambda_threshold
    Lean file:    Lutar/Topology/PersistentHomologyChain.lean:80
    Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
    Status:       GREEN

    Args:
        nodes:            List of node identifiers (unique).
        edges:            List of :class:`WeightedEdge`.
        lambda_threshold: Trust threshold Λ ≥ 0. Edges with weight ≤ Λ are admitted.
        lean_commit_sha:  lutar-lean HEAD SHA.

    Returns:
        :class:`H0Result` with β₀ and audit trail.

    Raises:
        ValueError: If any edge references a node not in ``nodes``,
                    or if ``lambda_threshold < 0``.
    """
    if lambda_threshold < 0:
        raise ValueError(f"lambda_threshold must be ≥ 0, got {lambda_threshold!r}")
    node_set = set(nodes)
    for edge in edges:
        for endpoint in (edge.u, edge.v):
            if endpoint not in node_set:
                raise ValueError(
                    f"Edge endpoint {endpoint!r} not in nodes list. "
                    "All endpoints must be declared as nodes."
                )

    uf = _UnionFind(list(nodes))
    admitted: list[WeightedEdge] = []

    # Admit edges with weight ≤ Λ (Rips complex threshold).
    for edge in edges:
        if edge.weight <= lambda_threshold:
            uf.union(edge.u, edge.v)
            admitted.append(edge)

    h0 = uf.component_count

    # Extract component lists.
    comp_map: dict[str, list[str]] = {}
    for node in nodes:
        root = uf.find(node)
        comp_map.setdefault(root, []).append(node)
    components = [sorted(members) for members in comp_map.values()]
    components.sort(key=lambda c: c[0])

    inp = {
        "n_nodes": len(nodes),
        "n_edges_total": len(edges),
        "lambda_threshold": lambda_threshold,
        "nodes_hash": _sha256_hex(json.dumps(sorted(nodes))),
    }
    out = {
        "h0": h0,
        "n_edges_admitted": len(admitted),
        "fragmented": h0 > 1,
    }

    return H0Result(
        lambda_threshold=lambda_threshold,
        h0=h0,
        n_nodes=len(nodes),
        n_edges_admitted=len(admitted),
        n_edges_total=len(edges),
        fragmented=h0 > 1,
        components=components,
        dsse_receipt=_dsse_receipt(inp, out, lean_commit_sha=lean_commit_sha),
    )


def compute_h0_persistence(
    nodes: list[str],
    edges: list[WeightedEdge],
    lambda_values: list[float],
    *,
    lean_commit_sha: str = LUTAR_LEAN_HEAD_SHA,
) -> list[H0Result]:
    """Compute β₀ at multiple Λ values (H₀ persistence diagram).

    Sweeps Λ from smallest to largest, computing β₀ at each threshold.
    The resulting list traces how the organ mesh becomes more connected as
    the trust threshold increases.

    Lean theorem: Lutar.Topology.PersistentHomologyChain.h0_at_lambda_threshold
    Lean file:    Lutar/Topology/PersistentHomologyChain.lean:80
    Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
    Status:       GREEN

    Args:
        nodes:         Node identifiers.
        edges:         Edge list with weights.
        lambda_values: List of Λ thresholds to evaluate (need not be sorted).
        lean_commit_sha: lutar-lean HEAD SHA.

    Returns:
        List of :class:`H0Result`, one per Λ value, sorted ascending.
    """
    return [
        compute_h0(nodes, edges, lam, lean_commit_sha=lean_commit_sha)
        for lam in sorted(lambda_values)
    ]


def organ_connectivity_alert(
    nodes: list[str],
    edges: list[WeightedEdge],
    lambda_threshold: float,
    *,
    lean_commit_sha: str = LUTAR_LEAN_HEAD_SHA,
) -> dict[str, Any]:
    """Check organ mesh connectivity and return an alert if fragmented.

    β₀ > 1 indicates a topology-grade connectivity anomaly in the organ
    mesh at the given trust threshold. This is a Lean-backed anomaly claim.

    Lean theorem: Lutar.Topology.PersistentHomologyChain.h0_at_lambda_threshold
    Lean file:    Lutar/Topology/PersistentHomologyChain.lean:80
    Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
    Status:       GREEN

    Args:
        nodes:            Node identifiers.
        edges:            Edge list.
        lambda_threshold: Trust threshold Λ.
        lean_commit_sha:  lutar-lean HEAD SHA.

    Returns:
        Dict with keys:
            fragmented      — bool
            h0              — number of components
            alert_message   — human-readable alert (empty if not fragmented)
            dsse_receipt    — DSSE receipt
    """
    result = compute_h0(nodes, edges, lambda_threshold, lean_commit_sha=lean_commit_sha)
    alert = ""
    if result.fragmented:
        alert = (
            f"TOPOLOGY ALERT: organ mesh fragmented at Λ={lambda_threshold}. "
            f"β₀={result.h0} components (expected 1). "
            f"Isolated components: {result.components}. "
            f"Backed by {H0_THEOREM}."
        )
    return {
        "fragmented": result.fragmented,
        "h0": result.h0,
        "alert_message": alert,
        "components": result.components,
        "dsse_receipt": result.dsse_receipt,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 72)
    print("  rosie — H₀ Connectivity | Doctrine v6 | GREEN")
    print("=" * 72)

    # Demo: star topology (connected) vs split topology.
    nodes = ["sentra", "amaru", "rosie", "ouroboros", "terra"]
    edges_connected = [
        WeightedEdge("sentra", "amaru", 0.1),
        WeightedEdge("amaru", "rosie", 0.2),
        WeightedEdge("rosie", "ouroboros", 0.3),
        WeightedEdge("ouroboros", "terra", 0.4),
    ]
    edges_split = [
        WeightedEdge("sentra", "amaru", 0.1),
        # rosie, ouroboros, terra disconnected at Λ=0.15
        WeightedEdge("ouroboros", "terra", 0.4),
    ]

    for label, edges, lam in [
        ("Connected at Λ=0.5", edges_connected, 0.5),
        ("Fragmented at Λ=0.15", edges_split, 0.15),
    ]:
        r = compute_h0(nodes, edges, lam)
        print(f"\n  {label}")
        print(f"    β₀ = {r.h0}  (fragmented={r.fragmented})")
        print(f"    components = {r.components}")
        print(f"    edges admitted = {r.n_edges_admitted}/{r.n_edges_total}")
        if r.fragmented:
            alert = organ_connectivity_alert(nodes, edges, lam)
            print(f"    ALERT: {alert['alert_message'][:80]}...")
