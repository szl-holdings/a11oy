# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""szl_compliance_mesh.py — a11oy MESH surface for the GAP-3 compliance crosswalk.

Exposes the doctrine-v11 -> NIST AI RMF / ISO 42001 / EU AI Act crosswalk (and its honest
coverage score) behind a11oy's governed route table. Matches the szl_pnt_mesh.py /
szl_pinn_bounds.py contract exactly: pure-stdlib request path, FastAPI `add_api_route` with
a Starlette `Route` fallback, try/except-guarded `register(app, ns)`.

Routes (all GET, read-only / deterministic):
  /api/<ns>/v1/compliance            full servable crosswalk artifact (controls + cells + coverage)
  /api/<ns>/v1/compliance/coverage   just the honest coverage report

HONESTY (Doctrine v11): the artifact is a SELF-ASSERTED advisory alignment, NOT a
certification. Coverage counts ONLY IMPLEMENTED cells. See compliance_crosswalk.py.
"""
import json
import os
import sys

try:
    from starlette.responses import JSONResponse
except Exception:  # pragma: no cover - bare-env shim for unit tests
    class JSONResponse:
        def __init__(self, content, status_code=200):
            self.body = content
            self.status_code = status_code

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import compliance_crosswalk as cc  # noqa: E402


def _h_compliance(request=None):
    return JSONResponse(cc.to_servable())


def _h_coverage(request=None):
    return JSONResponse(cc.coverage())


def register(app, ns="a11oy"):
    """Wire the compliance mesh onto the app under /api/<ns>/v1/compliance[/coverage].

    Additive. Uses FastAPI's add_api_route when available; falls back to a Starlette route
    append for a bare Starlette app.
    """
    base = f"/api/{ns}/v1/compliance"
    handlers = [
        (base, _h_compliance),
        (f"{base}/coverage", _h_coverage),
    ]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            from starlette.routing import Route
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


def write_servable_json(path=None) -> str:
    """Emit the static compliance.json the mesh can serve / the parent can commit."""
    path = path or os.path.join(_THIS_DIR, "compliance.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(cc.to_json())
    return path


if __name__ == "__main__":  # pragma: no cover
    p = write_servable_json()
    print(f"wrote {p}")
