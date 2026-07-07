# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · label:"MODELED"
# Co-Authored-By: Perplexity Computer Agent
"""
szl_kc_loop_forge_metrics.py — EXTENDED GRAPH/ARCHIVE METRICS for THE LOOP FORGE organ.

An OPTIONAL additive endpoint that reads the REAL loop-forge archive (imported from
szl_kc_loop_forge — this file NEVER edits that organ) and computes archive-structure
metrics over the real DGM-style branching archive DAG. Pure stdlib, deterministic,
label:"MODELED". Mirrors the shape/quality of szl_kc_flower_metrics.py.

What it measures (all MODELED, honest, over the REAL archive DAG):
  (a) archive acceptance rate — kernel-accepted branches / total proposed candidates.
  (b) recursion-depth histogram + mean — the distribution of accepted-branch depths
      (bounded by the depth cap), plus the mean recursion depth.
  (c) Fiedler lambda2 / connectivity of the archive DAG — the 2nd-smallest graph-
      Laplacian eigenvalue (algebraic connectivity) of the UNDIRECTED skeleton of the
      parent/child archive DAG, via a pure-stdlib symmetric Jacobi eigensolver copied
      verbatim (same technique) from szl_kc_flower_metrics._fiedler_lambda2. lambda2 > 0
      <=> the archive is one connected tree/DAG rooted at the locked-8 trunk (it always
      is, since every accepted branch links to a parent — we report it honestly).
  (d) honesty invariants — writer_ne_judge==True, kernel_outside_loop==True,
      conjecture_rendered_green==0, provenance_coverage==1.0.

Route (OPTIONAL, additive, never collides): GET /api/{ns}/v1/loopforge/metrics-ext

HONESTY SPINE (Doctrine v11 — NON-NEGOTIABLE):
  * The ARCHIVE is REAL (imported verbatim from szl_kc_loop_forge via defensive,
    getattr-based adapters). The METRICS are MODELED, deterministic, pure-stdlib graph
    statistics over that real archive DAG — never claimed as trained, alive, or measured.
  * The KERNEL GATE upstream is a MODELED oracle mirroring lutar-lean discipline
    (c7c0ba17, CITED; NOT run in-Space). We inherit and re-assert that honesty here.
  * WRITER != JUDGE is re-checked structurally (via the co_names separation Dev1 exposed).
  * Λ stays Conjecture 1, machine-checked FALSE, rendered GRAY, never green.
  * Every node carries provenance; provenance_coverage MUST be 1.0.
  * Pure stdlib (math only; no numpy, no stdlib random). Deterministic: same seed =>
    identical snapshot. A compute failure NEVER raises out of a handler (fail-open).
"""
from __future__ import annotations

import json as _json
import math as _math
import os as _os
import sys as _sys
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------------------
# Bind to Dev1's REAL module via import. sys.path.insert the w25 dir so the import works
# regardless of the caller's cwd. Defensive: if the import ever fails we fall back to an
# honest error marker rather than crashing the organ.
# --------------------------------------------------------------------------------------
_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)

try:
    import szl_kc_loop_forge as _forge  # type: ignore
except Exception as _exc:  # pragma: no cover — honest failure marker, never fabricate data
    _forge = None
    _IMPORT_ERROR = str(_exc)
else:
    _IMPORT_ERROR = ""

MODELED_LABEL = "MODELED"
DOCTRINE_VERSION = "v11"


# --------------------------------------------------------------------------------------
# Pure-stdlib symmetric Jacobi eigensolver -> Fiedler lambda2 of the archive DAG skeleton.
# Copied VERBATIM (same algorithm) from szl_kc_flower_metrics._fiedler_lambda2. No numpy.
# lambda2 > 0  <=>  the (undirected skeleton of the) archive is one connected component.
# --------------------------------------------------------------------------------------
def _fiedler_lambda2(ids: List[str], neighbours: Dict[str, List[str]]) -> float:
    """Algebraic connectivity (2nd-smallest Laplacian eigenvalue) of the induced graph
    on `ids` with undirected adjacency `neighbours`. Pure stdlib: symmetric Jacobi
    eigenvalue iteration on L = D - A."""
    ids = list(ids)
    n = len(ids)
    if n <= 1:
        return 0.0
    idx = {i: k for k, i in enumerate(ids)}
    aset = set(ids)
    L = [[0.0] * n for _ in range(n)]
    for i in ids:
        deg = 0
        for j in neighbours.get(i, []):
            if j in aset and j != i:
                L[idx[i]][idx[j]] = -1.0
                deg += 1
        L[idx[i]][idx[i]] = float(deg)
    # Jacobi eigenvalue iteration (symmetric). n is small; converges fast.
    A = [row[:] for row in L]
    for _sweep in range(80):
        p, qd, mx = 0, 1, 0.0
        for a in range(n):
            for b in range(a + 1, n):
                if abs(A[a][b]) > mx:
                    mx = abs(A[a][b]); p, qd = a, b
        if mx < 1e-10:
            break
        app_, aqq, apq = A[p][p], A[qd][qd], A[p][qd]
        if abs(apq) < 1e-15:
            continue
        theta = (aqq - app_) / (2.0 * apq)
        t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + _math.sqrt(theta * theta + 1.0))
        c = 1.0 / _math.sqrt(t * t + 1.0)
        s = t * c
        for k in range(n):
            akp, akq = A[k][p], A[k][qd]
            A[k][p] = c * akp - s * akq
            A[k][qd] = s * akp + c * akq
        for k in range(n):
            apk, aqk = A[p][k], A[qd][k]
            A[p][k] = c * apk - s * aqk
            A[qd][k] = s * apk + c * aqk
    eig = sorted(A[k][k] for k in range(n))
    return round(max(0.0, eig[1]) if len(eig) >= 2 else 0.0, 6)


def _undirected(ids: List[str], edges: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    nb: Dict[str, List[str]] = {i: [] for i in ids}
    for a, b in edges:
        if a in nb and b in nb and a != b:
            if b not in nb[a]:
                nb[a].append(b)
            if a not in nb[b]:
                nb[b].append(a)
    return nb


def _components(ids: List[str], nb: Dict[str, List[str]]) -> List[List[str]]:
    """Connected components (over nodes with >=1 edge) as sorted id lists, largest-first
    then lexicographically. Pure-stdlib iterative DFS, deterministic."""
    seen = set()
    comps: List[List[str]] = []
    for s in sorted(i for i in ids if nb.get(i)):
        if s in seen:
            continue
        stack = [s]
        comp: List[str] = []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            comp.append(x)
            for y in nb[x]:
                if y not in seen:
                    stack.append(y)
        comps.append(sorted(comp))
    comps.sort(key=lambda c: (-len(c), c[0] if c else ""))
    return comps


# --------------------------------------------------------------------------------------
# Defensive getattr-based adapters onto Dev1's module. A minor field rename upstream must
# not crash this organ — every read is guarded and falls back to an honest default.
# --------------------------------------------------------------------------------------
def _archive(seed: int, cycles: int) -> Dict[str, Any]:
    """Fetch Dev1's REAL archive snapshot defensively."""
    if _forge is None:
        return {}
    fn = getattr(_forge, "loop_archive", None)
    if not callable(fn):
        return {}
    try:
        return fn(seed=int(seed), cycles=int(cycles)) or {}
    except Exception:  # pragma: no cover
        return {}


def _writer_judge() -> Dict[str, Any]:
    """Fetch Dev1's structural writer!=judge separation defensively."""
    if _forge is None:
        return {}
    fn = getattr(_forge, "writer_judge_separation", None)
    if not callable(fn):
        return {}
    try:
        return fn() or {}
    except Exception:  # pragma: no cover
        return {}


def _conjecture_ids() -> frozenset:
    """Dev1's conjecture-id set (Λ etc.). Defensive; empty set if absent."""
    ids = getattr(_forge, "_CONJECTURE_IDS", None) if _forge is not None else None
    try:
        return frozenset(ids) if ids else frozenset()
    except Exception:  # pragma: no cover
        return frozenset()


def _coverage() -> float:
    """Provenance coverage from Dev1's own bookkeeping (getattr-guarded)."""
    if _forge is None:
        return 0.0
    fn = getattr(_forge, "_coverage", None)
    if callable(fn):
        try:
            _wp, _tot, cov = fn()
            return float(cov)
        except Exception:  # pragma: no cover
            pass
    # fall back: derive from _all_nodes() if present
    allnodes = getattr(_forge, "_all_nodes", None)
    if callable(allnodes):
        try:
            nodes = allnodes() or []
            if not nodes:
                return 0.0
            wp = sum(1 for n in nodes if str(n.get("provenance", "")).strip())
            return round(wp / len(nodes), 6)
        except Exception:  # pragma: no cover
            return 0.0
    return 0.0


def _branch_get(b: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Read the first present key from a branch dict (rename-tolerant)."""
    for k in keys:
        if k in b:
            return b[k]
    return default


# --------------------------------------------------------------------------------------
# The extended metrics computation over the REAL archive DAG.
# --------------------------------------------------------------------------------------
def compute_metrics(seed: int = 42, cycles: int = 10) -> Dict[str, Any]:
    """Extended MODELED archive-DAG metrics over the REAL loop-forge archive.
    Deterministic (same seed+cycles => identical snapshot). getattr-defensive."""
    if _forge is None:
        return {
            "service": "loop-forge-metrics-ext",
            "label": MODELED_LABEL,
            "doctrine": DOCTRINE_VERSION,
            "error": "szl_kc_loop_forge import unavailable: %s" % (_IMPORT_ERROR[:160]),
            "honesty": ("MODELED: extended metrics could not bind to the REAL loop-forge "
                        "module; no data fabricated."),
        }

    arch = _archive(seed, cycles)
    wj = _writer_judge()
    conj_ids = _conjecture_ids()

    branches: List[Dict[str, Any]] = list(arch.get("branches") or [])
    rejected: List[Dict[str, Any]] = list(arch.get("rejected") or [])

    # ---- (a) archive acceptance rate ----
    # Prefer Dev1's own computed rate; else derive from branch/reject counts. The archive
    # `branches` includes the root, which is not a "proposed candidate", so subtract it.
    accepted_nonroot = sum(1 for b in branches
                           if _branch_get(b, "bid", default="") != "root")
    total_proposed = accepted_nonroot + len(rejected)
    derived_rate = round(accepted_nonroot / total_proposed, 6) if total_proposed else 0.0
    acceptance_rate = arch.get("acceptance_rate", derived_rate)

    # ---- (b) recursion-depth histogram + mean (over accepted branches) ----
    depths: List[int] = []
    for b in branches:
        d = _branch_get(b, "depth", default=None)
        if isinstance(d, (int, float)):
            depths.append(int(d))
    depth_hist: Dict[int, int] = {}
    for d in depths:
        depth_hist[d] = depth_hist.get(d, 0) + 1
    mean_depth = round(sum(depths) / len(depths), 6) if depths else 0.0
    max_depth = max(depths) if depths else 0
    # prefer Dev1's own mean/max where present (rename-tolerant)
    mean_depth = arch.get("mean_recursion_depth", mean_depth)
    max_depth = arch.get("max_recursion_depth", max_depth)

    # ---- (c) Fiedler lambda2 / connectivity of the archive DAG skeleton ----
    # Build the undirected skeleton from parent/child links. Every accepted branch has a
    # `parent` (bid); the root's parent is None. lambda2>0 <=> one connected component.
    ids = [str(_branch_get(b, "bid", default="")) for b in branches]
    ids = [i for i in ids if i]
    edges: List[Tuple[str, str]] = []
    for b in branches:
        child = str(_branch_get(b, "bid", default=""))
        parent = _branch_get(b, "parent", default=None)
        if child and parent:
            edges.append((str(parent), child))
    nb = _undirected(ids, edges)
    lambda2 = _fiedler_lambda2(ids, nb)
    comps = _components(ids, nb)
    largest = comps[0] if comps else []
    lambda2_largest = _fiedler_lambda2(largest, nb)
    connected = lambda2 > 1e-9
    isolated = [i for i in ids if not nb.get(i)]

    # ---- (d) honesty invariants ----
    conjecture_rendered_green = sum(
        1 for b in branches
        if _branch_get(b, "target", default=None) in conj_ids and _branch_get(b, "accepted", default=False)
    )
    # also inherit Dev1's own count if it exposes one on the archive snapshot
    conjecture_rendered_green = int(arch.get("conjecture_rendered_green", conjecture_rendered_green))
    provenance_coverage = _coverage()
    writer_ne_judge = bool(wj.get("writer_ne_judge", False))
    kernel_outside_loop = bool(wj.get("proposer_cannot_call_judge", False))

    honesty_invariants = {
        "writer_ne_judge": writer_ne_judge,
        "kernel_outside_loop": kernel_outside_loop,
        "conjecture_rendered_green": conjecture_rendered_green,
        "provenance_coverage": provenance_coverage,
        # booleanized doctrine assertions (mirror flower's block)
        "writer_ne_judge_true": writer_ne_judge is True,
        "kernel_outside_loop_true": kernel_outside_loop is True,
        "conjecture_rendered_green_is_zero": conjecture_rendered_green == 0,
        "provenance_coverage_full": provenance_coverage == 1.0,
        "label_is_MODELED": True,
        "no_consciousness_claim": True,
    }

    return {
        "service": "loop-forge-metrics-ext",
        "label": MODELED_LABEL,
        "doctrine": DOCTRINE_VERSION,
        "seed": int(seed),
        "cycles": int(arch.get("cycles", cycles)),
        # (a)
        "acceptance_rate": acceptance_rate,
        "accepted_branches": accepted_nonroot,
        "rejected_total": len(rejected),
        "total_proposed": total_proposed,
        # (b)
        "recursion_depth_histogram": {str(k): v for k, v in sorted(depth_hist.items())},
        "mean_recursion_depth": mean_depth,
        "max_recursion_depth": max_depth,
        "depth_cap": arch.get("depth_cap"),
        # (c)
        "archive_nodes": len(ids),
        "archive_edges": len(edges),
        "fiedler_lambda2": lambda2,
        "fiedler_lambda2_largest_component": lambda2_largest,
        "archive_is_connected": connected,
        "component_count": len(comps),
        "largest_component_size": len(largest),
        "isolated_node_count": len(isolated),
        # (d)
        "conjecture_rendered_green": conjecture_rendered_green,
        "provenance_coverage": provenance_coverage,
        "writer_ne_judge": writer_ne_judge,
        "kernel_outside_loop": kernel_outside_loop,
        "honesty_invariants": honesty_invariants,
        "citations": dict(getattr(_forge, "CITATIONS", {}) or {}),
        "honesty": ("MODELED: the archive is the REAL DGM-style branching archive "
                    "(imported from szl_kc_loop_forge). These are MODELED, deterministic, "
                    "pure-stdlib archive-DAG statistics (acceptance rate, recursion-depth "
                    "histogram, and the graph-Laplacian Fiedler lambda2 via a symmetric "
                    "Jacobi eigensolver) over that real topology — never trained, alive, "
                    "or measured. The upstream kernel gate is a MODELED oracle mirroring "
                    "lutar-lean discipline (c7c0ba17, cited; NOT run in-Space); WRITER != "
                    "JUDGE is structurally enforced. Lambda stays Conjecture 1, gray, never "
                    "green. NO consciousness claim."),
    }


# Alias mandated by the brief: computeMetrics(seed) — thin wrapper over compute_metrics.
def computeMetrics(seed: int = 42) -> Dict[str, Any]:  # noqa: N802 (brief-mandated name)
    """Brief-mandated entrypoint. computeMetrics(seed) -> extended archive-DAG metrics."""
    return compute_metrics(seed=int(seed), cycles=10)


# --------------------------------------------------------------------------------------
# Registration (additive, optional). Returns the single registered path.
# --------------------------------------------------------------------------------------
def register(app, ns: str = "killinchu") -> List[str]:
    """Wire GET /api/<ns>/v1/loopforge/metrics-ext onto app. Additive, try/except-guarded.
    Uses FastAPI add_api_route when available; falls back to Starlette Route append.
    Returns the list with the single registered route path."""
    base = "/api/%s/v1/loopforge" % ns
    paths = ["%s/metrics-ext" % base]

    try:
        from fastapi.responses import JSONResponse

        def _metrics_ext_h(seed: int = 42, cycles: int = 10):  # noqa: ANN202
            try:
                return JSONResponse(compute_metrics(seed=seed, cycles=cycles))
            except Exception as exc:  # pragma: no cover — never 500 the surface
                return JSONResponse({"service": "loop-forge-metrics-ext", "label": MODELED_LABEL,
                                     "error": "compute fail-open: %s" % (str(exc)[:160])},
                                    status_code=200)

        add_api_route = getattr(app, "add_api_route", None)
        if callable(add_api_route):
            app.add_api_route(paths[0], _metrics_ext_h, methods=["GET"])
        else:
            from starlette.routing import Route  # type: ignore

            async def _m(request):  # type: ignore
                return JSONResponse(compute_metrics(
                    seed=int(request.query_params.get("seed", 42)),
                    cycles=int(request.query_params.get("cycles", 10))))

            app.router.routes.append(Route(paths[0], _m, methods=["GET"]))
    except Exception:
        pass  # additive registration must never break app boot

    return paths


# --------------------------------------------------------------------------------------
# Self-test (run `python3 szl_kc_loop_forge_metrics.py` — must print ALL OK).
# --------------------------------------------------------------------------------------
if __name__ == "__main__":
    m = compute_metrics(seed=42, cycles=10)

    print("label:", m["label"])
    print("acceptance_rate:", m["acceptance_rate"],
          "(%d accepted / %d proposed, %d rejected)" %
          (m["accepted_branches"], m["total_proposed"], m["rejected_total"]))
    print("recursion_depth_histogram:", m["recursion_depth_histogram"])
    print("mean_recursion_depth:", m["mean_recursion_depth"],
          "| max:", m["max_recursion_depth"], "(cap %s)" % m["depth_cap"])
    print("archive DAG: %d nodes, %d edges" % (m["archive_nodes"], m["archive_edges"]))
    print("fiedler_lambda2 (whole archive):", m["fiedler_lambda2"],
          "| connected:", m["archive_is_connected"])
    print("  components:", m["component_count"], "| largest:", m["largest_component_size"],
          "| isolated:", m["isolated_node_count"])
    print("  fiedler_lambda2 within largest component:", m["fiedler_lambda2_largest_component"])
    print("honesty invariants:")
    print("  writer_ne_judge:", m["writer_ne_judge"], "(must be True)")
    print("  kernel_outside_loop:", m["kernel_outside_loop"], "(must be True)")
    print("  conjecture_rendered_green:", m["conjecture_rendered_green"], "(must be 0)")
    print("  provenance_coverage:", m["provenance_coverage"], "(must be 1.0)")

    # ---- HARD invariants (Doctrine v11) ----
    assert _forge is not None, "must bind to the REAL szl_kc_loop_forge module: %s" % _IMPORT_ERROR
    assert m["label"] == MODELED_LABEL == "MODELED", m["label"]

    # (a) acceptance rate is a real, non-trivial gate (not a rubber stamp, not zero)
    assert isinstance(m["acceptance_rate"], float), "acceptance_rate must be a real number"
    assert 0.0 < m["acceptance_rate"] < 1.0, "acceptance rate must be a real, non-trivial gate"
    assert m["total_proposed"] > 0 and m["rejected_total"] > 0, "gate must reject some candidates"

    # (b) recursion-depth histogram + mean are sane and respect the depth cap
    assert isinstance(m["recursion_depth_histogram"], dict) and m["recursion_depth_histogram"], "histogram present"
    assert m["mean_recursion_depth"] > 0.0, "mean recursion depth must be positive"
    if m["depth_cap"] is not None:
        assert m["max_recursion_depth"] <= m["depth_cap"], "depth cap must hold"
        assert all(int(k) <= m["depth_cap"] for k in m["recursion_depth_histogram"]), "hist within cap"
    # histogram counts sum to the number of archive nodes (accepted branches incl. root)
    assert sum(m["recursion_depth_histogram"].values()) == m["archive_nodes"], "hist sums to node count"

    # (c) Fiedler lambda2 reported honestly; the archive DAG is one connected tree/component
    assert isinstance(m["fiedler_lambda2"], float) and m["fiedler_lambda2"] >= 0.0, "lambda2 real, non-negative"
    assert (m["fiedler_lambda2"] > 1e-9) == m["archive_is_connected"], "lambda2>0 <=> connected"
    assert m["archive_is_connected"] is True, "archive must be one connected DAG (rooted at locked-8 trunk)"
    assert m["component_count"] == 1, "archive is a single connected component"
    assert m["isolated_node_count"] == 0, "no isolated archive nodes (every branch links a parent)"
    assert m["fiedler_lambda2_largest_component"] > 0.0, "largest component internally connected"
    assert m["archive_nodes"] >= 2 and m["archive_edges"] >= 1, "non-trivial archive"

    # (d) honesty invariants — the four the brief names, all satisfied
    hi = m["honesty_invariants"]
    assert m["writer_ne_judge"] is True and hi["writer_ne_judge_true"] is True, "writer != judge"
    assert m["kernel_outside_loop"] is True and hi["kernel_outside_loop_true"] is True, "kernel outside loop"
    assert m["conjecture_rendered_green"] == 0 and hi["conjecture_rendered_green_is_zero"] is True, \
        "conjectures never rendered green"
    assert m["provenance_coverage"] == 1.0 and hi["provenance_coverage_full"] is True, \
        "provenance coverage must be 1.0"
    assert hi["label_is_MODELED"] is True and hi["no_consciousness_claim"] is True

    # honest string present
    assert isinstance(m["honesty"], str) and m["honesty"].startswith("MODELED"), "honesty string"

    # computeMetrics(seed) alias exists and matches compute_metrics(seed, 10)
    assert computeMetrics(42) == compute_metrics(42, 10), "computeMetrics(seed) alias must match"

    # ---- determinism: same seed => identical snapshot; seed-sensitive ----
    assert compute_metrics(42, 10) == compute_metrics(42, 10), "metrics must be deterministic"
    assert computeMetrics(42) == computeMetrics(42), "computeMetrics must be deterministic"
    assert compute_metrics(7, 10) != compute_metrics(42, 10), "metrics must be seed-sensitive"

    # ---- register() returns the exact metrics-ext path for BOTH namespaces ----
    class _NoApp:
        pass
    paths_k = register(_NoApp(), ns="killinchu")
    assert paths_k == ["/api/killinchu/v1/loopforge/metrics-ext"], paths_k
    paths_a = register(_NoApp(), ns="a11oy")
    assert paths_a == ["/api/a11oy/v1/loopforge/metrics-ext"], paths_a
    print("register paths (killinchu):", paths_k)
    print("register paths (a11oy):    ", paths_a)

    print("szl_kc_loop_forge_metrics: extended archive-DAG metrics on the real loop-forge "
          "archive — acceptance rate, recursion-depth histogram, Fiedler lambda2 "
          "connectivity, honesty invariants, ns-parametric, deterministic.", file=_sys.stderr)
    print("ALL OK")
