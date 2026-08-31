"""feat/frontier-brainground — Brainground grounding-confidence + honest-abstention guard.

Brainground scores the brain's REAL grounding_subgraph for a query and returns an honest
verdict — GROUNDED / WEAK-GROUNDING / INSUFFICIENT-GROUNDING — so the brain can truthfully
abstain when it lacks grounding. These tests pin the honest-by-construction invariants:

  1. grounding_confidence is always in [0,1] and each of the four components is computed.
  2. Honest abstention FIRES on empty / weak grounding (INSUFFICIENT-GROUNDING, should_abstain).
  3. A strong grounding reads GROUNDED.
  4. Routes (GET info/ground, POST receipt) answer 200 (never 500), BEFORE the SPA catch-all.
  5. RECEIPT-ON-WRITE-NOT-ON-READ: GET mints NOTHING; POST receipt emits ONE UNSIGNED,
     deterministic SHA-256 content digest.
  6. Honest labels are the brain's OWN vocabulary, VERBATIM, never upgraded.
  7. Doctrine: locked-8 exact, adds nothing, Λ = Conjecture 1, trust 0.97 (never 100%).

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
import pytest

import szl_brainground as bg  # noqa: E402

VERDICTS = {bg.VERDICT_GROUNDED, bg.VERDICT_WEAK, bg.VERDICT_INSUFFICIENT}


def _strong_ask():
    """A synthetic-but-honest ask() result whose grounding is strong on every component."""
    nodes = [{"id": f"n{i}", "title": "brain graph knowledge node",
              "ppr": 0.5 if i == 0 else 0.05, "salience": 0.1, "community": "c1"}
             for i in range(6)]
    return {
        "query": "brain graph knowledge",
        "seeds": [{"id": "n0", "title": "brain graph knowledge node"}],
        "grounding_subgraph": {"node_count": 6, "link_count": 13, "nodes": nodes},
        "community_context": [{"id": "c1"}],
    }


def _empty_ask():
    return {"query": "zxqw nonsense termz", "seeds": [],
            "grounding_subgraph": {"node_count": 0, "link_count": 0, "nodes": []}}


# --------------------------------------------------------------------------- #
# 1. confidence in [0,1] + every component computed
# --------------------------------------------------------------------------- #
def test_confidence_in_unit_interval_and_all_components_present():
    r = bg.compute_confidence(_strong_ask())
    assert 0.0 <= r["grounding_confidence"] <= 1.0
    for name in ("seed_coverage", "subgraph_cohesion", "salience_mass", "community_consistency"):
        assert name in r["components"], f"component missing: {name}"
        v = r["components"][name]["value"]
        assert 0.0 <= v <= 1.0, f"{name} out of [0,1]: {v}"
    # weights are published and sum to 1.0 (deterministic combination, no request-time tuning).
    assert abs(sum(bg.WEIGHTS.values()) - 1.0) < 1e-9


def test_confidence_is_the_published_weighted_sum():
    r = bg.compute_confidence(_strong_ask())
    recomputed = sum(bg.WEIGHTS[k] * r["components"][k]["value"] for k in bg.WEIGHTS)
    assert abs(r["grounding_confidence"] - min(1.0, max(0.0, recomputed))) < 1e-6


# --------------------------------------------------------------------------- #
# 2. honest abstention fires on empty / weak grounding
# --------------------------------------------------------------------------- #
def test_abstention_fires_on_empty_grounding():
    r = bg.compute_confidence(_empty_ask())
    assert r["grounding_confidence"] == 0.0
    assert r["verdict"] == bg.VERDICT_INSUFFICIENT
    assert r["should_abstain"] is True


def test_abstention_fires_on_too_few_nodes_even_if_components_ok():
    """Fewer than MIN_GROUNDING_NODES grounding nodes -> abstain regardless of the score."""
    nodes = [{"id": "n0", "title": "brain graph knowledge", "ppr": 1.0, "community": "c1"}]
    r = bg.compute_confidence({
        "query": "brain graph knowledge",
        "seeds": [{"id": "n0", "title": "brain graph knowledge"}],
        "grounding_subgraph": {"node_count": 1, "link_count": 0, "nodes": nodes},
    })
    assert r["grounding_stats"]["node_count"] < bg.MIN_GROUNDING_NODES
    assert r["verdict"] == bg.VERDICT_INSUFFICIENT and r["should_abstain"] is True


# --------------------------------------------------------------------------- #
# 3. strong grounding -> GROUNDED
# --------------------------------------------------------------------------- #
def test_strong_grounding_is_grounded():
    r = bg.compute_confidence(_strong_ask())
    assert r["verdict"] == bg.VERDICT_GROUNDED
    assert r["should_abstain"] is False
    assert r["grounding_confidence"] >= bg.GROUNDED_THRESHOLD


# --------------------------------------------------------------------------- #
# 4/5. routes + receipt-on-write-not-on-read (against the REAL booted estate)
# --------------------------------------------------------------------------- #
INFO = "/api/a11oy/v1/brain/ground/info"
GROUND = "/api/a11oy/v1/brain/ground"
RECEIPT = "/api/a11oy/v1/brain/ground/receipt"


def _client():
    pytest.importorskip("starlette.testclient")
    from fastapi.testclient import TestClient
    import serve
    return TestClient(serve.app), serve


def _route_index(serve, path):
    for i, r in enumerate(serve.app.router.routes):
        if getattr(r, "path", None) == path:
            return i
    return None


def test_routes_registered_before_catchalls():
    _c, serve = _client()
    for path in (INFO, GROUND, RECEIPT):
        assert _route_index(serve, path) is not None, f"{path} not registered"
    spa = _route_index(serve, "/{full_path:path}")
    proxy = _route_index(serve, "/api/a11oy/{path:path}")
    for path in (INFO, GROUND, RECEIPT):
        idx = _route_index(serve, path)
        if spa is not None:
            assert idx < spa, f"{path} ({idx}) must precede the SPA catch-all ({spa})"
        if proxy is not None:
            assert idx < proxy, f"{path} ({idx}) must precede the Node proxy ({proxy})"


def test_get_info_is_static_pure_read():
    c, _ = _client()
    with c:
        r = c.get(INFO)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True and j["label"] == "MODELED"
    assert "receipt" not in j, "GET info is a PURE READ — must mint NO receipt"
    assert set(j["verdicts"]) == VERDICTS


def test_get_ground_answers_and_mints_nothing():
    c, _ = _client()
    with c:
        r = c.get(GROUND, params={"q": "brain graph knowledge", "k": 12})
    assert r.status_code == 200, f"{GROUND} -> {r.status_code} (must never 500)"
    j = r.json()
    assert j["label"] in ("MODELED", "UNAVAILABLE")
    assert j["verdict"] in VERDICTS
    assert 0.0 <= float(j.get("grounding_confidence", 0.0)) <= 1.0
    assert "receipt" not in j, "GET ground is a PURE READ — must mint NO receipt"


def test_post_receipt_mints_unsigned_deterministic_sha256():
    c, _ = _client()
    with c:
        r = c.post(RECEIPT, params={"q": "brain graph knowledge", "k": 12})
    assert r.status_code == 200, f"{RECEIPT} -> {r.status_code} (must never 500)"
    j = r.json()
    assert j["verdict"] in VERDICTS
    rec = j["receipt"]
    assert rec["algorithm"] == "sha256"
    assert rec["signed"] is False, "receipt must be UNSIGNED (no fabricated signature)"
    assert rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert isinstance(rec["content_sha256"], str) and len(rec["content_sha256"]) == 64
    # deterministic over the grounding content (excludes the volatile clock).
    assert rec["content_sha256"] == bg.content_receipt(j)["content_sha256"]


def test_receipt_is_deterministic_on_write_and_get_mints_none():
    """A GET mints nothing; the POST digest is reproducible from the same computed result."""
    strong = bg.compute_confidence(_strong_ask())
    d1 = bg.content_receipt(strong)["content_sha256"]
    d2 = bg.content_receipt(strong)["content_sha256"]
    assert d1 == d2 and len(d1) == 64
    # info handler (a GET body) carries no receipt.
    assert "receipt" not in bg.handle_info("a11oy")


# --------------------------------------------------------------------------- #
# 6. honest labels never upgraded
# --------------------------------------------------------------------------- #
def test_labels_are_brain_vocabulary_never_upgraded():
    """grounding_confidence is MODELED, never upgraded to MEASURED/VERIFIED/PROVEN. An
    unavailable brain degrades to the brain's own UNAVAILABLE, never a fabricated pass. The
    tokens MEASURED/VERIFIED/PROVEN below are NEGATIVE examples the surface never emits — they
    exist only to prove the label stays MODELED (Conjecture 1 discipline, never a theorem)."""
    r = bg.compute_confidence(_strong_ask())
    assert r["label"] == bg.LBL_MODELED == "MODELED"
    for forbidden_upgrade in ("MEASURED", "VERIFIED", "PROVEN"):
        assert r["label"] != forbidden_upgrade, "label must never be upgraded"


def test_unavailable_brain_degrades_honestly(monkeypatch):
    """If the brain retrieval is unreachable, evaluate() returns the brain's own UNAVAILABLE
    label and abstains — never a fabricated confidence or verdict."""
    monkeypatch.setattr(bg, "_run_ask", lambda q, k, ns: (None, "brain graph unavailable"))
    r = bg.evaluate("anything", 12, "a11oy")
    assert r["ok"] is False
    assert r["label"] == bg.LBL_UNAVAILABLE == "UNAVAILABLE"
    assert r["verdict"] == bg.VERDICT_INSUFFICIENT and r["should_abstain"] is True
    assert "receipt" not in r, "an UNAVAILABLE read fabricates nothing, mints nothing"


# --------------------------------------------------------------------------- #
# 7. doctrine
# --------------------------------------------------------------------------- #
def test_doctrine_locked8_lambda_trust():
    info = bg.handle_info("a11oy")
    d = info["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1"
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
