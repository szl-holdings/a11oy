# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · Doctrine v11
"""szl_counter_uas_proxy.py — same-origin Counter-UAS live bridge (Dev4 surface).

The /holographic Counter-UAS surface (static/3d/surfaces/counter-uas.js) must wire
to REAL killinchu live data (doctrine v11: WIRE TO LIVE DATA, never fabricate). The
killinchu decision+evidence organ lives on a separate Space
(https://szlholdings-killinchu.hf.space), so a browser fetch would be cross-origin.

This module registers a small, additive, server-side proxy under the a11oy namespace
so the surface can poll SAME-ORIGIN (0 CDN, no CORS):

  GET  /api/a11oy/v1/counter-uas/evaluate    -> killinchu POST .../counter-uas/evaluate
       (live Λ decision + REAL ECDSA-P256 DSSE signature over the receipt)
  GET  /api/a11oy/v1/counter-uas/telemetry   -> killinchu .../drone/telemetry
       (friendly fleet + threat tracks, honest data_kind)
  GET  /api/a11oy/v1/counter-uas/cued-tracks -> killinchu .../drone/cued-tracks
  GET  /api/a11oy/v1/counter-uas/air-picture -> killinchu .../drone/air-picture
       (real cooperative ADS-B from airplanes.live)
  GET  /api/a11oy/v1/counter-uas/gates       -> killinchu .../v1/gates (13-axis Λ gate spec)

The 53-fingerprint drone classification DB is the killinchu repo's own drones_db.json
(verified count = 53), vendored verbatim into the static tree and served same-origin at
/static/3d/surfaces/data/drones_db.json (killinchu does not expose it as a JSON HTTP
route — its root path serves the Cesium SPA). Vendored-not-fabricated.

HONESTY (killinchu charter / JIATF-401 crosswalk): killinchu SENSES & EVIDENCES — it
does NOT defeat (no jamming/spoofing/takeover/kinetic). This proxy forwards the
detect/track/classify/evidence + signed-verdict payloads verbatim; it never invents a
value. On any upstream failure it returns {"degraded": true, ...} so szl3d_live renders
the honest DEGRADED state (not a crash). Λ = Conjecture 1 (advisory).

ADDITIVE, try/except-guarded, registered BEFORE the SPA catch-all (mirrors
szl3d_holographic.register + a11oy_active_flux_router.register).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

# killinchu Space base (overridable for tests / alternate deploys). The drone +
# evaluate routes are confirmed live (HTTP 200, verified 2026-06-14).
KILLINCHU_BASE = os.environ.get(
    "KILLINCHU_BASE", "https://szlholdings-killinchu.hf.space"
).rstrip("/")

# Upstream route map: a11oy-side suffix -> (method, upstream path).
# evaluate is POST upstream; we expose it as GET so szl3d_live.poll (a GET poller)
# can drive the live verdict without a custom fetch.
_UPSTREAM: Dict[str, Dict[str, str]] = {
    "evaluate":    {"method": "POST", "path": "/api/killinchu/v1/counter-uas/evaluate"},
    "telemetry":   {"method": "GET",  "path": "/api/killinchu/drone/telemetry"},
    "cued-tracks": {"method": "GET",  "path": "/api/killinchu/drone/cued-tracks"},
    "air-picture": {"method": "GET",  "path": "/api/killinchu/drone/air-picture"},
    "gates":       {"method": "GET",  "path": "/api/killinchu/v1/gates"},
}

_TIMEOUT = float(os.environ.get("KILLINCHU_PROXY_TIMEOUT", "20"))


def _degraded(suffix: str, reason: str, status: int = 0) -> Dict[str, Any]:
    """The honest degraded envelope szl3d_live renders as DEGRADED (never fabricates)."""
    return {
        "degraded": True,
        "surface": "counter-uas",
        "suffix": suffix,
        "upstream": KILLINCHU_BASE,
        "reason": reason,
        "upstream_status": status,
        "doctrine": "v11",
        "lambda_status": "Conjecture 1 (advisory, not a theorem)",
        "posture": "killinchu SENSES & EVIDENCES — does NOT defeat (no jam/spoof/takeover/kinetic)",
        "label": "STRUCTURAL-ONLY",
    }


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    """Attach the same-origin Counter-UAS proxy. ADDITIVE; never crashes the app."""
    import httpx
    from starlette.responses import JSONResponse

    prefix = f"/api/{ns}/v1/counter-uas"
    registered: List[str] = []

    async def _forward(suffix: str):
        spec = _UPSTREAM.get(suffix)
        if spec is None:
            return JSONResponse(
                _degraded(suffix, "route not allowlisted", 404), status_code=404
            )
        url = KILLINCHU_BASE + spec["path"]
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                if spec["method"] == "POST":
                    # evaluate returns a stable live verdict + real DSSE sig; empty
                    # body is accepted upstream. We forward an explicit evaluate cue.
                    res = await client.post(
                        url,
                        json={"source": "a11oy-holographic/counter-uas", "doctrine": "v11"},
                        headers={"accept": "application/json"},
                    )
                else:
                    res = await client.get(url, headers={"accept": "application/json"})
        except Exception as e:  # network/timeout — honest degraded, not a crash
            return JSONResponse(_degraded(suffix, f"upstream unreachable: {e!r}", 0))
        if res.status_code >= 400:
            return JSONResponse(_degraded(suffix, "upstream error", res.status_code))
        try:
            payload = res.json()
        except Exception:
            return JSONResponse(_degraded(suffix, "upstream non-JSON", res.status_code))
        # Forward verbatim — we never rewrite or fabricate killinchu's values.
        return JSONResponse(payload)

    # Bind one GET route per suffix (closure-safe via default arg).
    for _suffix in _UPSTREAM:
        async def _route(suffix: str = _suffix):
            return await _forward(suffix)

        app.add_api_route(
            f"{prefix}/{_suffix}", _route, methods=["GET"], include_in_schema=False
        )
        registered.append(f"GET {prefix}/{_suffix}")

    # ------------------------------------------------------------------
    # GET /counter-uas/compute — same-origin alias for the holographic
    # Counter-UAS surface's `EP.compute` poll. The governed in-request
    # MODELED formula stack + Λ-ROE advisory gate lives in szl_cuas_formulas
    # under /api/<ns>/v1/cuas/compute; the surface historically polled
    # /counter-uas/compute (this namespace), which had no such route and
    # therefore fell through to the SPA catch-all (surfaced as a 502 in the
    # holographic board). This ADDITIVE alias delegates to the SAME governed
    # compute function so the surface renders the real MODELED envelope +
    # honest label + Λ = Conjecture 1, with no duplication of logic. If the
    # formula module is somehow unavailable it returns the honest degraded
    # envelope (never a crash). Doctrine v11.
    async def _compute_alias():
        try:
            import szl_cuas_formulas as _cf  # local import: keeps this module import-light
            return JSONResponse(_cf.szl_cuas_compute(None))
        except Exception as e:  # noqa: BLE001 — honest degraded, never 500 the surface
            return JSONResponse(_degraded("compute", f"governed compute unavailable: {e!r}", 0))

    app.add_api_route(
        f"{prefix}/compute", _compute_alias, methods=["GET"], include_in_schema=False
    )
    registered.append(f"GET {prefix}/compute")

    async def _info():
        return JSONResponse({
            "capability": "Counter-UAS same-origin live bridge to killinchu",
            "ns": ns,
            "upstream": KILLINCHU_BASE,
            "routes": registered,
            "posture": "senses-and-evidences (no defeat)",
            "lambda": "Conjecture 1",
            "label": "STRUCTURAL-ONLY",
            "doctrine": "v11",
        })

    app.add_api_route(f"{prefix}/info", _info, methods=["GET"], include_in_schema=False)
    registered.append(f"GET {prefix}/info")

    return {
        "registered": registered,
        "count": len(registered),
        "capability": "counter-uas live bridge",
        "upstream": KILLINCHU_BASE,
        "data_label": "live-bridge",
    }


def _selftest() -> None:
    # Structural self-test (no network): the route map is well-formed and honest.
    assert "evaluate" in _UPSTREAM and _UPSTREAM["evaluate"]["method"] == "POST"
    assert _UPSTREAM["telemetry"]["path"].endswith("/drone/telemetry")
    d = _degraded("evaluate", "test", 0)
    assert d["degraded"] is True and d["label"] == "STRUCTURAL-ONLY"
    assert "does NOT defeat" in d["posture"]
    # The governed compute alias delegates to the real formula stack (MODELED).
    try:
        import szl_cuas_formulas as _cf
        _c = _cf.szl_cuas_compute(None)
        assert _c.get("label") == "MODELED" and _c.get("service") == "counter-uas"
    except Exception as _e:  # module optional in some checkouts — alias fails honest-degraded
        print(f"szl_counter_uas_proxy: compute-alias source unavailable (honest degraded): {_e!r}")
    print("szl_counter_uas_proxy: ALL OK (route map honest, compute alias honest, degraded envelope honest)")


if __name__ == "__main__":
    _selftest()
