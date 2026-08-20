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
SUMMARY = "/api/a11oy/v1/status/summary"
HEALTH = "/api/a11oy/v1/status/health"
HEALTH_TOKENS = {"LIVE", "DEGRADED", "UNAVAILABLE", "FRONTEND"}
ESTATE_TOKENS = {"LIVE", "DEGRADED", "UNAVAILABLE"}
_RANK = {"UNAVAILABLE": 0, "DEGRADED": 1, "LIVE": 2}
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
    assert _route_index(SUMMARY) is not None, f"{SUMMARY} not registered"
    spa = _route_index("/{full_path:path}")
    proxy = _route_index("/api/a11oy/{path:path}")
    for path in (STATUS, SUMMARY, HEALTH):
        idx = _route_index(path)
        if spa is not None:
            assert idx < spa, f"{path} ({idx}) must precede the SPA catch-all ({spa})"
        if proxy is not None:
            assert idx < proxy, f"{path} ({idx}) must precede the Node proxy ({proxy})"


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


def test_status_preflight_and_worst_wins_headline():
    """Boot-preflight readiness is folded into the estate; the headline is
    worst-wins across live surface health AND preflight (never fabricated green)."""
    with TestClient(serve.app) as c:
        j = c.get(STATUS).json()
    pf = j["preflight"]
    assert pf["overall"] in HEALTH_TOKENS, f"preflight overall not honest: {pf['overall']}"
    # readiness is a health token, not a doctrine disclosure label — must not use a
    # reserved honesty-label key (the frontier-endpoint contract vocab-checks those).
    assert "label" not in pf, "preflight must not carry a reserved honesty-label key"
    assert isinstance(pf.get("subsystems"), list)
    est = j["estate"]
    headline = est["headline"]
    assert headline in ESTATE_TOKENS, f"bad headline {headline}"
    # Headline can never be healthier than either the estate health or preflight.
    assert _RANK[headline] <= _RANK.get(est["health"], 0)
    assert _RANK[headline] <= _RANK.get(pf["overall"], 1)


def test_status_history_sparkline_is_honest_sample():
    """The history sparkline is an in-memory ring buffer of REAL observed probes,
    labelled SAMPLE, bounded, and never fabricated. Each GET appends one probe."""
    with TestClient(serve.app) as c:
        j1 = c.get(STATUS).json()
        h1 = j1["history"]
        assert h1["label"] == "SAMPLE", h1
        cap = h1["capacity"]
        assert h1["observed"] == len(h1["sparkline"]) == len(h1["samples"])
        assert 1 <= h1["observed"] <= cap, "ring buffer must be bounded and non-empty after a probe"
        for tok in h1["sparkline"]:
            assert tok in ESTATE_TOKENS, f"non-honest sparkline token {tok}"
        before = h1["observed"]
        h2 = c.get(STATUS).json()["history"]
        assert h2["observed"] == min(before + 1, cap), "each probe appends exactly one observation"


def test_status_summary_compact_agrees_with_full():
    with TestClient(serve.app) as c:
        r = c.get(SUMMARY)
        assert r.status_code == 200, f"{SUMMARY} -> {r.status_code} (must never 500)"
        sm = r.json()
        full = c.get(STATUS).json()
    assert sm["ok"] is True and sm["label"] == "MODELED"
    assert sm["endpoint"] == "status/summary"
    assert sm["headline"] in ESTATE_TOKENS
    assert sm["estate_health"] in ESTATE_TOKENS
    assert sm["preflight"] in HEALTH_TOKENS
    assert sm["history"]["label"] == "SAMPLE"
    assert isinstance(sm["history"]["sparkline"], list)
    # Compact payload must not disagree with the full aggregate it derives from.
    assert sm["estate_health"] == full["estate"]["health"]
    assert sm["surfaces"] == full["estate"]["surfaces"]
    d = sm["doctrine"]
    assert d["locked_proven"] == 8 and d["lambda"] == "Conjecture 1"
    assert d["trust_ceiling"] == 0.97 and d["runtime_cdn"] == 0
