"""Wave-R Dev 2 — operational STATUS aggregate contract guard.

Boots the REAL app in-process (Starlette/FastAPI TestClient, no mocks, no
network) and asserts the honest, drift-proof invariants of the operational-
dashboard back-end GET /api/a11oy/v1/status:

  1. It is registered and answers 200 (never a 500), BEFORE the SPA / Node-proxy
     catch-alls (so it does not silently fall through to an HTML 200).
  2. It enumerates the app's OWN surface registry and every surface carries an
     honest data label (verbatim from that surface's backend) + an honest health
     token; the per-subsystem and estate counts are internally consistent.
  3. DRIFT-PROOF: it is built on the Wave-Q frontier index — the surface ids +
     their verbatim data labels MUST match szl_frontier_index.build_catalog
     exactly (proving it reuses the registry rather than a hand-maintained list).
  4. Doctrine: locked-8 exact, adds nothing, Λ = Conjecture 1, trust 0.97 (never
     100%), and the estate rollup is NEVER a fabricated all-green.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
import pytest

pytest.importorskip("starlette.testclient")
from fastapi.testclient import TestClient  # noqa: E402

import serve  # noqa: E402
import szl_frontier_index as fi  # noqa: E402

STATUS = "/api/a11oy/v1/status"
HEALTH = "/api/a11oy/v1/status/health"
HEALTH_TOKENS = {"LIVE", "DEGRADED", "UNAVAILABLE", "FRONTEND"}
VOCAB = set(fi.HONEST_LABELS)


def _route_index(path):
    for i, r in enumerate(serve.app.router.routes):
        if getattr(r, "path", None) == path:
            return i
    return None


def test_status_routes_registered_before_catchalls():
    si = _route_index(STATUS)
    assert si is not None, f"{STATUS} not registered"
    assert _route_index(HEALTH) is not None, f"{HEALTH} not registered"
    spa = _route_index("/{full_path:path}")
    proxy = _route_index("/api/a11oy/{path:path}")
    if spa is not None:
        assert si < spa, f"{STATUS} ({si}) must precede the SPA catch-all ({spa})"
    if proxy is not None:
        assert si < proxy, f"{STATUS} ({si}) must precede the Node proxy ({proxy})"


def test_status_answers_200_and_is_internally_consistent():
    with TestClient(serve.app) as c:
        r = c.get(STATUS)
    assert r.status_code == 200, f"{STATUS} -> {r.status_code} (must never 500)"
    j = r.json()
    assert j["ok"] is True and j["label"] == "MODELED"
    surfaces = j["surfaces"]
    assert len(surfaces) >= 50, f"expected the full registry, got {len(surfaces)}"
    for e in surfaces:
        assert e["health"] in HEALTH_TOKENS, f"{e['id']}: bad health {e['health']}"
        assert e["data_label"] in VOCAB, f"{e['id']}: non-vocab label {e['data_label']}"
    est = j["estate"]
    assert est["surfaces"] == len(surfaces)
    assert sum(est["counts"].values()) == len(surfaces)
    assert sum(s["surfaces"] for s in j["subsystems"]) == len(surfaces)


def test_status_is_driftproof_against_frontier_index():
    """Surface ids + verbatim data labels MUST match the frontier index catalog."""
    with TestClient(serve.app) as c:
        j = c.get(STATUS).json()
    cat = fi.build_catalog(serve.app, "a11oy")
    cat_by_id = {c["id"]: c["label"] for c in cat["surfaces"]}
    status_by_id = {e["id"]: e["data_label"] for e in j["surfaces"]}
    assert set(status_by_id) == set(cat_by_id), "status/catalog surface-id set drifted"
    for sid, label in status_by_id.items():
        assert label == cat_by_id[sid], (
            f"{sid}: status label {label} != catalog {cat_by_id[sid]} (drift/upgrade)"
        )


def test_status_doctrine_and_no_fabricated_green():
    with TestClient(serve.app) as c:
        j = c.get(STATUS).json()
    d = j["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    est = j["estate"]
    # Honest rollup: LIVE only when zero degraded/unavailable backends.
    if est["counts"]["DEGRADED"] > 0 or est["counts"]["UNAVAILABLE"] > 0:
        assert est["health"] in ("DEGRADED", "UNAVAILABLE")


def test_status_health_tile_ok():
    with TestClient(serve.app) as c:
        r = c.get(HEALTH)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True and j["label"] == "MODELED"
    assert j["doctrine"]["lambda"] == "Conjecture 1"
