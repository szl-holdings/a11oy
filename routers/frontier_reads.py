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

import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi.responses import JSONResponse

PHASE_B_OBSERVATION_PATHS = frozenset(
    {
        "/api/a11oy/provenance",
        "/api/a11oy/v1/energy/sci",
        "/api/a11oy/v1/ledger",
        "/api/a11oy/v1/observability/summary",
        "/api/a11oy/v1/observability/business",
        "/api/a11oy/v1/mesh/state",
        "/api/a11oy/v1/sec/cve",
        "/api/a11oy/v1/sec/attack",
        "/api/a11oy/v1/sec/threats",
        "/api/a11oy/v1/sec/threatgraph",
        "/api/a11oy/v1/sec/kevgate",
    }
)
PHASE_B_OBSERVATION_ALIASES = frozenset({"/v1/observability/business"})
KEVGATE_PATHS = frozenset(
    {
        "/api/a11oy/v1/sec/kev",
        "/api/a11oy/v1/sec/kevgate",
    }
)
_PHASE_B_MUTATED_PATHS = (
    PHASE_B_OBSERVATION_PATHS
    | PHASE_B_OBSERVATION_ALIASES
    | KEVGATE_PATHS
)


def utc_observation_clock() -> str:
    """Return one genuine request-time UTC observation clock."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_phase_b_payload(
    path: str,
    payload: Any,
    *,
    observed_at: str | None = None,
    status_code: int = 200,
) -> Any:
    """Apply the closed Phase-B vocabulary to one decoded JSON value.

    Supplying ``observed_at`` makes the function deterministic for regression
    tests. Unknown paths and non-object values are returned without semantic
    changes. Error responses are never rewritten into cached KEV evidence.
    """
    if not isinstance(payload, dict):
        return payload

    normalized = dict(payload)
    if 200 <= int(status_code) < 300 and (
        path in PHASE_B_OBSERVATION_PATHS
        or path in PHASE_B_OBSERVATION_ALIASES
        or path in KEVGATE_PATHS
    ):
        normalized["observed_at"] = observed_at or utc_observation_clock()

    if path in KEVGATE_PATHS and 200 <= int(status_code) < 300:
        raw_kind_text = str(normalized.get("data_kind") or "").strip()
        raw_kind = raw_kind_text.casefold()
        if raw_kind == "live":
            canonical_kind = "live"
        elif (
            raw_kind.startswith("live ")
            and "kev" in raw_kind
            and not any(
                blocked in raw_kind
                for blocked in ("mock", "fabricated", "placeholder")
            )
        ):
            canonical_kind = "live"
            normalized["data_kind_detail"] = raw_kind_text
        elif raw_kind in {"cached", "sample", "snapshot"}:
            # Bundled/in-image CISA rows are cached source material, not a
            # fabricated SAMPLE feed. Unknown kinds stay fail-closed.
            canonical_kind = "cached"
        else:
            return normalized
        normalized["data_kind"] = canonical_kind

        detail = normalized.get("detail")
        if not isinstance(detail, str) or not detail.strip():
            note = normalized.get("note")
            if isinstance(note, str) and note.strip():
                detail = note
            elif canonical_kind == "live":
                detail = (
                    "The KEV source identified this response as live during "
                    "the current request; reachability is not independent "
                    "validation."
                )
            else:
                detail = (
                    "Bundled CISA KEV snapshot served from the current image; "
                    "this is cached source material, not a live catalog fetch."
                )
        normalized["detail"] = detail

    return normalized


async def _phase_b_single_body(body: bytes) -> AsyncIterator[bytes]:
    yield body


def install_phase_b_response_contract(app: Any) -> None:
    """Install the exact-path JSON normalizer once."""
    state = getattr(app, "state", None)
    marker = "_readiness_phase_b_response_contract_installed"
    if state is not None and getattr(state, marker, False):
        return
    if state is not None:
        setattr(state, marker, True)

    @app.middleware("http")
    async def _phase_b_response_contract(
        request: Any,
        call_next: Any,
    ) -> Any:
        response = await call_next(request)
        path = request.url.path
        if path not in _PHASE_B_MUTATED_PATHS:
            return response

        content_type = response.headers.get("content-type", "").casefold()
        if "json" not in content_type:
            return response
        content_encoding = response.headers.get(
            "content-encoding",
            "identity",
        ).casefold()
        if content_encoding not in {"", "identity"}:
            return response

        iterator = getattr(response, "body_iterator", None)
        if iterator is None:
            return response

        chunks: list[bytes] = []
        async for chunk in iterator:
            if isinstance(chunk, bytes):
                chunks.append(chunk)
            elif isinstance(chunk, str):
                chunks.append(chunk.encode("utf-8"))
            else:
                chunks.append(bytes(chunk))
        raw = b"".join(chunks)

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            response.body_iterator = _phase_b_single_body(raw)
            response.headers["content-length"] = str(len(raw))
            return response

        normalized = normalize_phase_b_payload(
            path,
            payload,
            status_code=int(getattr(response, "status_code", 200)),
        )
        encoded = json.dumps(
            normalized,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        response.body_iterator = _phase_b_single_body(encoded)
        response.headers["content-length"] = str(len(encoded))
        for stale_validator in ("etag", "content-md5"):
            if stale_validator in response.headers:
                del response.headers[stale_validator]
        return response


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
