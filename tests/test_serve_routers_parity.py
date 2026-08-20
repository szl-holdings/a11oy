"""Wave-K Dev4 — serve.py router-split parity guard (refactor-only regression net).

The first bounded slice of the serve.py decomposition moved three cohesive route
groups OUT of serve.py into the routers/ package:

    routers/lambda_bounty.py   — /api/lambda-bounty/{healthz,submit,receipts}
    routers/research_3d.py     — router/metrics, chaski/routing-graph,
                                 reason/loop-depth, consensus/votes
    routers/frontier_reads.py  — forecast-baseline, vertical-packs,
                                 observability/business

Each is imported + register(app)'d from serve.py (guarded try/except) at the SAME
position it used to occupy — BEFORE the SPA /{full_path:path} catch-all. This test
locks the invariants that make the move behavior-preserving:

  1. Every moved path still resolves (no 404 / no dead surface).
  2. Every moved path is handled by its NEW routers.* module (proving it moved,
     not just that a same-named route exists).
  3. Every moved path is ordered BEFORE the SPA catch-all (so it wins matching).
  4. The moved GET endpoints return their expected honest status codes.
  5. The lambda-bounty POST intake still accepts a good payload (200) and rejects
     a bad one (422) exactly as before.

Pure in-process TestClient, no network. Stdlib + fastapi only.
Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
import importlib

import pytest
from fastapi.testclient import TestClient

serve = importlib.import_module("serve")

MOVED = {
    # path : (expected handler module prefix)
    "/api/lambda-bounty/healthz": "routers.lambda_bounty",
    "/api/lambda-bounty/submit": "routers.lambda_bounty",
    "/api/lambda-bounty/receipts": "routers.lambda_bounty",
    "/api/a11oy/v1/router/metrics": "routers.research_3d",
    "/v1/router/metrics": "routers.research_3d",
    "/api/a11oy/v1/chaski/routing-graph": "routers.research_3d",
    "/v1/chaski/routing-graph": "routers.research_3d",
    "/api/chaski/routing-graph": "routers.research_3d",
    "/api/a11oy/v1/reason/loop-depth": "routers.research_3d",
    "/v1/reason/loop-depth": "routers.research_3d",
    "/api/a11oy/v1/consensus/votes": "routers.research_3d",
    "/v1/consensus/votes": "routers.research_3d",
    "/api/a11oy/v1/forecast-baseline": "routers.frontier_reads",
    "/v1/forecast-baseline": "routers.frontier_reads",
    "/api/a11oy/v1/vertical-packs": "routers.frontier_reads",
    "/v1/vertical-packs": "routers.frontier_reads",
    "/api/a11oy/v1/observability/business": "routers.frontier_reads",
    "/v1/observability/business": "routers.frontier_reads",
}

GET_PATHS = [p for p in MOVED if p != "/api/lambda-bounty/submit"]


def _route_index(path):
    for i, r in enumerate(serve.app.router.routes):
        if getattr(r, "path", None) == path:
            return i, r
    return None, None


def _catchall_index():
    for i, r in enumerate(serve.app.router.routes):
        if getattr(r, "path", None) == "/{full_path:path}":
            return i
    return None


def test_moved_routes_exist_and_come_from_router_modules():
    for path, mod_prefix in MOVED.items():
        idx, r = _route_index(path)
        assert idx is not None, f"moved route vanished: {path}"
        ep = getattr(r, "endpoint", None)
        qual = f"{getattr(ep, '__module__', '?')}"
        assert qual.startswith(mod_prefix), (
            f"{path} handler is {qual}, expected to live in {mod_prefix} "
            f"(route did not actually move out of serve.py)"
        )


def test_moved_routes_are_before_spa_catchall():
    ci = _catchall_index()
    assert ci is not None, "SPA /{full_path:path} catch-all not found"
    for path in MOVED:
        idx, _ = _route_index(path)
        assert idx < ci, f"{path} at idx {idx} is NOT before the SPA catch-all at {ci}"


# /api/lambda-bounty/receipts returns NDJSON (PlainTextResponse), not a JSON body;
# it has its own dedicated content-type assertion below.
JSON_GET_PATHS = [p for p in GET_PATHS if p != "/api/lambda-bounty/receipts"]


@pytest.mark.parametrize("path", JSON_GET_PATHS)
def test_moved_get_endpoints_ok(path):
    with TestClient(serve.app) as c:
        r = c.get(path)
    assert r.status_code == 200, f"{path} -> {r.status_code} (expected 200)"
    r.json()  # must be parseable JSON


def test_lambda_bounty_receipts_is_ndjson():
    with TestClient(serve.app) as c:
        r = c.get("/api/lambda-bounty/receipts")
    assert r.status_code == 200
    assert "ndjson" in r.headers.get("content-type", "")


def test_lambda_bounty_submit_accept_and_reject():
    good = {
        "submitter": {"name": "parity-tester"},
        "pr_url": "https://github.com/szl-holdings/lambda-bounty/pull/1",
        "lean_toolchain": "leanprover/lean4:v4.13.0",
        "axiom_print": "propext, Classical.choice",
        "sorry_free_claim": True,
    }
    with TestClient(serve.app) as c:
        ok = c.post("/api/lambda-bounty/submit", json=good)
        bad = c.post("/api/lambda-bounty/submit", json={"foo": "bar"})
    assert ok.status_code == 200, f"good intake -> {ok.status_code}"
    assert ok.json()["accepted_intake"] is True
    assert bad.status_code == 422, f"bad intake -> {bad.status_code}"
    assert bad.json()["accepted_intake"] is False
    assert bad.json()["errors"], "rejected intake must list errors"
