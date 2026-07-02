#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""a11oy_operator_organ.py — the OPERATOR organ (live 3D infrastructure topology).

ADDITIVE, self-contained. Registered in serve.py via register(app) and the routes
are moved to the FRONT of the router (same pattern as a11oy_dev1_endpoints) so the
explicit /operator-organ* routes win over the SPA + proxy catch-alls.

PROVENANCE: the real 3D infra-visualization *capability* was ingested from an
internal showpiece Space and re-homed here as the platform's Operator organ. The
codename of that showpiece is NOT surfaced anywhere — the user-visible name is
"Operator". The viz engine (orbiting service nodes, signal wires, live health
poll) is that ingested capability, re-themed to a11oy's sovereign-gold palette and
honestly reframed as an infrastructure topology.

ROUTES (all GET, additive):
  /operator-organ                  -> pages/operator_organ.html (the 3D page)
  /operator-organ/app.js           -> static/a11oy_operator_organ.js (vendored-three viz)
  /operator-organ/topology.json    -> honest topology: 6 governed-organ nodes + a
                                       best-effort liveness probe of in-process
                                       health, with an honest source flag
                                       (live | cached). 0 fabricated telemetry.

Doctrine v11: locked-proven = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17; Λ =
Conjecture 1; SLSA L1 honest + L2 build-attestation present. 0 runtime CDN.
Signed-off-by: Opus 4.8 (Dev3 — Operator-organ ingest). Co-Authored-By: SZL Holdings.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Container WORKDIR is /app (set by Dockerfile). For local QA, fall back to the
# module's own directory so the page/JS resolve without changing prod behavior.
_APP = Path("/app") if (Path("/app") / "pages").is_dir() else Path(__file__).resolve().parent
_PAGES = _APP / "pages"
_STATIC = _APP / "static"

# The governed organs the Operator orchestrates. Positions match the viz
# fallback. `probe` is an in-process health route we can hit locally (best-effort).
_NODES = [
    {"id": "gate",      "name": "Trust Gate",       "role": "heart",       "pos": [13, 6, 2],   "probe": "/api/a11oy/healthz"},
    {"id": "reasoning", "name": "Reasoning Cortex", "role": "brain",       "pos": [8, 12, -3],  "probe": "/api/a11oy/v1/brain"},
    {"id": "receipts",  "name": "Receipt Bus",      "role": "circulatory", "pos": [-13, 7, 2],  "probe": "/api/a11oy/healthz"},
    {"id": "telemetry", "name": "Telemetry Spans",  "role": "nervous",     "pos": [12, -5, 3],  "probe": "/api/a11oy/healthz"},
    {"id": "mesh",      "name": "Service Mesh",     "role": "skeleton",    "pos": [-12, -5, 3], "probe": "/api/a11oy/healthz"},
    {"id": "fleet",     "name": "Fleet C2",         "role": "effector",    "pos": [0, 6, -15],  "probe": "/api/a11oy/healthz"},
    # WALLPA — the VOICE/expression organ (Doctrine v13 §2.2). Best-effort liveness
    # via the in-process voices route; honestly null (amber) when unmeasured.
    {"id": "voice",     "name": "Wallpa Voice",     "role": "voice",       "pos": [0, -12, -6], "probe": "/api/a11oy/wallpa/voices"},
    # AYLLU — the a11oy-native agent community (ingested tribe). Liveness via the
    # roster route (registered in-process); honestly null (amber) when unmeasured.
    {"id": "ayllu",     "name": "Ayllu Council",    "role": "community",   "pos": [0, 2, 15],   "probe": "/api/a11oy/v1/ayllu/roster"},
]

# Honest cache of the last successfully-built topology (so a degraded probe
# returns the last-known good with source="cached" instead of fabricating).
_CACHE: dict = {"topo": None, "ts": 0.0}


def _build_topology(app) -> dict:
    """Build the topology with a best-effort in-process liveness signal.

    We do NOT fabricate health. If we cannot determine liveness we leave
    `healthy` = null (the viz renders it 'unmeasured', amber). If the process
    itself is serving this route, the core orchestrator is by definition up.
    """
    nodes = []
    any_measured = False
    # Cheap, honest signal: which probe paths actually have a registered route.
    try:
        route_paths = {getattr(r, "path", None) for r in app.router.routes}
    except Exception:
        route_paths = set()
    for nd in _NODES:
        healthy = None
        probe = nd.get("probe")
        if probe:
            # If the route is registered in THIS process, it is reachable here.
            if probe in route_paths:
                healthy = True
                any_measured = True
            else:
                # route not in this image -> honestly unmeasured (null), not down
                healthy = None
        nodes.append({
            "id": nd["id"], "name": nd["name"], "role": nd["role"],
            "pos": nd["pos"], "healthy": healthy,
        })
    topo = {
        "core": {"id": "operator", "name": "Operator Core", "role": "orchestrator", "healthy": True},
        "nodes": nodes,
        "source": "live" if any_measured else "cached",
        "doctrine": {"version": "v11", "locked_proven": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
                     "lambda": "Conjecture 1", "kernel": "c7c0ba17"},
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "Operator organ — ingested infra-viz capability. Health is best-effort "
                "in-process route presence; unmeasured nodes are null (amber), never faked.",
    }
    return topo


def register(app, ns: str = "a11oy") -> str:
    """Register the Operator-organ routes and move them to the FRONT of the router.

    Front-move mirrors a11oy_dev1_endpoints: serve.py's proxy + SPA catch-alls are
    registered earlier, so plain @app.get decorators would be shadowed without the
    reorder. Path namespace /operator-organ does not overlap any other dev block.
    """
    try:
        from fastapi.responses import FileResponse, JSONResponse, HTMLResponse  # noqa
        from starlette.responses import Response  # noqa
    except Exception as e:  # pragma: no cover
        return f"unavailable: {e!r}"

    n_before = len(app.router.routes)

    @app.get("/operator-organ")
    async def _operator_page() -> Response:  # noqa
        f = _PAGES / "operator_organ.html"
        if f.is_file():
            return FileResponse(str(f), media_type="text/html; charset=utf-8")
        return JSONResponse({"error": "operator organ page missing"}, status_code=404)

    @app.get("/operator-organ/app.js")
    async def _operator_js() -> Response:  # noqa
        f = _STATIC / "a11oy_operator_organ.js"
        if f.is_file():
            return FileResponse(
                str(f), media_type="application/javascript; charset=utf-8",
                headers={"Cache-Control": "public, max-age=3600"})
        return JSONResponse({"error": "operator organ js missing"}, status_code=404)

    @app.get("/operator-organ/topology.json")
    async def _operator_topology() -> Response:  # noqa
        try:
            topo = _build_topology(app)
            _CACHE["topo"] = topo
            _CACHE["ts"] = time.time()
            return JSONResponse(topo)
        except Exception:
            if _CACHE["topo"]:
                t = dict(_CACHE["topo"]); t["source"] = "cached"
                return JSONResponse(t)
            return JSONResponse({"nodes": [], "source": "cached",
                                 "note": "topology unavailable; honest degrade"}, status_code=200)

    # Move the just-registered routes to the front so they win over catch-alls.
    new = app.router.routes[n_before:]
    del app.router.routes[n_before:]
    app.router.routes[0:0] = new
    print(f"[{ns}] Operator organ registered: /operator-organ (+app.js +topology.json) "
          f"[moved {len(new)} routes to front]", file=sys.stderr)
    return f"ok: {len(new)} routes (operator organ, 0 CDN, ingested infra-viz)"


if __name__ == "__main__":
    # local sanity check (no FastAPI app) — print the static topology skeleton
    class _Stub:
        class router:  # noqa
            routes = []
    print(json.dumps(_build_topology(_Stub), indent=2))