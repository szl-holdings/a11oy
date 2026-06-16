#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1 · sovereign=false on this path
"""szl_orbital_topology.py — SZL Orbital Compute Tier: MODELED constellation topology.

ROADMAP / MODELED ONLY. SZL has NO on-orbit hardware. Every node and link returned
by this surface is a MODELED design artifact — there are no live orbital nodes, none
are reachable, and none ever serve a real job. This module exists to describe the
FORWARD architecture (the orbital extension of the existing ground GPU fabric), never
to claim a deployed satellite.

DOCTRINE v11 (this surface is roadmap-architecture, be ruthless about honesty):
  - data_kind is always "MODELED-roadmap". The whole payload carries that label.
  - EVERY node carries modeled:true and reachable:false. There is no code path that
    can set reachable=true here — these are not real endpoints and we never probe
    them (a reachable flag is a REAL-PROBE-ONLY fact, and there is nothing to probe).
  - EVERY link (OISL / ground-space downlink) carries modeled:true.
  - No joules / FLOPs / receipts are minted here. Energy belongs to the projection
    surface (szl_orbital_projection.py), which derives a MODELED orbital figure FROM
    the REAL ground-measured J/token coefficient and labels it MODELED.
  - "no on-orbit hardware" is stated in the payload so the demo is honest at a glance.

The constellation is a deterministic MODELED design (no randomness): a LEO edge shell,
a MEO aggregation ring, and a GEO backhaul tier, joined by inter-satellite optical
links (OISL) and ground-space downlinks to the REAL named ground fabric nodes. The
moat being illustrated is SZL's governed-energy-receipt + signed-bundle provenance
applied to space compute — a forward design, not a deployed system.

Endpoint (existing dual-register pattern — handler functions + FastAPI register()):
  GET /api/a11oy/v1/orbital/topology
    Returns the MODELED constellation: orbital_nodes[], links[], ground_stations[],
    every element labeled modeled:true / reachable:false, data_kind MODELED-roadmap.
"""
from __future__ import annotations

import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Honesty label constants (doctrine v11 vocabulary). The tests grep these exact
# strings. There is NO "MEASURED"/"LIVE"/"reachable:true" path in this module.
# ---------------------------------------------------------------------------
DATA_KIND = "MODELED-roadmap"
ROADMAP = "ROADMAP"
MODELED = "MODELED"
NO_HARDWARE_NOTE = (
    "MODELED orbital roadmap — no on-orbit hardware. SZL operates a real GROUND "
    "GPU fabric today; every orbital node/link below is a MODELED design artifact, "
    "not reachable and never serving a real job."
)

# Real ground fabric nodes the MODELED downlinks reference (these names ARE real
# ground exporters in the energy operator config; the downlink itself is MODELED).
_GROUND_STATIONS = (
    {"id": "gs-betterwithage", "ground_node": "betterwithage",
     "role": "primary ground-space downlink (MODELED) to real ground GPU fabric"},
    {"id": "gs-chaski", "ground_node": "chaski",
     "role": "secondary ground-space downlink (MODELED) to real ground GPU fabric"},
)

# MODELED constellation shape. Deterministic counts — a forward design, not a probe.
_LEO_EDGE_COUNT = 6      # LEO edge-compute shell (per-node rad-hard inference)
_MEO_AGG_COUNT = 3       # MEO aggregation ring
_GEO_BACKHAUL_COUNT = 2  # GEO backhaul / persistent backhaul tier


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _node(node_id: str, tier: str, plane: int, role: str) -> dict:
    """A single MODELED orbital node. ALWAYS modeled:true / reachable:false.

    There is intentionally no parameter that can flip reachable to true: a
    reachable flag is a REAL-PROBE-ONLY fact and these nodes do not exist to probe.
    """
    return {
        "id": node_id,
        "tier": tier,            # "LEO-edge" | "MEO-aggregation" | "GEO-backhaul"
        "orbital_plane": plane,
        "role": role,
        "modeled": True,
        "reachable": False,      # never live — no on-orbit hardware
        "data_kind": DATA_KIND,
        "note": "MODELED node — no on-orbit hardware; not reachable, never serves a real job",
    }


def _link(link_id: str, src: str, dst: str, kind: str) -> dict:
    """A MODELED link (OISL between sats, or ground-space downlink). modeled:true."""
    return {
        "id": link_id,
        "src": src,
        "dst": dst,
        "kind": kind,            # "OISL" | "ground-space-downlink"
        "modeled": True,
        "data_kind": DATA_KIND,
        "note": "MODELED link — design artifact, not a measured RF/optical path",
    }


def build_topology() -> dict:
    """Build the MODELED constellation topology. No randomness, no live probe."""
    nodes: list[dict] = []
    links: list[dict] = []

    # --- LEO edge shell: per-node rad-hard inference (MODELED) ---
    leo_ids = []
    for i in range(_LEO_EDGE_COUNT):
        nid = f"leo-edge-{i:02d}"
        leo_ids.append(nid)
        nodes.append(_node(nid, "LEO-edge", plane=i % 3,
                           role="MODELED LEO edge-compute node (rad-hard inference, roadmap)"))

    # --- MEO aggregation ring (MODELED) ---
    meo_ids = []
    for i in range(_MEO_AGG_COUNT):
        nid = f"meo-agg-{i:02d}"
        meo_ids.append(nid)
        nodes.append(_node(nid, "MEO-aggregation", plane=i,
                           role="MODELED MEO aggregation node (governed-receipt aggregation, roadmap)"))

    # --- GEO backhaul tier (MODELED) ---
    geo_ids = []
    for i in range(_GEO_BACKHAUL_COUNT):
        nid = f"geo-backhaul-{i:02d}"
        geo_ids.append(nid)
        nodes.append(_node(nid, "GEO-backhaul", plane=i,
                           role="MODELED GEO backhaul node (persistent downlink, roadmap)"))

    # --- OISL links: ring within LEO shell, LEO→MEO uplinks, MEO→GEO uplinks ---
    for i, nid in enumerate(leo_ids):
        nxt = leo_ids[(i + 1) % len(leo_ids)]
        links.append(_link(f"oisl-leo-{i:02d}", nid, nxt, "OISL"))
        # each LEO edge node feeds a MEO aggregator (MODELED)
        links.append(_link(f"oisl-leo-meo-{i:02d}", nid, meo_ids[i % len(meo_ids)], "OISL"))
    for i, nid in enumerate(meo_ids):
        links.append(_link(f"oisl-meo-geo-{i:02d}", nid, geo_ids[i % len(geo_ids)], "OISL"))

    # --- ground-space downlinks: GEO backhaul → real ground fabric (MODELED path) ---
    for i, gs in enumerate(_GROUND_STATIONS):
        links.append(_link(f"downlink-{gs['id']}", geo_ids[i % len(geo_ids)], gs["id"],
                           "ground-space-downlink"))

    reachable_count = sum(1 for n in nodes if n["reachable"])

    return {
        "ok": True,
        "endpoint": "orbital/topology",
        "data_kind": DATA_KIND,
        "status": ROADMAP,
        "on_orbit_hardware": False,
        "label": MODELED,
        "doctrine": (
            "v11: MODELED orbital ROADMAP. No on-orbit hardware. Every node is "
            "modeled:true / reachable:false and every link is modeled:true — there is "
            "no code path that fabricates a live/reachable orbital node. The real asset "
            "today is the GROUND GPU fabric; this is its forward orbital extension. "
            "Λ = Conjecture 1; sovereign=false."
        ),
        "summary": {
            "leo_edge_nodes": _LEO_EDGE_COUNT,
            "meo_aggregation_nodes": _MEO_AGG_COUNT,
            "geo_backhaul_nodes": _GEO_BACKHAUL_COUNT,
            "total_nodes": len(nodes),
            "total_links": len(links),
            "ground_stations": len(_GROUND_STATIONS),
            "reachable_nodes": reachable_count,   # MUST be 0 — no live orbital hardware
        },
        "orbital_nodes": nodes,
        "links": links,
        "ground_stations": [
            {**gs, "modeled": True, "data_kind": DATA_KIND,
             "note": "ground side is a REAL fabric node; the space downlink to it is MODELED"}
            for gs in _GROUND_STATIONS
        ],
        "honesty": {
            "sovereign": False,
            "lambda": "Conjecture 1",
            "on_orbit_hardware": False,
            "all_nodes_modeled": True,
            "all_nodes_reachable_false": True,
            "note": NO_HARDWARE_NOTE,
        },
        "timestamp_utc": _now_iso(),
    }


def handle_topology() -> dict:
    """GET /orbital/topology — handler used by FastAPI and __main__."""
    try:
        return build_topology()
    except Exception as exc:  # never 500: honest degraded response
        return {
            "ok": False,
            "endpoint": "orbital/topology",
            "data_kind": DATA_KIND,
            "error": str(exc),
            "doctrine": "v11: topology unavailable; no fabricated orbital node emitted.",
            "timestamp_utc": _now_iso(),
        }


# ---------------------------------------------------------------------------
# FastAPI router registration — mirrors szl_energy_projection.register() exactly.
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    """Mount the orbital topology endpoint on the FastAPI ``app``. Returns a status string."""
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/orbital"

    @app.get(f"{base}/topology")
    async def _orbital_topology():
        """MODELED orbital constellation (ROADMAP) — no on-orbit hardware; nothing reachable."""
        return JSONResponse(handle_topology())

    return "orbital-topology-wired:1"


# ---------------------------------------------------------------------------
# Self-test — verifies labels, no-reachable invariant, link integrity.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json
    import sys as _sys

    print("=" * 72)
    print("szl_orbital_topology — self-test (MODELED labels, no reachable node)")
    print("=" * 72)

    topo = build_topology()

    # 1) data_kind + roadmap labels present
    assert topo["data_kind"] == DATA_KIND, topo["data_kind"]
    assert topo["on_orbit_hardware"] is False
    assert topo["status"] == ROADMAP
    print(f"[1] data_kind={topo['data_kind']} status={topo['status']} on_orbit_hardware=False  OK")

    # 2) EVERY node modeled:true / reachable:false — no fabricated live node
    assert topo["orbital_nodes"], "no nodes built"
    for n in topo["orbital_nodes"]:
        assert n["modeled"] is True, n
        assert n["reachable"] is False, f"DOCTRINE VIOLATION: reachable orbital node {n['id']}"
    assert topo["summary"]["reachable_nodes"] == 0, "reachable_nodes must be 0"
    print(f"[2] {len(topo['orbital_nodes'])} nodes, all modeled:true reachable:false  OK")

    # 3) EVERY link modeled:true and points at existing nodes/ground stations
    node_ids = {n["id"] for n in topo["orbital_nodes"]}
    gs_ids = {g["id"] for g in topo["ground_stations"]}
    valid = node_ids | gs_ids
    for l in topo["links"]:
        assert l["modeled"] is True, l
        assert l["src"] in valid, f"dangling link src {l['src']}"
        assert l["dst"] in valid, f"dangling link dst {l['dst']}"
    print(f"[3] {len(topo['links'])} links, all modeled:true, no dangling endpoints  OK")

    # 4) the honest no-hardware note is present and says "no on-orbit hardware"
    blob = _json.dumps(topo)
    assert "no on-orbit hardware" in blob, "honest no-hardware note missing"
    # 5) NOTHING in this payload may claim a MEASURED orbital reading or live node
    assert "MEASURED" not in blob, "DOCTRINE VIOLATION: 'MEASURED' in MODELED topology payload"
    assert '"reachable": true' not in blob.lower().replace(" ", "")  # belt-and-suspenders
    print("[4] 'no on-orbit hardware' stated  [5] no 'MEASURED'/reachable-true in payload  OK")

    print("\n--- example topology summary ---")
    print(_json.dumps(topo["summary"], indent=2))
    print("\nok:true checks:5")
    _sys.exit(0)
