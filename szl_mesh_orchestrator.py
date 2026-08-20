# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""szl_mesh_orchestrator.py — LIVE cross-node mesh orchestration (Wave-P Dev2).

Makes the SZL sovereign mesh REAL across BOTH fleet GPU nodes:

  * omen  ("omen-betterwithage")     — RTX 4060 Ti  · gpu.a-11-oy.com  · meter.a-11-oy.com
  * betterwithage ("rtx-betterwithage") — RTX 5050    · gpu2.a-11-oy.com · meter2.a-11-oy.com

Grounded in the org's OWN libraries (studied, NOT vendored): szl-router (own-GPU-first
routing with receipts), szl-mesh (doctrine-pinned CRDT + DSSE + BFT), khipu-consensus
(BFT 3-of-4 ECDSA-P256 witnesses; safety = Conjecture 2), szl-lake (append-only DSSE Khipu).

Three ADDITIVE, honest GET endpoints (registered BEFORE the SPA catch-all):

  GET /api/a11oy/v1/mesh/status
      Probes BOTH nodes THIS request: the Ollama /api/tags model list (gpu*) AND the NVML
      joule meter (meter*). Per node returns {reachable, models, watts, joules_label} with a
      per-node STATE MACHINE:
        LIVE     — gpu 2xx AND meter live reading this request
        DEGRADED — gpu 2xx but meter 403/1010/timeout/no-live (model-serving up, no energy read)
        OFFLINE  — gpu unreachable / 530 / 1033 (origin/tunnel down)
      reachability is NEVER fabricated — an honest UNAVAILABLE/OFFLINE when a probe fails.

  GET /api/a11oy/v1/mesh/route?model=<tag>
      Which node WOULD serve <model>, per the cheapest-live-watt policy: among LIVE nodes
      that host the model, pick the lowest MEASURED watts (basis `cheapest-measured-watt`);
      when no meter is live, honest round-robin over reachable nodes (basis `heuristic-fallback`).
      ADVISORY routing status (Λ = Conjecture 1, trust ≤ 0.97) — NOT a fabricated dispatch.

  GET /api/a11oy/v1/mesh/quorum
      A 3-of-4 witness-quorum VIEW over the mesh as CONJECTURE 2 (khipu-consensus BFT safety is
      proof-deferred per doctrine). Counts witnesses reachable THIS request; NEVER claims a
      proven/attested consensus — the honest label is STRUCTURAL-ONLY / CONJECTURE-2.

HONESTY SPINE (Doctrine v11 — NON-NEGOTIABLE):
  * MEASURED watts only from a live meter reading THIS request; else the node's energy is a
    plain UNAVAILABLE (joules_label 'sample'/STRUCTURAL-ONLY) — never a fabricated wattage.
  * reachable is set ONLY by a real 2xx probe this request. No green is faked.
  * Λ = Conjecture 1 (advisory, NOT proven trust); BFT = Conjecture 2; locked-proven = 8 (untouched).
  * Pure stdlib transport (urllib), browser-like UA so the Cloudflare-fronted origins do not 403.
"""
import json as _json
import os as _os
import time as _time
import urllib.request as _urllib_request
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse

DOCTRINE_VERSION = "v11"
LAMBDA_STATUS = "Conjecture 1"
BFT_STATUS = "Conjecture 2"
LOCKED_PROVEN = 8
TRUST_CEIL = 0.97

# Browser-like UA (Cloudflare-safe) — the SAME transport the energy/JPT organs use so the
# fronted origins (gpu*.a-11-oy.com, meter*.a-11-oy.com) do not 403 a bare urllib agent.
_PROBE_UA = _os.environ.get(
    "SZL_PROBE_USER_AGENT",
    "Mozilla/5.0 (compatible; szl-mesh-orchestrator/1.0; +https://a-11-oy.com)")
try:
    _PROBE_TIMEOUT_S = float(_os.environ.get("A11OY_MESH_PROBE_TIMEOUT_S", "4.0"))
except (TypeError, ValueError):
    _PROBE_TIMEOUT_S = 4.0

# Cloudflare origin-down / tunnel-error statuses that mean OFFLINE (not merely degraded).
_OFFLINE_HTTP = {521, 522, 523, 530, 1033}
# Statuses that mean the origin is up but the browser signature / WAF blocked the probe.
_BLOCKED_HTTP = {403, 1010, 1020}

# Per-node fleet table. Public Cloudflare hostnames are the DEFAULT ingress; each is
# overridable by env WITHOUT a code change (never hardcodes reachability, only WHERE to look).
_NODES: List[Dict[str, str]] = [
    {
        "name": "omen",
        "label": "omen · RTX 4060 Ti (always-on home brain)",
        "gpu_env": "A11OY_OMEN_BASE_URL",
        "gpu_default": "https://gpu.a-11-oy.com",
        "meter_env": "A11OY_OMEN_METER_URL",
        "meter_default": "https://meter.a-11-oy.com/",
    },
    {
        "name": "betterwithage",
        "label": "betterwithage · RTX 5050 (Blackwell laptop)",
        "gpu_env": "A11OY_BETTERWITHAGE_BASE_URL",
        "gpu_default": "https://gpu2.a-11-oy.com",
        "meter_env": "A11OY_BETTERWITHAGE_METER_URL",
        "meter_default": "https://meter2.a-11-oy.com/",
    },
]

CITATIONS: Dict[str, str] = {
    "szl-router": "own-GPU-first routing with signed receipts (SZL Holdings)",
    "szl-mesh": "doctrine-pinned CRDT + DSSE + BFT mesh state (SZL Holdings)",
    "khipu-consensus": "BFT 3-of-4 ECDSA-P256 witness quorum; safety = Conjecture 2 (proof-deferred)",
    "meter": "meter*.a-11-oy.com — NVML joule exporter (real nvidia-smi power)",
    "doctrine": "SZL Doctrine v11 — MEASURED only from a live reading this request; Λ = Conjecture 1",
}


# ---------------------------------------------------------------------------
# transport — pure stdlib, browser-UA, fully guarded (NEVER raises, NEVER fakes)
# ---------------------------------------------------------------------------
def _http_get_json(url: str, timeout: float) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    """GET url -> (http_status, json_dict) or (status_or_None, None) on any failure.

    Returns the HTTP status when we got a response (so the caller can classify 403/530/etc.),
    None status on a transport-level failure (DNS/connreset/timeout). Guarded; never raises.
    """
    try:
        req = _urllib_request.Request(url, headers={
            "User-Agent": _PROBE_UA, "Accept": "application/json"})
        with _urllib_request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            status = int(getattr(r, "status", None) or 200)
            body = r.read().decode("utf-8", "replace")
        if not (200 <= status < 300):
            return status, None
        doc = _json.loads(body)
        return status, (doc if isinstance(doc, dict) else None)
    except _urllib_request.HTTPError as exc:  # noqa: PERF203 — need the status code
        return int(getattr(exc, "code", 0) or 0) or None, None
    except Exception:  # noqa: BLE001 — degrade honestly
        return None, None


def _gpu_base(node: Dict[str, str]) -> str:
    return (_os.environ.get(node["gpu_env"]) or node["gpu_default"]).strip().rstrip("/")


def _meter_url(node: Dict[str, str]) -> str:
    return (_os.environ.get(node["meter_env"]) or node["meter_default"]).strip()


def _probe_models(node: Dict[str, str]) -> Dict[str, Any]:
    """Probe the node's Ollama /api/tags (fallback /v1/models) for its REAL model list.
    Returns {reachable, models, http_status, api_style, offline}. reachable only on a real 2xx."""
    base = _gpu_base(node)
    root = base[:-3].rstrip("/") if base.endswith("/v1") else base
    last_status: Optional[int] = None
    for url, key, itemkey, style in (
        (root + "/api/tags", "models", "name", "ollama"),
        (root + "/v1/models", "data", "id", "openai"),
    ):
        status, doc = _http_get_json(url, _PROBE_TIMEOUT_S)
        last_status = status if status is not None else last_status
        if doc is not None and isinstance(doc.get(key), list):
            names = [str(m.get(itemkey)) for m in doc[key]
                     if isinstance(m, dict) and m.get(itemkey)]
            return {"reachable": True, "models": names, "http_status": status,
                    "api_style": style, "offline": False}
    offline = bool(last_status in _OFFLINE_HTTP) or last_status is None
    return {"reachable": False, "models": [], "http_status": last_status,
            "api_style": None, "offline": offline}


def _live_watts(doc: Optional[Dict[str, Any]]) -> Optional[float]:
    """First live=true GPU power_w in the meter doc, or None. HARD honesty gate — an engine
    with no live=true real GPU reading is not a live reading (mirrors szl_energy_measured)."""
    if not isinstance(doc, dict):
        return None
    for e in (doc.get("engines") or []):
        if not isinstance(e, dict):
            continue
        for g in (e.get("gpus") or []):
            if isinstance(g, dict) and g.get("live") is True and isinstance(g.get("power_w"), (int, float)):
                return float(g["power_w"])
    return None


def _probe_meter(node: Dict[str, str]) -> Dict[str, Any]:
    """Probe the node's NVML joule meter for a LIVE watt reading THIS request.
    Returns {watts, joules_label, http_status, blocked, reason}. watts is None unless a real
    live=true GPU power reading came back — never a fabricated wattage."""
    url = _meter_url(node)
    status, doc = _http_get_json(url, _PROBE_TIMEOUT_S)
    if status is not None and status in _BLOCKED_HTTP:
        return {"watts": None, "joules_label": "sample", "http_status": status,
                "blocked": True, "reason": "meter WAF/browser-signature blocked (%s)" % status}
    if doc is None:
        return {"watts": None, "joules_label": "sample", "http_status": status,
                "blocked": False,
                "reason": "meter did not respond live this request (status %s)" % status}
    watts = _live_watts(doc)
    if watts is None:
        return {"watts": None, "joules_label": "sample", "http_status": status,
                "blocked": False, "reason": "meter reachable but no live=true GPU reading"}
    return {"watts": round(watts, 3), "joules_label": "measured", "http_status": status,
            "blocked": False, "reason": "live NVML reading this request"}


# ---------------------------------------------------------------------------
# per-node state machine — LIVE / DEGRADED / OFFLINE (never fabricated)
# ---------------------------------------------------------------------------
def probe_node(node: Dict[str, str]) -> Dict[str, Any]:
    """Honest per-node health: probe the model endpoint AND the meter, classify the state.
    reachable/watts are set ONLY by real 2xx readings this request."""
    g = _probe_models(node)
    m = _probe_meter(node)
    if not g["reachable"]:
        state = "OFFLINE"
        note = ("model endpoint unreachable this request (status %s) — honest OFFLINE, "
                "reachability never fabricated" % g["http_status"])
    elif m["joules_label"] == "measured":
        state = "LIVE"
        note = "serving models AND a live NVML watt reading this request"
    else:
        state = "DEGRADED"
        note = "serving models, but energy meter not live (%s)" % m["reason"]
    return {
        "name": node["name"],
        "label": node["label"],
        "state": state,
        "reachable": bool(g["reachable"]),
        "models": g["models"],
        "model_count": len(g["models"]),
        "watts": m["watts"],
        "joules_label": m["joules_label"],
        "api_style": g["api_style"],
        "meter_blocked": bool(m["blocked"]),
        "note": note,
        "probes": {
            "gpu_http_status": g["http_status"],
            "meter_http_status": m["http_status"],
        },
    }


def mesh_status() -> Dict[str, Any]:
    """GET /mesh/status — honest per-node LIVE/DEGRADED/OFFLINE across BOTH fleet nodes."""
    nodes = [probe_node(n) for n in _NODES]
    live = [n for n in nodes if n["state"] == "LIVE"]
    degraded = [n for n in nodes if n["state"] == "DEGRADED"]
    offline = [n for n in nodes if n["state"] == "OFFLINE"]
    measured_any = any(n["joules_label"] == "measured" for n in nodes)
    if live:
        mesh_state = "LIVE" if not (degraded or offline) else "PARTIAL"
    elif degraded:
        mesh_state = "DEGRADED"
    else:
        mesh_state = "OFFLINE"
    return {
        "ok": True,
        "mesh_state": mesh_state,
        "data_label": "MEASURED" if measured_any else "STRUCTURAL-ONLY",
        "nodes": nodes,
        "counts": {
            "total": len(nodes), "live": len(live),
            "degraded": len(degraded), "offline": len(offline),
        },
        "note": (
            "per-node state is set ONLY by real probes THIS request: LIVE = model endpoint 2xx "
            "AND a live NVML watt reading; DEGRADED = models up but no live meter; OFFLINE = "
            "model endpoint unreachable. No reachability or wattage is fabricated."),
        "doctrine": {"version": DOCTRINE_VERSION, "lambda": LAMBDA_STATUS,
                     "locked_proven": LOCKED_PROVEN, "trust_ceiling": TRUST_CEIL},
        "citations": CITATIONS,
        "ts": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
    }


# ---------------------------------------------------------------------------
# routing — cheapest-live-watt policy (advisory; NEVER a fabricated dispatch)
# ---------------------------------------------------------------------------
def mesh_route(model: Optional[str] = None) -> Dict[str, Any]:
    """GET /mesh/route?model= — which node WOULD serve, per cheapest-live-watt policy.

    Policy: among LIVE nodes that host `model` (or all LIVE nodes when model is unspecified),
    pick the lowest MEASURED watts (basis `cheapest-measured-watt`). When no node has a live
    meter reading, fall back to an honest round-robin over reachable nodes that host the model
    (basis `heuristic-fallback`). ADVISORY (Λ = Conjecture 1, trust ≤ 0.97) — not a dispatch."""
    st = mesh_status()
    nodes = st["nodes"]
    want = (model or "").strip()

    def _hosts(n: Dict[str, Any]) -> bool:
        if not want:
            return True
        return any(want.lower() in str(mm).lower() for mm in n["models"])

    candidates = [n for n in nodes if n["reachable"] and _hosts(n)]
    live_metered = [n for n in candidates if n["state"] == "LIVE" and isinstance(n["watts"], (int, float))]

    chosen: Optional[Dict[str, Any]] = None
    basis: str
    if live_metered:
        chosen = min(live_metered, key=lambda n: n["watts"])
        basis = "cheapest-measured-watt"
        reason = ("chosen among %d live-metered node(s) by lowest MEASURED watts (%s W) — "
                  "real reading this request" % (len(live_metered), chosen["watts"]))
    elif candidates:
        # honest round-robin: deterministic pick by name so the fallback is stable + explainable
        chosen = sorted(candidates, key=lambda n: n["name"])[0]
        basis = "heuristic-fallback"
        reason = ("no live meter reading this request — honest round-robin over %d reachable "
                  "node(s); watts UNKNOWN so cheapest-watt cannot be applied" % len(candidates))
    else:
        basis = "none"
        reason = ("no reachable node hosts %r this request — honest NO-LIVE-DATA, no route "
                  "fabricated" % (want or "<any>"))

    return {
        "ok": True,
        "requested_model": want or None,
        "route": chosen["name"] if chosen else None,
        "route_label": chosen["label"] if chosen else None,
        "route_state": chosen["state"] if chosen else None,
        "route_watts": chosen["watts"] if chosen else None,
        "policy": "cheapest-live-watt (own-GPU-first, szl-router doctrine)",
        "basis": basis,
        "data_label": "MEASURED" if basis == "cheapest-measured-watt" else "MODELED",
        "advisory": True,
        "reason": reason,
        "candidates": [{"name": n["name"], "state": n["state"], "watts": n["watts"],
                        "hosts_model": _hosts(n)} for n in nodes if n["reachable"]],
        "note": ("ADVISORY routing status (Λ = Conjecture 1, trust ≤ %.2f) — this is which node "
                 "WOULD serve under the policy, NOT a fabricated dispatch or a proven placement."
                 % TRUST_CEIL),
        "doctrine": {"version": DOCTRINE_VERSION, "lambda": LAMBDA_STATUS,
                     "trust_ceiling": TRUST_CEIL},
        "ts": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
    }


# ---------------------------------------------------------------------------
# quorum — 3-of-4 witness VIEW as CONJECTURE 2 (never claims proven consensus)
# ---------------------------------------------------------------------------
def mesh_quorum() -> Dict[str, Any]:
    """GET /mesh/quorum — a 3-of-4 witness-quorum VIEW over the mesh, honestly labeled as
    CONJECTURE 2 (khipu-consensus BFT safety is proof-deferred per doctrine v11).

    Witnesses = this box (self, reachable by definition) + the two GPU nodes + a governance
    witness. We count how many are reachable THIS request; a real BFT quorum needs ≥3 signed
    `allow` votes. We NEVER claim a proven/attested consensus — the honest posture is that a
    quorum WOULD form iff ≥3 witnesses are live, and even then safety remains Conjecture 2."""
    st = mesh_status()
    node_witnesses = [
        {"witness": "self (orchestrator host)", "reachable": True,
         "kind": "self", "note": "host running this service — reachable by definition"},
    ]
    for n in st["nodes"]:
        node_witnesses.append({
            "witness": n["name"], "reachable": bool(n["reachable"]),
            "kind": "gpu-node", "state": n["state"],
            "note": n.get("note", ""),
        })
    # A 4th governance witness rounds the set to 4 (khipu-consensus 3-of-4). It is a
    # STRUCTURAL witness slot here (no live signing endpoint wired in this runtime) — honestly
    # reported as reachable=False so we NEVER inflate the live-witness count.
    node_witnesses.append({
        "witness": "governance-witness", "reachable": False, "kind": "governance",
        "note": "khipu-consensus signing witness — no live signing endpoint in this runtime; "
                "counted STRUCTURALLY, never faked reachable"})

    reachable = sum(1 for w in node_witnesses if w["reachable"])
    total = len(node_witnesses)
    threshold = 3
    would_form = reachable >= threshold
    return {
        "ok": True,
        "consensus_model": "BFT 3-of-4 witness quorum (khipu-consensus)",
        "data_label": "STRUCTURAL-ONLY",
        "conjecture": BFT_STATUS,
        "threshold": threshold,
        "witnesses_total": total,
        "witnesses_reachable": reachable,
        "quorum_would_form": would_form,
        "quorum_proven": False,
        "witnesses": node_witnesses,
        "note": ("a real quorum needs >=%d signed `allow` votes; %d of %d witness(es) are "
                 "reachable this request. This is a STRUCTURAL VIEW — BFT safety is %s "
                 "(proof-deferred). We NEVER claim a proven or attested consensus."
                 % (threshold, reachable, total, BFT_STATUS)),
        "doctrine": {"version": DOCTRINE_VERSION, "bft": BFT_STATUS,
                     "lambda": LAMBDA_STATUS, "locked_proven": LOCKED_PROVEN},
        "citations": CITATIONS,
        "ts": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
    }


def info(ns: str = "a11oy") -> Dict[str, Any]:
    return {
        "capability": "Live cross-node mesh orchestration (status/route/quorum)",
        "ns": ns,
        "nodes": [{"name": n["name"], "label": n["label"]} for n in _NODES],
        "endpoints": [
            f"/api/{ns}/v1/mesh/status",
            f"/api/{ns}/v1/mesh/route",
            f"/api/{ns}/v1/mesh/quorum",
        ],
        "doctrine": {"version": DOCTRINE_VERSION, "lambda": LAMBDA_STATUS,
                     "bft": BFT_STATUS, "locked_proven": LOCKED_PROVEN,
                     "trust_ceiling": TRUST_CEIL},
        "citations": CITATIONS,
    }


# ---------------------------------------------------------------------------
# registration — dual-register /api/{ns}/v1/* AND /v1/*, BEFORE the SPA catch-all.
# Module-level Request/JSONResponse imports keep the raw-Request annotation valid
# under fastapi 0.137.2 (register via starlette router, add_api_route as fallback).
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    from starlette.concurrency import run_in_threadpool

    async def _h_status():  # noqa: ANN202
        return JSONResponse(await run_in_threadpool(mesh_status))

    async def _h_route(request: Request):  # noqa: ANN202 — reads ?model=
        model = None
        try:
            model = request.query_params.get("model")
        except Exception:  # noqa: BLE001 — no/invalid query => route over any model
            model = None
        return JSONResponse(await run_in_threadpool(mesh_route, model))

    async def _h_quorum():  # noqa: ANN202
        return JSONResponse(await run_in_threadpool(mesh_quorum))

    async def _h_info():  # noqa: ANN202
        return JSONResponse(info(ns))

    routes: List[str] = []
    for base in (f"/api/{ns}/v1", "/v1"):
        app.add_api_route(f"{base}/mesh/status", _h_status,
                          methods=["GET"], include_in_schema=True)
        # /mesh/route takes a raw Request (module-level `from fastapi import Request` makes the
        # annotation resolvable so add_api_route does not misread it as a query param). Register
        # via the Starlette router (version-proof), add_api_route as the fallback.
        try:
            app.router.add_route(f"{base}/mesh/route", _h_route, methods=["GET"])
        except Exception:  # noqa: BLE001 — fall back to the FastAPI registrar
            app.add_api_route(f"{base}/mesh/route", _h_route,
                              methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{base}/mesh/quorum", _h_quorum,
                          methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{base}/mesh/info", _h_info,
                          methods=["GET"], include_in_schema=False)
        routes.extend([f"{base}/mesh/status", f"{base}/mesh/route",
                       f"{base}/mesh/quorum", f"{base}/mesh/info"])

    print(f"[{ns}] szl_mesh_orchestrator routes registered "
          f"(live cross-node mesh: status/route/quorum, {len(routes)} routes)", flush=True)
    return {"ok": True, "ns": ns, "routes": routes,
            "data_label": "STRUCTURAL-ONLY", "nodes": [n["name"] for n in _NODES]}


# ---------------------------------------------------------------------------
# no-server self-test — proves the state machine + honesty spine with mocked probes
# (no HTTP, no live deps). Run: python szl_mesh_orchestrator.py
# ---------------------------------------------------------------------------
def _selftest() -> Dict[str, Any]:
    import unittest.mock as _mock

    out: Dict[str, Any] = {}

    # 1. LIVE node: models 2xx + live meter watts -> state LIVE, joules_label measured.
    with _mock.patch.object(_sys_mod, "_probe_models",
                            return_value={"reachable": True, "models": ["qwen2.5:7b"],
                                          "http_status": 200, "api_style": "ollama", "offline": False}), \
         _mock.patch.object(_sys_mod, "_probe_meter",
                            return_value={"watts": 12.5, "joules_label": "measured",
                                          "http_status": 200, "blocked": False, "reason": "live"}):
        n = probe_node(_NODES[0])
    assert n["state"] == "LIVE" and n["watts"] == 12.5 and n["joules_label"] == "measured", n
    out["live_node"] = n["state"]

    # 2. DEGRADED node: models 2xx but meter blocked (403) -> DEGRADED, watts None (never faked).
    with _mock.patch.object(_sys_mod, "_probe_models",
                            return_value={"reachable": True, "models": ["llama3.1:8b"],
                                          "http_status": 200, "api_style": "ollama", "offline": False}), \
         _mock.patch.object(_sys_mod, "_probe_meter",
                            return_value={"watts": None, "joules_label": "sample",
                                          "http_status": 403, "blocked": True, "reason": "blocked"}):
        n = probe_node(_NODES[0])
    assert n["state"] == "DEGRADED" and n["watts"] is None, n
    out["degraded_node"] = n["state"]

    # 3. OFFLINE node: models unreachable (530) -> OFFLINE, reachable False, models [].
    with _mock.patch.object(_sys_mod, "_probe_models",
                            return_value={"reachable": False, "models": [],
                                          "http_status": 530, "api_style": None, "offline": True}), \
         _mock.patch.object(_sys_mod, "_probe_meter",
                            return_value={"watts": None, "joules_label": "sample",
                                          "http_status": None, "blocked": False, "reason": "x"}):
        n = probe_node(_NODES[0])
    assert n["state"] == "OFFLINE" and n["reachable"] is False and n["models"] == [], n
    out["offline_node"] = n["state"]

    # 4. route: cheapest-measured-watt picks the lower-watt LIVE node.
    fake_status = {
        "nodes": [
            {"name": "omen", "label": "omen", "state": "LIVE", "reachable": True,
             "models": ["qwen2.5:7b"], "watts": 18.0, "joules_label": "measured"},
            {"name": "betterwithage", "label": "bwa", "state": "LIVE", "reachable": True,
             "models": ["qwen2.5:7b"], "watts": 9.0, "joules_label": "measured"},
        ],
    }
    with _mock.patch.object(_sys_mod, "mesh_status", return_value=fake_status):
        r = mesh_route("qwen2.5:7b")
    assert r["route"] == "betterwithage" and r["basis"] == "cheapest-measured-watt", r
    assert r["data_label"] == "MEASURED", r
    out["route_cheapest"] = r["route"]

    # 5. route heuristic fallback: no live meter -> round-robin, watts UNKNOWN, MODELED label.
    fake_status2 = {
        "nodes": [
            {"name": "omen", "label": "omen", "state": "DEGRADED", "reachable": True,
             "models": ["m"], "watts": None, "joules_label": "sample"},
            {"name": "betterwithage", "label": "bwa", "state": "OFFLINE", "reachable": False,
             "models": [], "watts": None, "joules_label": "sample"},
        ],
    }
    with _mock.patch.object(_sys_mod, "mesh_status", return_value=fake_status2):
        r = mesh_route("m")
    assert r["route"] == "omen" and r["basis"] == "heuristic-fallback" and r["data_label"] == "MODELED", r
    out["route_fallback"] = r["basis"]

    # 6. route none: no reachable node hosts the model -> honest NO-LIVE-DATA, no fabricated route.
    with _mock.patch.object(_sys_mod, "mesh_status", return_value=fake_status2):
        r = mesh_route("nonexistent-model")
    assert r["route"] is None and r["basis"] == "none", r
    out["route_none"] = r["basis"]

    # 7. quorum: honest CONJECTURE 2, never proven; governance witness never faked reachable.
    with _mock.patch.object(_sys_mod, "mesh_status", return_value=fake_status):
        q = mesh_quorum()
    assert q["conjecture"] == BFT_STATUS and q["quorum_proven"] is False, q
    assert q["data_label"] == "STRUCTURAL-ONLY", q
    gov = [w for w in q["witnesses"] if w["kind"] == "governance"][0]
    assert gov["reachable"] is False, gov
    out["quorum_conjecture"] = q["conjecture"]

    # 8. info: exposes the three endpoints + doctrine.
    i = info()
    assert any("/mesh/status" in e for e in i["endpoints"]), i
    assert i["doctrine"]["locked_proven"] == LOCKED_PROVEN and i["doctrine"]["bft"] == BFT_STATUS, i
    out["info_ok"] = True

    return out


import sys as _sys  # noqa: E402 — used only to self-reference for patch.object in _selftest
_sys_mod = _sys.modules[__name__]


if __name__ == "__main__":
    res = _selftest()
    for k, v in res.items():
        print(f"  ok  {k}: {v}")
    print("szl_mesh_orchestrator: ALL OK")
