"""routers/frontier_reads.py — frontier read endpoints (moved verbatim from serve.py).

Wave-K Dev4 refactor-only extraction. Route group (all GET, read-only):
    GET /api/a11oy/v1/forecast-baseline      (+ /v1/forecast-baseline)
    GET /api/a11oy/v1/vertical-packs         (+ /v1/vertical-packs)
    GET /api/a11oy/v1/observability/business (+ /v1/observability/business)

Shared serve.py module-scope state referenced (unchanged, via `import serve`):
    serve._A11OY_FORECAST      — forecast-baseline payload
    serve._a11oy_build_chain   — receipt-chain builder
    serve._A11OY_CAPS          — capability list (for the observability count)

`_A11OY_VERTICALS` was defined inline in the moved block and is genuinely local to
this group, so it moves here with the routes. Registered BEFORE the /api/a11oy/
{path:path} Node proxy + SPA catch-all, identical to the pre-refactor inline block.

The additive Series-A controller is registered at this same pre-catch-all seam. It
keeps GET/HEAD read-only, uses explicit POSTs for refresh/evaluate/execute, and
fails one surface closed without taking down the existing frontier reads. Frontier
Now is a read-only projection over that controller: no second store, signer,
credential, scheduler, passport authority, or effector.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
from __future__ import annotations

from fastapi.responses import JSONResponse

from routers.readiness_phase_b import install_phase_b_response_contract

# ---- Vertical-pack registry (GAP-5): 13 verticals, live/stub. "Cyber Resilience"
# label avoids the literal forbidden string. NO amaru/sentra/rosie. ----
_A11OY_VERTICALS = [
    {"id": "platform", "title": "Platform / AgentOps", "purpose": "Release Gate Intelligence", "status": "live", "owner": "eng-vp@szl"},
    {"id": "pulse", "title": "Pulse", "purpose": "Founder Operating Channel", "status": "live", "owner": "ceo@szl"},
    {"id": "finance", "title": "Finance / Capital Weather", "purpose": "Capital Weather", "status": "live", "owner": "cfo@szl"},
    {"id": "decision_ledger", "title": "Decision Debt Ledger", "purpose": "Decision Debt Ledger", "status": "live", "owner": "cpo@szl"},
    {"id": "terra", "title": "Acquisition Time Machine", "purpose": "Acquisition Time Machine", "status": "live", "owner": "ceo@szl"},
    {"id": "voyage", "title": "Voyage Risk Exchange", "purpose": "Voyage Risk Exchange", "status": "live", "owner": "coo@szl"},
    {"id": "counsel", "title": "Matter Flight Recorder", "purpose": "Matter Flight Recorder", "status": "live", "owner": "general-counsel@szl"},
    {"id": "growth", "title": "Marketing / Growth", "purpose": "Proof-To-Pipeline Engine", "status": "live", "owner": "cmo@szl"},
    {"id": "cyber", "title": "Cyber Resilience", "purpose": "Cyber Resilience Command", "status": "live", "owner": "ciso@szl"},
    {"id": "firestorm", "title": "Firestorm Ops", "purpose": "Crisis Operations Command", "status": "stub", "owner": "coo@szl"},
    {"id": "nuroforge", "title": "NuroForge", "purpose": "AI Agent Forge", "status": "stub", "owner": "cto@szl"},
    {"id": "infra", "title": "Meridian Infra", "purpose": "Infrastructure Intelligence", "status": "stub", "owner": "eng-vp@szl"},
    {"id": "graph", "title": "Constellation Graph", "purpose": "Cross-Domain Intelligence Graph", "status": "stub", "owner": "cto@szl"},
]


def register(app) -> dict:
    """Attach frontier reads and the additive Series-A control plane."""
    install_phase_b_response_contract(app)

    import serve  # shared module-scope state lives at serve module scope

    @app.get("/api/a11oy/v1/forecast-baseline")
    @app.get("/v1/forecast-baseline")
    async def a11oy_forecast_baseline_v2() -> JSONResponse:
        return JSONResponse(serve._A11OY_FORECAST)

    @app.get("/api/a11oy/v1/vertical-packs")
    @app.get("/v1/vertical-packs")
    async def a11oy_vertical_packs_v2() -> JSONResponse:
        live = sum(1 for v in _A11OY_VERTICALS if v["status"] == "live")
        return JSONResponse({"total": len(_A11OY_VERTICALS), "live": live,
                             "stub": len(_A11OY_VERTICALS) - live,
                             "verticals": _A11OY_VERTICALS,
                             "honesty": "Live = shipping pack; stub = scaffolded, roadmap."})

    @app.get("/api/a11oy/v1/observability/business")
    @app.get("/v1/observability/business")
    async def a11oy_business_observability_v2() -> JSONResponse:
        ch = serve._a11oy_build_chain(24)
        domains = [
            {"id": "coverage", "name": "Coverage",
             "measure": "knowledge ontology + vertical policies",
             "value": "10 policies · axioms→theorems→formulas graph", "status": "real"},
            {"id": "connectivity", "name": "Connectivity",
             "measure": "in-image capability mesh + MCP tools",
             "value": "%d capabilities · 4 MCP tools" % len(serve._A11OY_CAPS), "status": "real"},
            {"id": "cognitive", "name": "Cognitive",
             "measure": "reasoning + orchestration + Λ scoring",
             "value": "13-axis trust vector · Λ=0.919 (Conjecture 1)", "status": "real"},
            {"id": "executive", "name": "Executive Interfaces",
             "measure": "operator tabs + Ask & Act",
             "value": "command tabs + grounded operator", "status": "real"},
            {"id": "impact", "name": "Impact",
             "measure": "signed decision receipts (hash-chained)",
             "value": "%d signed spans · chain verified" % ch["depth"], "status": "real"},
        ]
        return JSONResponse({
            "domains": domains,
            "honesty": ("Capability domains on real in-image data. We do NOT reproduce "
                        "any third-party marketing percentages as our own."),
            "lambda_status": "Conjecture 1 (advisory)",
        })

    try:
        from routers import series_a_control_plane as _series_a_control_plane

        series_a = _series_a_control_plane.register(app, ns="a11oy")
    except Exception as exc:  # one additive surface must never take down A11oy
        series_a = {
            "ok": False,
            "state": "UNAVAILABLE",
            "reason": type(exc).__name__,
            "effectors": [],
        }

    try:
        from routers import frontier_now_control_plane as _frontier_now

        frontier_now = _frontier_now.register(app, ns="a11oy")
    except Exception as exc:  # one read projection must never take down A11oy
        frontier_now = {
            "ok": False,
            "state": "UNAVAILABLE",
            "reason": type(exc).__name__,
            "effectors": [],
        }

    return {
        "ok": True,
        "ns": "a11oy",
        "group": "frontier-reads",
        "series_a": series_a,
        "frontier_now": frontier_now,
        "routes": [
            "/api/a11oy/v1/forecast-baseline", "/v1/forecast-baseline",
            "/api/a11oy/v1/vertical-packs", "/v1/vertical-packs",
            "/api/a11oy/v1/observability/business", "/v1/observability/business",
            "/series-a", "/api/a11oy/v1/series-a/status",
            "/frontier-now", "/now",
            "/api/a11oy/v1/frontier-now/summary",
            "/api/a11oy/v1/frontier-now/inventory",
        ],
    }
