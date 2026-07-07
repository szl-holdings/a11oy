"""routers/research_3d.py — research-3D read endpoints (moved verbatim from serve.py).

Wave-K Dev4 refactor-only extraction. Route group (all GET, read-only):
    GET /api/a11oy/v1/router/metrics        (+ /v1/router/metrics)
    GET /api/a11oy/v1/chaski/routing-graph  (+ /v1/chaski/routing-graph, /api/chaski/routing-graph)
    GET /api/a11oy/v1/reason/loop-depth     (+ /v1/reason/loop-depth)
    GET /api/a11oy/v1/consensus/votes       (+ /v1/consensus/votes)

These four handlers are thin JSON wrappers over the deterministic payload builders
`_r3d_router_metrics_payload` / `_r3d_routing_graph_payload` / `_r3d_loop_depth_payload`
/ `_r3d_consensus_votes_payload`, which REMAIN defined at serve.py module scope (they
are shared / referenced elsewhere). This module reaches them via `import serve`, which
is safe because register() is called from inside serve.py AFTER those helpers are
defined. Registered BEFORE the /api/a11oy/{path:path} Node proxy + SPA catch-all so
FastAPI ordered matching resolves them here (identical to the pre-refactor inline block).

REFACTOR-ONLY: paths, methods, and payloads are byte-identical to before.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
from __future__ import annotations

from fastapi.responses import JSONResponse


def register(app) -> dict:
    """Attach the research-3D read route group to `app`, identically to the prior
    inline serve.py block. Called BEFORE the Node proxy + SPA catch-all."""
    import serve  # shared deterministic payload builders live at serve module scope

    @app.get("/api/a11oy/v1/router/metrics")
    @app.get("/v1/router/metrics")
    async def _r3d_router_metrics() -> JSONResponse:
        return JSONResponse(serve._r3d_router_metrics_payload())

    @app.get("/api/a11oy/v1/chaski/routing-graph")
    @app.get("/v1/chaski/routing-graph")
    @app.get("/api/chaski/routing-graph")
    async def _r3d_routing_graph() -> JSONResponse:
        return JSONResponse(serve._r3d_routing_graph_payload())

    @app.get("/api/a11oy/v1/reason/loop-depth")
    @app.get("/v1/reason/loop-depth")
    async def _r3d_loop_depth() -> JSONResponse:
        return JSONResponse(serve._r3d_loop_depth_payload())

    @app.get("/api/a11oy/v1/consensus/votes")
    @app.get("/v1/consensus/votes")
    async def _r3d_consensus_votes() -> JSONResponse:
        return JSONResponse(serve._r3d_consensus_votes_payload())

    return {"ok": True, "ns": "a11oy", "group": "research-3d", "routes": [
        "/api/a11oy/v1/router/metrics", "/v1/router/metrics",
        "/api/a11oy/v1/chaski/routing-graph", "/v1/chaski/routing-graph", "/api/chaski/routing-graph",
        "/api/a11oy/v1/reason/loop-depth", "/v1/reason/loop-depth",
        "/api/a11oy/v1/consensus/votes", "/v1/consensus/votes",
    ]}
