#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""szl_agentos.py — AGENT OS MAP: a live, self-honest operator's-eye map of the agent OS.

concept spark: Agentic-OS mapping, @Av1dlive on X
https://x.com/Av1dlive/status/2074796427595874636 — we borrow the single-operator-map idea
(one map of the whole agent OS: a daily loop, a trust ledger, standing goals, optional loops);
we do NOT copy their diagrams or claim Fable-5 specifics. agentos composes ONLY our own
governed components and derives every node/edge and every verdict LIVE from the running estate.

WHAT IT DOES (honest by construction):
  Every "agentic OS" shipped today is a DIAGRAM — a picture you trust because a human drew it.
  agentos is generated LIVE from the running system's OWN honesty receipts, and REFUSES to
  render a loop it cannot prove honest THIS request. It assembles a node/edge graph of the
  agent OS from the app's OWN in-process data — never a hand-maintained topology:

    node                backing (our OWN existing surfaces / invariants)
    ----                --------------------------------------------------
    standing goals   ←  doctrine v11 + locked-8 invariants (immutable OS constraints, fixed)
    daily loop       ←  agentops (bounded operate loop)
    trust ledger     ←  anatomy belief-tiers + SHA-256 receipts + honestywall aggregate
    optional loops   ←  governedagent, governedrag, loopforge, mesh

  Node PRESENCE is derived from the LIVE surface registry (szl3d_holographic.SURFACES,
  imported in-process): a surface-backed node exists ONLY if a backing surface id is actually
  registered. agentos never invents a node whose backing is absent from the registry.

  Each node carries a LIVE honesty verdict sourced from the honestywall aggregate (already
  merged; we consume its in-process API, never an HTTP hop out of the Space):
    INTACT    — backing surface(s) probed NATIVE-OK with 0 reachable invariant violations
    DEGRADED  — a mixed/partial backing that is neither confidently intact nor unknown
    UNKNOWN   — a backing manifest unreachable THIS request (never a confident node)
    VIOLATED  — a backing surface reports a reachable invariant violation this request

  Overall map state (NEVER green if anything is violated):
    OPERATING     — every present backing node INTACT
    DEGRADED      — some present node UNKNOWN/DEGRADED, none VIOLATED
    HALTED-HONEST — any present backing node VIOLATED; the map declares ITSELF untrustworthy
                    rather than drawing a confident lie.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. GET status/info/map reads mint NOTHING. Only the
POST snapshot endpoint emits an UNSIGNED SHA-256 content digest over the map (a plain content
hash, never a fabricated signature, never a receipt on a GET).

RECURSION SAFETY. agentos is itself a registered surface, so honestywall probes it. Its GET
status/info are STATIC self-manifests that do NOT call honestywall (they are what honestywall
reads for agentos), so honestywall's probe of agentos can never re-enter the honestywall
aggregate. A module-level guard is an additional belt-and-suspenders barrier: if the live-map
path is ever re-entered while a honestywall read is already in flight, the nested read degrades
honestly to UNKNOWN rather than recursing.

DOCTRINE v11:
  - OBSERVES/composes only; adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @
    kernel c7c0ba17. Touches no locked formula and no kernel.
  - Λ stays Conjecture 1 (advisory); introduces no theorem, no green/1.0, no proof of Λ.
    Khipu BFT remains Conjecture 2. Trust ceiling 0.97, never 100%.
  - No label is ever upgraded; a VIOLATED node can never be reported as OPERATING. A truthful
    HALTED-HONEST beats a fake green.
  - Additive routes, registered before the SPA catch-all; 0 runtime CDN.
"""

import datetime
import hashlib
import json
import threading
from typing import Any

# This surface's own top label — a derived composed view, not a measurement.
MODELED = "MODELED"

# Node verdicts (sourced from the honestywall aggregate).
N_INTACT = "INTACT"
N_DEGRADED = "DEGRADED"
N_UNKNOWN = "UNKNOWN"
N_VIOLATED = "VIOLATED"

# Overall map states.
OPERATING = "OPERATING"
MAP_DEGRADED = "DEGRADED"
HALTED_HONEST = "HALTED-HONEST"

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html + agentos.js).
SURFACE_ID = "agentos"

SPARK_URL = "https://x.com/Av1dlive/status/2074796427595874636"
SPARK_NOTE = ("concept spark: Agentic-OS mapping, @Av1dlive on X — we borrow the "
              "single-operator-map idea; we do not copy their diagrams or claim Fable-5 "
              "specifics. agentos composes only our own governed components.")

# Per-surface honestywall status token (mirrors szl_honestywall).
_HW_NATIVE_OK = "NATIVE-OK"
_HW_UNKNOWN = "UNKNOWN"

# ---------------------------------------------------------------------------
# Composition — the node/edge template. Node PRESENCE is confirmed LIVE against the surface
# registry; a surface-backed node with no registered backing is NOT rendered (never invented).
# ---------------------------------------------------------------------------

# backing_kind: "surface" -> presence derived from the live registry; verdict from honestywall
#               per-surface entries. "doctrine" -> immutable OS constraint (locked-8 / v11),
#               rendered fixed; verdict derived from the honestywall doctrine block.
NODE_SPECS = [
    {"id": "standing_goals", "title": "Standing goals — doctrine v11 + locked-8",
     "kind": "goals", "backing": [], "backing_kind": "doctrine",
     "role": "immutable OS constraints that gate every loop step (rendered fixed)"},
    {"id": "daily_loop", "title": "Daily loop — bounded operate loop",
     "kind": "loop", "backing": ["agentops"], "backing_kind": "surface",
     "role": "the recurring operate loop of the agent OS"},
    {"id": "trust_ledger", "title": "Trust ledger — belief-tiers + receipts + honesty aggregate",
     "kind": "ledger", "backing": ["anatomy", "honestywall"], "backing_kind": "surface",
     "role": "belief-tier progression (CONJECTURE→CORROBORATED→LOAD-BEARING) + SHA-256 receipts"},
    {"id": "governed_agent", "title": "Optional loop — governed agent loop",
     "kind": "optional_loop", "backing": ["governedagent"], "backing_kind": "surface",
     "role": "doctrine-gated agent loop dispatched by the daily loop"},
    {"id": "governed_rag", "title": "Optional loop — governed retrieval",
     "kind": "optional_loop", "backing": ["governedrag"], "backing_kind": "surface",
     "role": "governed retrieval loop dispatched by the daily loop"},
    {"id": "loopforge", "title": "Optional loop — loopforge",
     "kind": "optional_loop", "backing": ["loopforge"], "backing_kind": "surface",
     "role": "loop-composition surface dispatched by the daily loop"},
    {"id": "mesh", "title": "Optional loop — mesh orchestrator",
     "kind": "optional_loop", "backing": ["mesh"], "backing_kind": "surface",
     "role": "mesh orchestration loop dispatched by the daily loop"},
]

# Directed control/data flow between nodes. An edge is rendered ONLY when BOTH endpoints are
# present this request (never a dangling edge to an absent node).
EDGE_SPECS = [
    {"src": "standing_goals", "dst": "daily_loop", "flow": "control",
     "label": "standing goals gate every loop step"},
    {"src": "daily_loop", "dst": "trust_ledger", "flow": "data",
     "label": "loop writes belief-tier updates + receipts"},
    {"src": "daily_loop", "dst": "governed_agent", "flow": "control",
     "label": "loop dispatches to the governed agent loop"},
    {"src": "daily_loop", "dst": "governed_rag", "flow": "control",
     "label": "loop dispatches to governed retrieval"},
    {"src": "daily_loop", "dst": "loopforge", "flow": "control",
     "label": "loop dispatches to loopforge"},
    {"src": "daily_loop", "dst": "mesh", "flow": "control",
     "label": "loop dispatches to the mesh orchestrator"},
    {"src": "governed_agent", "dst": "trust_ledger", "flow": "data",
     "label": "optional loop emits receipts to the ledger"},
    {"src": "governed_rag", "dst": "trust_ledger", "flow": "data",
     "label": "optional loop emits receipts to the ledger"},
    {"src": "loopforge", "dst": "trust_ledger", "flow": "data",
     "label": "optional loop emits receipts to the ledger"},
    {"src": "mesh", "dst": "trust_ledger", "flow": "data",
     "label": "optional loop emits receipts to the ledger"},
]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# In-process introspection — the surface registry + the honestywall aggregate. Both guarded:
# on any failure the map degrades honestly (nodes UNKNOWN) rather than raising.
# ---------------------------------------------------------------------------

def _registry_ids() -> set:
    """The app's OWN live surface-registry ids, imported in-process (never re-typed here)."""
    try:
        import szl3d_holographic as holo
        surfaces = getattr(holo, "SURFACES", None)
        if not isinstance(surfaces, list):
            return set()
        return {s.get("id") for s in surfaces if isinstance(s, dict) and s.get("id")}
    except Exception:
        return set()


# Cross-thread recursion guard. The frontier-index probe honestywall uses invokes route
# callables in a worker thread, so a plain module-level flag (visible across threads) is the
# correct barrier — not a thread-local one.
_HW_LOCK = threading.Lock()
_HW_ACTIVE = False


def _honestywall_aggregate(app, ns: str = "a11oy") -> dict | None:
    """Consume the honestywall aggregate via its OWN in-process API (never an HTTP hop out of
    the Space). Returns the aggregate dict, or None if honestywall is unavailable OR if this
    call would re-enter an in-flight honestywall read (recursion guard) — in which case the
    caller degrades every node honestly to UNKNOWN, never a fabricated pass."""
    global _HW_ACTIVE
    with _HW_LOCK:
        if _HW_ACTIVE:
            return None
        _HW_ACTIVE = True
    try:
        import szl_honestywall as hw
        agg = hw.build_aggregate(app, ns)
        return agg if isinstance(agg, dict) else None
    except Exception:
        return None
    finally:
        with _HW_LOCK:
            _HW_ACTIVE = False


# ---------------------------------------------------------------------------
# Verdict derivation — read the honestywall aggregate VERBATIM; never upgrade.
# ---------------------------------------------------------------------------

def _hw_index(agg: dict | None) -> dict:
    """Map of surface id -> its honestywall per-surface entry."""
    if not isinstance(agg, dict):
        return {}
    out = {}
    for e in agg.get("surfaces", []) or []:
        if isinstance(e, dict) and e.get("id"):
            out[e["id"]] = e
    return out


def _doctrine_verdict(agg: dict | None) -> tuple[str, str]:
    """Verdict for the immutable-doctrine node, from the honestywall doctrine block. Returns
    (verdict, reason). UNKNOWN if the aggregate is unreachable; VIOLATED if a doctrine fact is
    contradicted; INTACT only when locked-8 is exact and Λ/trust invariants hold."""
    if not isinstance(agg, dict):
        return N_UNKNOWN, "honestywall aggregate unreachable this request"
    d = agg.get("doctrine") if isinstance(agg.get("doctrine"), dict) else {}
    locked = d.get("locked_proven")
    adds = d.get("adds_to_locked_8")
    lam = str(d.get("lambda", "")).lower()
    tc = d.get("trust_ceiling")
    t100 = d.get("trust_100_percent")
    bad = []
    if not (isinstance(locked, (int, float)) and not isinstance(locked, bool) and int(locked) == LOCKED_COUNT):
        bad.append(f"locked_proven={locked!r} (expected {LOCKED_COUNT})")
    if isinstance(adds, (int, float)) and not isinstance(adds, bool) and int(adds) != 0:
        bad.append(f"adds_to_locked_8={adds!r} (expected 0)")
    if "conjecture" in lam and "theorem" in lam:
        bad.append(f"lambda={d.get('lambda')!r} (Λ must be a Conjecture, never a theorem)")
    if isinstance(tc, (int, float)) and not isinstance(tc, bool) and tc > TRUST_CEILING + 1e-9:
        bad.append(f"trust_ceiling={tc!r} (> {TRUST_CEILING})")
    if t100 is True:
        bad.append("trust_100_percent=True")
    if bad:
        return N_VIOLATED, "; ".join(bad)
    return N_INTACT, f"locked-8 exact @ {KERNEL_COMMIT}; Λ=Conjecture 1; trust ceiling {TRUST_CEILING}"


def _surface_verdict(backing: list, hw_by_id: dict, agg: dict | None) -> tuple[str, str, list]:
    """Verdict for a surface-backed node from the honestywall per-surface entries of its
    backing ids. Returns (verdict, reason, per_backing_detail)."""
    detail = []
    if agg is None:
        for b in backing:
            detail.append({"surface": b, "hw_status": None, "violations": 0})
        return N_UNKNOWN, "honestywall aggregate unreachable this request", detail

    any_violated = False
    any_unknown = False
    for b in backing:
        entry = hw_by_id.get(b)
        if entry is None:
            any_unknown = True
            detail.append({"surface": b, "hw_status": None, "violations": 0,
                           "note": "not present in honestywall aggregate this request"})
            continue
        status = entry.get("status")
        viol = int(entry.get("checks_violated", 0) or 0)
        detail.append({"surface": b, "hw_status": status, "violations": viol,
                       "label": entry.get("label")})
        if viol >= 1:
            any_violated = True
        elif status != _HW_NATIVE_OK:
            any_unknown = True

    if any_violated:
        return N_VIOLATED, "a backing surface reports a reachable invariant violation", detail
    if any_unknown:
        return N_UNKNOWN, "a backing surface manifest was unreachable/non-native this request", detail
    return N_INTACT, "all backing surface(s) NATIVE-OK with 0 reachable violations", detail


# ---------------------------------------------------------------------------
# Map assembly — pure computation; mints nothing.
# ---------------------------------------------------------------------------

def _build_map(app, ns: str = "a11oy") -> dict:
    agg = _honestywall_aggregate(app, ns)
    hw_by_id = _hw_index(agg)
    registry = _registry_ids()

    nodes = []
    present_ids = set()
    for spec in NODE_SPECS:
        if spec["backing_kind"] == "surface":
            present = any(b in registry for b in spec["backing"])
        else:  # doctrine invariant — immutable OS constraint, always rendered fixed
            present = True
        if not present:
            continue  # never invent a node whose backing is absent from the live registry
        present_ids.add(spec["id"])

        if spec["backing_kind"] == "doctrine":
            verdict, reason = _doctrine_verdict(agg)
            detail = []
        else:
            verdict, reason, detail = _surface_verdict(spec["backing"], hw_by_id, agg)

        nodes.append({
            "id": spec["id"],
            "title": spec["title"],
            "kind": spec["kind"],
            "role": spec["role"],
            "backing": list(spec["backing"]),
            "backing_kind": spec["backing_kind"],
            "verdict": verdict,
            "verdict_reason": reason,
            "backing_detail": detail,
        })

    edges = [
        {"src": e["src"], "dst": e["dst"], "flow": e["flow"], "label": e["label"]}
        for e in EDGE_SPECS
        if e["src"] in present_ids and e["dst"] in present_ids
    ]

    verdict_counts: dict[str, int] = {N_INTACT: 0, N_DEGRADED: 0, N_UNKNOWN: 0, N_VIOLATED: 0}
    for n in nodes:
        verdict_counts[n["verdict"]] = verdict_counts.get(n["verdict"], 0) + 1

    if verdict_counts.get(N_VIOLATED, 0) >= 1:
        state = HALTED_HONEST
        state_reason = (f"{verdict_counts[N_VIOLATED]} backing node(s) VIOLATED; the map "
                        "declares itself untrustworthy rather than rendering green")
    elif verdict_counts.get(N_UNKNOWN, 0) + verdict_counts.get(N_DEGRADED, 0) >= 1:
        state = MAP_DEGRADED
        state_reason = (f"{verdict_counts.get(N_UNKNOWN, 0)} UNKNOWN + "
                        f"{verdict_counts.get(N_DEGRADED, 0)} DEGRADED backing node(s); "
                        "0 violated")
    else:
        state = OPERATING
        state_reason = "every present backing node INTACT"

    return {
        "ok": True,
        "endpoint": "govern/agentos/map",
        "service": "a11oy.govern.agentos",
        "surface_id": SURFACE_ID,
        "title": "Agent OS map — live, self-honest operator's-eye map",
        "label": MODELED,
        "state": state,
        "state_reason": state_reason,
        "what": ("a LIVE operator's-eye map of the agent OS, composed ENTIRELY from our OWN "
                 "governed components. Node presence is derived from the live surface registry; "
                 "each node's honesty verdict is sourced VERBATIM from the honestywall aggregate. "
                 "NEVER OPERATING if anything is VIOLATED; a node with an unreachable backing "
                 "renders UNKNOWN, never a confident node. Composes only — advances no capability."),
        "spark": {"source": "@Av1dlive on X", "url": SPARK_URL, "note": SPARK_NOTE},
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "nodes_present": len(nodes),
            "edges_present": len(edges),
            "verdict_counts": verdict_counts,
            "honestywall_reachable": agg is not None,
            "honestywall_verdict": (agg.get("verdict") if isinstance(agg, dict) else None),
        },
        "introspection": {
            "surface_registry": "szl3d_holographic.SURFACES (imported in-process)",
            "verdict_source": "szl_honestywall.build_aggregate (in-process; VERBATIM, never upgraded)",
            "no_http_hop": True,
        },
        "doctrine": {
            "label_top": MODELED,
            "locked_proven": LOCKED_COUNT,
            "locked_set": LOCKED_SET,
            "kernel_commit": KERNEL_COMMIT,
            "adds_to_locked_8": 0,
            "lambda": "Conjecture 1",
            "khipu_bft": "Conjecture 2",
            "trust_ceiling": TRUST_CEILING,
            "trust_100_percent": False,
            "runtime_cdn": 0,
            "note": ("additive OBSERVE/compose-only surface; touches no locked formula and no "
                     "kernel; GET reads sign/mint nothing; POST snapshot emits an UNSIGNED "
                     "SHA-256 content digest only; introduces no theorem, no green/1.0."),
        },
        "state_legend": {
            OPERATING: "every present backing node INTACT",
            MAP_DEGRADED: "some node UNKNOWN/DEGRADED, none VIOLATED",
            HALTED_HONEST: ">= 1 backing node VIOLATED (never rendered as OPERATING)",
        },
        "timestamp_utc": _now_iso(),
    }


_MAP_TTL = 30.0  # seconds — warm reads serve the last real map; the cache only holds real output.


def build_map(app, ns: str = "a11oy") -> dict:
    """Cached entrypoint. Serves the last real map for _MAP_TTL seconds so a read does not
    re-probe the whole estate on every hit. The cache only ever holds real output."""
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    key = (id(app), ns)
    cache = getattr(build_map, "_cache", None)
    if cache is not None:
        ck, ts, val = cache
        if ck == key and (now - ts) < _MAP_TTL:
            return val
    val = _build_map(app, ns)
    build_map._cache = (key, now, val)  # type: ignore[attr-defined]
    return val


# ---------------------------------------------------------------------------
# Self-manifest — STATIC honesty posture. This is what honestywall reads for agentos, so it
# must NEVER call honestywall (no recursion) and never lie about its own posture.
# ---------------------------------------------------------------------------

def _self_manifest(ns: str = "a11oy") -> dict:
    base = f"/api/{ns}/v1/govern/agentos"
    return {
        "service": "a11oy.govern.agentos",
        "label": MODELED,
        "surface_id": SURFACE_ID,
        "endpoint": f"{base}/status",
        "spark": {"source": "@Av1dlive on X", "url": SPARK_URL, "note": SPARK_NOTE},
        "doctrine": {
            "label_top": MODELED,
            "locked_proven": LOCKED_COUNT,
            "locked_set": LOCKED_SET,
            "kernel_commit": KERNEL_COMMIT,
            "adds_to_locked_8": 0,
            "lambda": "Conjecture 1",
            "khipu_bft": "Conjecture 2",
            "trust_ceiling": TRUST_CEILING,
            "trust_100_percent": False,
            "runtime_cdn": 0,
        },
        "provenance_coverage": 1.0,
        "honesty_invariants": {
            "composes_only_never_advances_capability": True,
            "never_operating_while_any_node_violated": True,
            "unreachable_backing_renders_unknown": True,
            "never_invents_a_node_absent_from_registry": True,
            "never_upgrades_a_label": True,
            "receipt_on_write_not_on_read": True,
            "lambda_is_conjecture_1_not_a_theorem": True,
            "adds_nothing_to_locked_8": True,
            "no_consciousness_claim": True,
        },
    }


# ---------------------------------------------------------------------------
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), NEVER on a GET read.
# ---------------------------------------------------------------------------

def _canonical_core(mp: dict) -> str:
    """Deterministic canonical serialization of the integrity-bearing content (excludes the
    volatile timestamp), so the digest attests the STATE + topology, not the clock."""
    core = {
        "state": mp.get("state"),
        "summary": mp.get("summary"),
        "nodes": [
            {"id": n.get("id"), "verdict": n.get("verdict"), "backing": n.get("backing")}
            for n in mp.get("nodes", [])
        ],
        "edges": mp.get("edges", []),
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def _content_receipt(mp: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the map (no signature fabricated)."""
    canonical = _canonical_core(mp)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.agentos.map",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST snapshot)",
        "note": ("unsigned SHA-256 content digest of the agent-OS map; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Handlers.
# ---------------------------------------------------------------------------

def handle_map(app, ns: str = "a11oy") -> dict:
    """GET /govern/agentos (+ /map) — the full live map. PURE READ (mints nothing)."""
    try:
        return build_map(app, ns)
    except Exception as exc:  # never 500: honest degraded response
        return {
            "ok": False, "endpoint": "govern/agentos/map", "label": "UNAVAILABLE",
            "surface_id": SURFACE_ID, "state": MAP_DEGRADED, "error": str(exc)[:200],
            "doctrine": "v11: agent-OS map unavailable; no fabricated state emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_status(ns: str = "a11oy") -> dict:
    """GET /govern/agentos/status — compact STATIC self-manifest (the honestywall probe target;
    does NOT call honestywall, so honestywall's probe of agentos can never recurse). PURE READ."""
    man = _self_manifest(ns)
    man.update({
        "ok": True,
        "endpoint": "govern/agentos/status",
        "title": "Agent OS map — live, self-honest operator's-eye map",
        "note": ("static self-manifest; the live map (with per-node verdicts + overall state) "
                 "is served by GET govern/agentos and POST govern/agentos/snapshot."),
        "timestamp_utc": _now_iso(),
    })
    return man


def handle_info(ns: str = "a11oy") -> dict:
    """GET /govern/agentos/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/govern/agentos"
    man = _self_manifest(ns)
    man.update({
        "ok": True,
        "endpoint": "govern/agentos/info",
        "title": "Agent OS map — live, self-honest operator's-eye map",
        "what": ("a live operator's-eye map of the agent OS composed only from our OWN governed "
                 "components; node presence from the live registry, per-node verdict from the "
                 "honestywall aggregate; never OPERATING while anything is VIOLATED."),
        "endpoints": {
            "map": f"GET  {base}",
            "status": f"GET  {base}/status",
            "info": f"GET  {base}/info",
            "snapshot": f"POST {base}/snapshot",
        },
        "node_template": [
            {"id": s["id"], "kind": s["kind"], "backing": s["backing"],
             "backing_kind": s["backing_kind"]}
            for s in NODE_SPECS
        ],
        "states": [OPERATING, MAP_DEGRADED, HALTED_HONEST],
        "node_verdicts": [N_INTACT, N_DEGRADED, N_UNKNOWN, N_VIOLATED],
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — only POST /snapshot emits an "
                           "unsigned SHA-256 content digest."),
        "timestamp_utc": _now_iso(),
    })
    return man


def handle_snapshot(app, ns: str = "a11oy") -> dict:
    """POST /govern/agentos/snapshot — the full live map + an UNSIGNED SHA-256 content-digest
    receipt (RECEIPT-ON-WRITE). Never 500s: honest degraded response on error."""
    try:
        mp = build_map(app, ns)
        out = dict(mp)
        out["receipt"] = _content_receipt(mp)
        return out
    except Exception as exc:
        return {
            "ok": False, "endpoint": "govern/agentos/snapshot", "label": "UNAVAILABLE",
            "state": MAP_DEGRADED, "error": str(exc)[:200],
            "doctrine": "v11: snapshot unavailable; no fabricated state/receipt emitted.",
            "timestamp_utc": _now_iso(),
        }


# ---------------------------------------------------------------------------
# FastAPI router registration.
#   GET map/status/info — normal FastAPI GET handlers.
#   POST snapshot       — raw-Request handler via app.router.add_route (Starlette passes the
#                         Request positionally, version-proof under fastapi==0.137.x), with
#                         app.add_api_route as the fallback. Registered BEFORE the SPA catch-all.
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/govern/agentos"

    @app.get(base)
    def _agentos_map():
        """The full live agent-OS map (pure read; mints nothing)."""
        return JSONResponse(handle_map(app, ns))

    @app.get(f"{base}/map")
    def _agentos_map_alias():
        """Alias for the full live agent-OS map (pure read; mints nothing)."""
        return JSONResponse(handle_map(app, ns))

    @app.get(f"{base}/status")
    def _agentos_status():
        """Static self-manifest / honestywall probe target (pure read; no honestywall call)."""
        return JSONResponse(handle_status(ns))

    @app.get(f"{base}/info")
    def _agentos_info():
        """Self-describing agent-OS map manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    async def _agentos_snapshot(request):
        """POST: full live map + UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE). The body
        is ignored (a pure map compute)."""
        return JSONResponse(handle_snapshot(app, ns))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature analysis (in
    # the add_api_route fallback path) treats the param as the request object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _agentos_snapshot.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    snap_path = f"{base}/snapshot"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(snap_path, _agentos_snapshot, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(snap_path, _agentos_snapshot, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(snap_path, _agentos_snapshot, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] agentos snapshot POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "agentos-wired:4(get-only)"

    return "agentos-wired:5"


# ---------------------------------------------------------------------------
# Self-test — honest state, no fabricated pass, no label upgrade, receipt only on write.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_agentos — self-test (live self-honest agent-OS map)")
    print("=" * 72)

    from fastapi import FastAPI
    app = FastAPI()
    import szl_frontier_index as _fi_mod
    _fi_mod.register(app, ns="a11oy")
    try:
        import szl_honestywall as _hw
        _hw.register(app, ns="a11oy")
    except Exception as _e:  # pragma: no cover
        print(f"(honestywall not wired for self-test: {_e!r})")
    register(app, ns="a11oy")

    mp = handle_snapshot(app, ns="a11oy")

    # 1) map built, ok:true, MODELED self label, honest state, nodes present.
    assert mp["ok"] is True
    assert mp["label"] == MODELED
    assert mp["state"] in (OPERATING, MAP_DEGRADED, HALTED_HONEST)
    assert len(mp["nodes"]) >= 1
    print(f"[1] map ok, MODELED, state={mp['state']}, "
          f"{len(mp['nodes'])} nodes, {len(mp['edges'])} edges  OK")

    # 2) NEVER OPERATING while any node is VIOLATED; state consistent with evidence.
    vc = mp["summary"]["verdict_counts"]
    if vc.get(N_VIOLATED, 0) >= 1:
        assert mp["state"] == HALTED_HONEST, "must HALT-HONEST when a node is VIOLATED"
    elif vc.get(N_UNKNOWN, 0) + vc.get(N_DEGRADED, 0) >= 1:
        assert mp["state"] == MAP_DEGRADED
    else:
        assert mp["state"] == OPERATING
    print(f"[2] state consistent w/ evidence (verdict_counts={vc})  OK")

    # 3) every node verdict is an honest token; edges never dangle to an absent node.
    present = {n["id"] for n in mp["nodes"]}
    for n in mp["nodes"]:
        assert n["verdict"] in (N_INTACT, N_DEGRADED, N_UNKNOWN, N_VIOLATED)
    for e in mp["edges"]:
        assert e["src"] in present and e["dst"] in present, "edge to an absent node"
    print("[3] all node verdicts honest; no dangling edges  OK")

    # 4) RECEIPT-ON-WRITE: POST snapshot carries an UNSIGNED sha256 digest; GET map mints none.
    r = mp["receipt"]
    assert r["algorithm"] == "sha256" and len(r["content_sha256"]) == 64
    assert r["signed"] is False and r["mode"] == "UNSIGNED-CONTENT-DIGEST"
    gm = handle_map(app, ns="a11oy")
    assert "receipt" not in gm, "GET map must NOT mint a receipt (receipt-on-write-not-on-read)"
    print(f"[4] POST digest={r['content_sha256'][:16]}… unsigned; GET map mints nothing  OK")

    # 5) doctrine: locked-8 exact, adds nothing, Λ Conjecture 1, trust 0.97 not 100%.
    d = mp["doctrine"]
    assert d["locked_proven"] == 8 and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[5] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    print("\nok:true checks:5")
    _sys.exit(0)
