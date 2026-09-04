#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Unify flock ledger. Additive. register(app) serves GET /unify.

Already-imported sister module szl_lyte_lattice should call into this
or copy these routes. pause+private, never delete. Not a Hub Space.
"""
from __future__ import annotations
import hashlib, json, time
from typing import Any, Dict, List

_BIND = "BIND_AS_A11OY_PACKAGE"
KEEP = [
    {"slug": "a11oy", "dest": "https://a-11-oy.com/console"},
    {"slug": "killinchu", "dest": "https://szlholdings-killinchu.hf.space/elite"},
    {"slug": "immune", "dest": "https://a-11-oy.com/immune"},
    {"slug": "lyte", "dest": "https://a-11-oy.com/lyte"},
    {"slug": "vertical-services", "dest": "https://a-11-oy.com/spaces"},
]
FOLD = [
    {"slug": "immune-lattice", "into": "immune"},
    {"slug": "counsel", "into": "ayllu"},
    {"slug": "ayllu", "into": "https://a11oy.net/ayllu/"},
    {"slug": "sentra", "into": "vertical-services"},
    {"slug": "finance", "into": "vertical-services"},
    {"slug": "terra", "into": "vertical-services"},
    {"slug": "david-leads", "into": "https://a-11-oy.com"},
]
UNIFY = [
    {"slug": "szl-command-lab", "into": "a11oy"},
    {"slug": "szl-model-inference-lab", "into": "a11oy"},
    {"slug": "szl-frontier", "into": "a11oy"},
    {"slug": "szl-constellation", "into": "a11oy"},
]

def status() -> Dict[str, Any]:
    p = {
        "ok": True, "service": "unify-flock", "state": "BIND", "bind": _BIND,
        "certified": False, "proven_trust": False, "hub_write": False,
        "keep": KEEP, "fold": FOLD, "unify_stragglers": UNIFY,
        "policy": "pause+private, never delete",
        "lambda": "Conjecture 1",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    p["digest"] = hashlib.sha256(json.dumps(p, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    p["signer"] = "UNSIGNED-honest"
    return p

def page() -> str:
    s = status()
    def rows(items, act, key):
        return "".join(f"<tr><td>{r['slug']}</td><td>{act}</td><td>{r[key]}</td></tr>" for r in items)
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'/><title>Unify flock</title>"
        "<style>body{margin:0;background:#0a0a0a;color:#f5f5f5;font-family:sans-serif}"
        "a{color:#5fb3a3}.wrap{max-width:960px;margin:0 auto;padding:1.4rem}"
        "table{width:100%;border-collapse:collapse;font-family:monospace;font-size:12px}"
        "td,th{padding:.35rem;border-bottom:1px solid #333;text-align:left;color:#9a9a9a}</style></head>"
        f"<body><div class='wrap'><p>BIND · digest {s['digest'][:16]}</p><h1>Unify flock</h1>"
        "<p>Product tab on a-11-oy.com. Not a Hub Space. pause+private, never delete.</p>"
        "<p><a href='/lyte'>/lyte</a> · <a href='/spaces'>/spaces</a></p>"
        "<h2>KEEP</h2><table>" + rows(KEEP,'KEEP','dest') + "</table>"
        "<h2>FOLD</h2><table>" + rows(FOLD,'FOLD','into') + "</table>"
        "<h2>UNIFY</h2><table>" + rows(UNIFY,'UNIFY','into') + "</table></div></body></html>"
    )

def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    from fastapi.responses import HTMLResponse, JSONResponse
    routes: List[str] = []
    try:
        from starlette.routing import Route
        def _api(_r=None): return JSONResponse(status())
        def _page(_r=None): return HTMLResponse(page())
        app.router.routes.insert(0, Route(f"/api/{ns}/v1/unify/status", _api, methods=["GET"]))
        app.router.routes.insert(0, Route("/unify", _page, methods=["GET", "HEAD"]))
        app.router.routes.insert(0, Route(f"/{ns}/unify", _page, methods=["GET", "HEAD"]))
        routes = [f"/api/{ns}/v1/unify/status", "/unify", f"/{ns}/unify"]
    except Exception:
        app.add_api_route(f"/api/{ns}/v1/unify/status", lambda: JSONResponse(status()), methods=["GET"])
        app.add_api_route("/unify", lambda: HTMLResponse(page()), methods=["GET", "HEAD"])
        routes = [f"/api/{ns}/v1/unify/status", "/unify"]
    print(f"[{ns}] szl_unify_flock registered {routes}", flush=True)
    return {"ok": True, "certified": False, "routes": routes}

if __name__ == "__main__":
    print(json.dumps(status(), indent=2))
