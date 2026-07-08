#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar <stephenlutar2@gmail.com>
"""szl_flowbrain.py — a CONTINUOUS-FLOW lens on the governed brain.

GET /api/a11oy/v1/frontier/flowbrain             — status/info (STRUCTURAL-ONLY).
GET /api/a11oy/v1/frontier/flowbrain/trajectory  — a continuous belief-flow trajectory
                                                   x_t ∈ [0,1] for a brain node (or a demo
                                                   trajectory over the real brain graph),
                                                   with the threshold-crossing points.

SOURCE IDEA (borrowed, NOT ours):
  Hwang, Zhang, Dai, Kontras, Vanmarcke, De Vos, Fiete, Liang — "B[FM]²: Brain Foundation
  Model via Flow Matching with SplitUNet." MIT + KU Leuven. arXiv:2606.20812v1, 18 Jun 2026.
  https://arxiv.org/abs/2606.20812

  We take exactly TWO *principles* from that EEG foundation-model paper and re-fashion them
  for OUR governed brain graph — honest-labeled, nothing reproduced:

  (1) CONTINUOUS OVER DISCRETE. B[FM]² argues that forcing a continuous process into discrete
      tokens fragments its dynamics, and learns a continuous-time flow instead. We apply the
      *principle* only: the estate's belief tiers (CONJECTURE → CORROBORATED → LOAD-BEARING)
      are discrete jumps today; we REFRAME belief as a CONTINUOUS confidence flow x_t ∈ [0,1]
      where the named tiers are THRESHOLDS CROSSED, not states occupied. A node's belief over
      successive anatomy-loop pulses is a trajectory (a path), not a step function.

  (2) AXIS FACTORIZATION (SplitUNet). B[FM]²'s velocity network factorizes each block into a
      1D temporal conv then a 1D electrode conv, downsampling ONLY the long autocorrelated
      time axis and preserving the short structured spatial axis. We apply the *shape* to OUR
      telemetry: a factorized "1D-time ⊗ 1D-node" view — a long autocorrelated telemetry/time
      axis × a short node-topology axis (omen / betterwithage). MEASURED only where a real
      reading exists THIS request; STRUCTURAL-ONLY otherwise.

HONESTY — read this before believing anything below:
  * We do NOT do EEG or BCI. We claim NO EEG capability, NO benchmark, NO trained
    brain-foundation-model, and we have NOT reproduced any B[FM]² result. We borrow the
    continuous-flow-over-discretization *principle*, nothing else.
  * TOP-LEVEL LABEL: STRUCTURAL-ONLY. The synthesis (that belief evolution is usefully modeled
    as a continuous flow crossing tier thresholds) is CONJECTURE — explicitly NOT a theorem,
    never green, never 1.0.
  * The trajectory is a DETERMINISTIC, client-recomputable STRUCTURAL reframe derived from a
    real brain-graph node's OWN attributes (degree / layer / honest label). It is NOT a
    measurement of belief; no anatomy pulse was sampled this request, so it is STRUCTURAL-ONLY,
    never MEASURED. Node facts are pulled from the graph the estate already builds
    (a11oy_brain_graph.build_brain_graph) — no node is fabricated; if that module is
    unavailable the endpoint degrades to an honest, explicitly-labeled STRUCTURAL demo graph.
  * Λ stays Conjecture 1 (advisory, gray, trust ceiling ≤ 0.97, never a theorem, never green).
    Khipu BFT stays Conjecture 2. Adds NOTHING to the locked-8.
  * RECEIPT: these are READ paths, so nothing is signed (receipt-on-write, not on-read). We
    emit a SHA-256 CONTENT digest of the deterministic trajectory — a content-addressable,
    UNSIGNED anchor a client can recompute, NOT a signed write-receipt. A signed Khipu receipt
    is minted only on a state change, of which this pure read has none.
"""
import datetime
import hashlib
import json
from typing import Any

# Honesty-label vocabulary (doctrine v11) — tests grep these exact strings.
STRUCTURAL = "STRUCTURAL-ONLY"
CONJECTURE = "CONJECTURE"
MEASURED = "MEASURED"
MODELED = "MODELED"

# Trust ceiling — advisory, never 100% (doctrine v11).
TRUST_CEILING = 0.97

# Continuous belief flow x_t ∈ [0,1]; the named tiers are THRESHOLDS CROSSED, not states.
# (Advisory reframe only — the numbers are structural, not measured confidences.)
TIER_THRESHOLDS = [
    {"tier": "CONJECTURE", "x": 0.0,
     "note": "baseline — a belief enters as a conjecture; advisory, gray, never a theorem"},
    {"tier": "CORROBORATED", "x": 0.50,
     "note": "crossing this threshold means corroborating pulses have accumulated"},
    {"tier": "LOAD-BEARING", "x": 0.85,
     "note": "crossing this threshold means the estate leans on the belief; ceiling ≤ 0.97"},
]

# The single source idea, cited verbatim (id only on-surface — 0 runtime CDN).
SOURCE = {
    "id": "arXiv:2606.20812",
    "title": ("B[FM]²: Brain Foundation Model via Flow Matching with SplitUNet"),
    "authors": ("Hwang, Zhang, Dai, Kontras, Vanmarcke, De Vos, Fiete, Liang"),
    "venue": "MIT + KU Leuven, arXiv:2606.20812v1, 18 Jun 2026",
    "url": "https://arxiv.org/abs/2606.20812",
    "borrowed": ("the continuous-flow-over-discretization principle + the SplitUNet "
                 "axis-factorization shape — NOT any EEG capability, benchmark, or result"),
    "we_do_not": ("do EEG/BCI, claim an EEG benchmark, or reproduce any B[FM]² result"),
}

# Number of anatomy-loop pulses the demo trajectory spans (the long, autocorrelated axis).
_PULSES = 24


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Brain-graph access — pull REAL nodes; never fabricate a node fact.
# ---------------------------------------------------------------------------

def _load_graph(ns: str = "a11oy") -> tuple[list, str]:
    """Return (nodes, source_label). Prefer the real graph the estate already builds; if the
    module is unavailable, return an honest STRUCTURAL demo graph clearly labeled as such."""
    try:
        import a11oy_brain_graph as _bg  # lazy — keeps this optional/additive
        g = _bg.build_brain_graph(ns=ns)
        nodes = g.get("nodes") or []
        if nodes:
            return nodes, "brain-graph"
    except Exception:
        pass
    # Honest fallback — a tiny STRUCTURAL demo graph (NOT harvested, explicitly labeled).
    demo = [
        {"id": "demo:estate", "title": "estate root (demo)", "kind": "estate",
         "layer": 3, "degree": 6, "label": STRUCTURAL},
        {"id": "demo:topic", "title": "topic cluster (demo)", "kind": "topic",
         "layer": 1, "degree": 3, "label": STRUCTURAL},
        {"id": "demo:surface", "title": "surface node (demo)", "kind": "surface",
         "layer": 0, "degree": 1, "label": STRUCTURAL},
    ]
    return demo, "structural-demo"


def _pick_node(nodes: list, node_id: str | None) -> tuple[dict, bool]:
    """Return (node, found). If node_id is given and present, return it; else pick a stable
    representative (highest degree, ties broken by id) and report found=False for an
    explicitly-requested-but-absent id so the caller can note it honestly."""
    if node_id:
        for n in nodes:
            if str(n.get("id")) == node_id:
                return n, True
    # representative = highest-degree node (deterministic tie-break on id)
    rep = max(nodes, key=lambda n: (int(n.get("degree", 0) or 0), str(n.get("id", ""))))
    return rep, (node_id is None)


# ---------------------------------------------------------------------------
# The continuous belief-flow trajectory (STRUCTURAL-ONLY reframe).
# ---------------------------------------------------------------------------

def _flow_trajectory(node: dict) -> dict[str, Any]:
    """A deterministic, client-recomputable belief-flow x_t ∈ [0,1] over _PULSES anatomy
    pulses, derived ONLY from the node's real attributes (normalized degree → asymptote,
    layer → onset). This is a STRUCTURAL reframe of the discrete tiers as a continuous path,
    NOT a measured confidence — no pulse was sampled this request."""
    degree = int(node.get("degree", 0) or 0)
    layer = int(node.get("layer", 0) or 0)
    # asymptote (ceiling of the flow) grows with connectivity but is capped at the Trust
    # ceiling — a well-connected node can approach, never reach, certainty.
    asymptote = min(TRUST_CEILING, 0.35 + 0.08 * degree)
    # a deeper (more downstream / output) layer starts a touch higher (more corroboration
    # has flowed into it); a growth rate that saturates over the pulse window.
    onset = min(0.25, 0.05 * layer)
    rate = 0.18

    xs = []
    for t in range(_PULSES + 1):
        # logistic-shaped monotone flow from `onset` up toward `asymptote`.
        s = 1.0 / (1.0 + pow(2.718281828, -rate * (t - _PULSES / 3.0)))
        x = onset + (asymptote - onset) * s
        xs.append(round(min(asymptote, max(0.0, x)), 4))

    # threshold-crossing points: the first pulse index at which the flow crosses each tier.
    crossings = []
    for tier in TIER_THRESHOLDS:
        thr = tier["x"]
        crossed_at = None
        for t, x in enumerate(xs):
            if x >= thr:
                crossed_at = t
                break
        crossings.append({
            "tier": tier["tier"],
            "threshold": thr,
            "crossed_at_pulse": crossed_at,       # None if the flow never reaches this tier
            "reached": crossed_at is not None,
            "note": tier["note"],
        })

    return {
        "label": STRUCTURAL,
        "pulses": _PULSES,
        "x_t": xs,                                # the continuous trajectory (the path)
        "asymptote": round(asymptote, 4),
        "trust_ceiling": TRUST_CEILING,
        "tier_thresholds": TIER_THRESHOLDS,
        "threshold_crossings": crossings,
        "derived_from": {
            "node_degree": degree,
            "node_layer": layer,
            "formula": ("x_t = onset + (asymptote-onset)·σ(rate·(t - N/3)); "
                        "asymptote = min(0.97, 0.35 + 0.08·degree); onset = min(0.25, 0.05·layer)"),
        },
        "honest_note": ("a STRUCTURAL reframe of the discrete belief tiers as a continuous "
                        "path over anatomy pulses — deterministic from the node's own graph "
                        "attributes. NOT a measured confidence; no pulse was sampled this "
                        "request. Tiers are thresholds crossed, not states occupied."),
    }


def _axis_factorization(node: dict, n_nodes: int) -> dict[str, Any]:
    """The SplitUNet-inspired factorized "1D-time ⊗ 1D-node" view applied to OUR data.
    STRUCTURAL-ONLY: no real meter reading is taken here, so nothing is MEASURED."""
    return {
        "label": STRUCTURAL,
        "borrowed_from": SOURCE["id"],
        "time_axis": {
            "role": "long, autocorrelated telemetry/time axis (the anatomy-pulse sequence)",
            "length": _PULSES,
            "downsampled": True,
            "note": "SplitUNet downsamples ONLY the long time axis — mirrored here structurally",
        },
        "node_axis": {
            "role": "short, structured node-topology axis (omen / betterwithage neighborhood)",
            "length": max(1, int(node.get("degree", 0) or 0)),
            "graph_nodes_available": n_nodes,
            "downsampled": False,
            "note": "node topology is preserved at every layer (never downsampled)",
        },
        "measured_where": ("MEASURED only where a real meter reading exists THIS request; none "
                           "is taken on this read path, so this factorized view is "
                           "STRUCTURAL-ONLY"),
        "honest_note": ("we borrow the axis-factorization SHAPE (factor a long autocorrelated "
                        "axis from a short structured one). We do NOT run a SplitUNet, and we "
                        "claim no EEG electrode topology — the 'node axis' is OUR graph "
                        "topology."),
    }


def _content_receipt(trajectory: dict) -> dict[str, Any]:
    """A SHA-256 CONTENT digest of the deterministic trajectory. Content-addressable and
    client-recomputable; UNSIGNED (GETs never sign — receipt-on-write, not on-read)."""
    canonical = json.dumps(trajectory, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "algo": "sha256",
        "digest": _sha256_hex(canonical),
        "signed": False,
        "kind": "content-digest",
        "note": ("content-addressable digest of the deterministic trajectory (a client can "
                 "recompute it). NOT a signed write-receipt — this is a read path and mints "
                 "no Khipu envelope; a signed receipt belongs only on a state change."),
    }


def _doctrine() -> dict[str, Any]:
    return {
        "label_top": STRUCTURAL,
        "synthesis_label": CONJECTURE,
        "not_verified": True,
        "locked_proven": 8,
        "locked_set": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
        "kernel_commit": "c7c0ba17",
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "runtime_cdn": 0,
        "eeg_capability": False,
        "note": ("borrows the continuous-flow-over-discretization principle from "
                 "arXiv:2606.20812; claims NO EEG capability/benchmark and reproduces no "
                 "result. Additive STRUCTURAL-ONLY surface; touches no locked formula/kernel; "
                 "the synthesis is CONJECTURE — no theorem, no green/1.0, no proof of Λ/BFT."),
    }


# ---------------------------------------------------------------------------
# Payload assembly
# ---------------------------------------------------------------------------

def build_info(ns: str = "a11oy") -> dict[str, Any]:
    """Status/info for the flowbrain surface. Pure read; signs nothing."""
    nodes, source_label = _load_graph(ns)
    return {
        "ok": True,
        "endpoint": "frontier/flowbrain",
        "service": "a11oy.frontier.flowbrain",
        "title": "FlowBrain · Continuous Belief-Flow Lens on the Governed Brain",
        "label": STRUCTURAL,
        "claim": CONJECTURE,
        "not_verified": True,
        "what": ("a continuous-flow lens on the governed brain: belief-tier evolution "
                 "(CONJECTURE → CORROBORATED → LOAD-BEARING) reframed as a CONTINUOUS "
                 "confidence flow x_t ∈ [0,1] where the named tiers are thresholds crossed, "
                 "not states occupied. Borrows the continuous-flow-over-discretization "
                 "principle from B[FM]² (arXiv:2606.20812); we do NOT do EEG and claim NO EEG "
                 "capability or benchmark."),
        "graph_source": source_label,
        "graph_nodes_available": len(nodes),
        "tier_thresholds": TIER_THRESHOLDS,
        "axis_factorization": _axis_factorization(_pick_node(nodes, None)[0], len(nodes)),
        "trajectory_endpoint": f"/api/{ns}/v1/frontier/flowbrain/trajectory",
        "source": SOURCE,
        "doctrine": _doctrine(),
        "labels_legend": {
            STRUCTURAL: "definitional/structural reframe only — no measurement taken",
            CONJECTURE: "the SZL synthesis — a design thesis, explicitly NOT a theorem",
            MEASURED: "would require a real reading this request — none taken on this read path",
        },
        "timestamp_utc": _now_iso(),
    }


def build_trajectory(ns: str = "a11oy", node_id: str | None = None) -> dict[str, Any]:
    """A continuous belief-flow trajectory for `node_id` (or a demo over the real graph).
    Pure read; emits a SHA-256 CONTENT digest (unsigned) of the deterministic trajectory."""
    nodes, source_label = _load_graph(ns)
    node, found = _pick_node(nodes, node_id)
    traj = _flow_trajectory(node)
    receipt = _content_receipt(traj)

    requested_note = None
    if node_id and not found:
        requested_note = (f"requested node id {node_id!r} not present in the graph — showing a "
                          f"representative node instead (honest fallback, not fabricated)")

    return {
        "ok": True,
        "endpoint": "frontier/flowbrain/trajectory",
        "service": "a11oy.frontier.flowbrain",
        "title": "FlowBrain · Continuous Belief-Flow Trajectory",
        "label": STRUCTURAL,
        "claim": CONJECTURE,
        "not_verified": True,
        "graph_source": source_label,
        "node": {
            "id": node.get("id"),
            "title": node.get("title"),
            "kind": node.get("kind"),
            "layer": node.get("layer"),
            "degree": node.get("degree"),
            # the node's OWN verbatim honest label from the graph (never upgraded here).
            "node_label": node.get("label"),
        },
        "requested_node_found": (found if node_id else None),
        "requested_note": requested_note,
        "trajectory": traj,
        "axis_factorization": _axis_factorization(node, len(nodes)),
        "receipt": receipt,
        "source": SOURCE,
        "doctrine": _doctrine(),
        "timestamp_utc": _now_iso(),
    }


def handle_info(ns: str = "a11oy") -> dict[str, Any]:
    try:
        return build_info(ns)
    except Exception as exc:  # never 500 — honest degraded response
        return {
            "ok": False, "endpoint": "frontier/flowbrain", "label": STRUCTURAL,
            "error": str(exc),
            "doctrine": "v11: surface unavailable; no fabricated trajectory/node emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_trajectory(ns: str = "a11oy", node_id: str | None = None) -> dict[str, Any]:
    try:
        return build_trajectory(ns, node_id)
    except Exception as exc:  # never 500 — honest degraded response
        return {
            "ok": False, "endpoint": "frontier/flowbrain/trajectory", "label": STRUCTURAL,
            "error": str(exc),
            "doctrine": "v11: surface unavailable; no fabricated trajectory/node emitted.",
            "timestamp_utc": _now_iso(),
        }


# ---------------------------------------------------------------------------
# FastAPI router registration — mirrors szl_frontier_fmverif.register() (FastAPI 0.137.1).
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    """Mount the flowbrain surface endpoints. ADDITIVE; register BEFORE the SPA catch-all."""
    from fastapi import Query
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/frontier"

    @app.get(f"{base}/flowbrain")
    async def _frontier_flowbrain():
        """FlowBrain status/info: the continuous-flow lens (STRUCTURAL-ONLY / CONJECTURE)."""
        return JSONResponse(handle_info(ns))

    @app.get(f"{base}/flowbrain/trajectory")
    async def _frontier_flowbrain_trajectory(node: str | None = Query(default=None)):
        """A continuous belief-flow trajectory for a node (or a demo over the real graph)."""
        return JSONResponse(handle_trajectory(ns, node))

    return "frontier-flowbrain-wired:2"


# ---------------------------------------------------------------------------
# Self-test — honest labels, no upgrade, deterministic, source cited.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_flowbrain — self-test (STRUCTURAL-ONLY surface, CONJECTURE synthesis)")
    print("=" * 72)

    info = build_info()
    traj = build_trajectory()
    blob = json.dumps({"info": info, "traj": traj})

    # 1) top-level STRUCTURAL-ONLY, synthesis CONJECTURE, explicitly NOT VERIFIED.
    assert info["label"] == STRUCTURAL and info["claim"] == CONJECTURE
    assert traj["label"] == STRUCTURAL and traj["claim"] == CONJECTURE
    assert info["not_verified"] is True and traj["not_verified"] is True
    print("[1] top-level STRUCTURAL-ONLY / synthesis CONJECTURE / not_verified  OK")

    # 2) doctrine: locked-8 exact, adds nothing, Λ/BFT conjectures, trust 0.97 (not 100%),
    #    no EEG capability claimed.
    d = info["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0 and d["eeg_capability"] is False
    print("[2] doctrine: locked-8 exact, +0, Λ/BFT conjectures, trust 0.97, NO EEG  OK")

    # 3) source cited: arXiv:2606.20812 + explicit no-EEG note present.
    assert SOURCE["id"] == "arXiv:2606.20812" and SOURCE["url"] in blob
    assert "EEG" in blob and "arXiv:2606.20812" in blob
    print("[3] B[FM]² source cited (arXiv:2606.20812) + explicit no-EEG note  OK")

    # 4) trajectory is continuous, bounded [0,1], monotone non-decreasing, ceiling <= 0.97.
    xs = traj["trajectory"]["x_t"]
    assert xs and all(0.0 <= x <= 1.0 for x in xs)
    assert all(xs[i] <= xs[i + 1] + 1e-9 for i in range(len(xs) - 1)), "flow not monotone"
    assert max(xs) <= TRUST_CEILING + 1e-9, "flow exceeds the Trust ceiling"
    print(f"[4] trajectory: {len(xs)} pulses, bounded [0,1], monotone, ceiling<=0.97  OK")

    # 5) threshold crossings are tiers-as-thresholds (not states); receipt is unsigned digest.
    cr = traj["trajectory"]["threshold_crossings"]
    assert [c["tier"] for c in cr] == ["CONJECTURE", "CORROBORATED", "LOAD-BEARING"]
    rc = traj["receipt"]
    assert rc["algo"] == "sha256" and rc["signed"] is False and len(rc["digest"]) == 64
    # digest is client-recomputable:
    recompute = _sha256_hex(json.dumps(traj["trajectory"], sort_keys=True,
                                       separators=(",", ":")).encode("utf-8"))
    assert recompute == rc["digest"], "content digest not client-recomputable"
    print("[5] tiers-as-thresholds; unsigned content digest, client-recomputable  OK")

    # 6) Λ is advisory and NEVER a 'green' value; STRUCTURAL never upgraded to VERIFIED.
    def _lambda_vals(o, out):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(k, str) and "lambda" in k.lower() and isinstance(v, str):
                    out.append(v)
                _lambda_vals(v, out)
        elif isinstance(o, list):
            for x in o:
                _lambda_vals(x, out)
        return out
    lam = _lambda_vals(info, []) + _lambda_vals(traj, [])
    assert lam and all(v.strip().lower() != "green" for v in lam), lam
    assert "VERIFIED" not in {info["label"], traj["label"]}
    print("[6] Λ advisory (never 'green'); STRUCTURAL-ONLY never upgraded  OK")

    print("\nok:true checks:6")
    _sys.exit(0)
