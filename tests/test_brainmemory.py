"""feat/frontier-brainmemory — Brain Memory Freshness contract guard.

Brain Memory Freshness computes a deterministic, explainable memory-freshness score per
knowledge-graph node, derived from honest signals ONLY. These tests pin the honest-by-
construction invariants that make it trustworthy — the scoring is a pure function, so most
assertions run directly on it, plus a TestClient smoke over the three registered routes:

  1. Score is always in [0,1]; per-component breakdown (connectivity, salience, recency)
     is computed and reported for every ranked node.
  2. STRUCTURAL-ONLY label is used HONESTLY when NO recency signal exists — the recency
     component is None (never a fabricated timestamp), and the top label is never upgraded
     to MEASURED.
  3. MEASURED is used ONLY when a real per-node capture date (captured_at) is present; the
     recency component is then the LIVE age of that real date, and a node with no real date
     scores 0.0 on recency (recency_measured=false) — never a fabricated timestamp.
  4. Verdict transitions FRESH -> AGING -> STALE follow the fixed thresholds.
  5. Receipt is a deterministic UNSIGNED SHA-256 on write (POST); a GET mints nothing.
  6. Doctrine: locked-8 exact, adds nothing, Lambda = Conjecture 1, trust 0.97 (never 100%).
  7. The estate propagates a REAL committed capture date (per-snapshot) onto its 34 org-repo
     nodes only, and the live ranking route emits MEASURED from that real date.

Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""
import pytest

import szl_brainmemory as bm

pytest.importorskip("starlette.testclient")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

INFO = "/api/a11oy/v1/brain/memory/info"
RANK = "/api/a11oy/v1/brain/memory"
RECEIPT = "/api/a11oy/v1/brain/memory/receipt"


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    status = bm.register(app, ns="a11oy")
    assert status.startswith("brainmemory-wired")
    return TestClient(app)


# --------------------------------------------------------------------------- #
# 1. score in range + per-component breakdown computed for every node.
# --------------------------------------------------------------------------- #
def test_score_in_range_and_components_computed():
    nodes = [
        {"id": "hub", "degree": 40, "salience": 0.9, "title": "hub"},
        {"id": "mid", "degree": 12, "salience": 0.3, "title": "mid"},
        {"id": "leaf", "degree": 1, "salience": 0.02, "title": "leaf"},
        {"id": "orphan", "degree": 0, "salience": 0.0, "title": "orphan"},
    ]
    agg = bm.compute_freshness(nodes, recency_field=None)
    assert agg["node_count"] == 4
    for e in agg["ranking"]:
        assert 0.0 <= e["freshness"] <= 1.0
        comps = e["components"]
        assert 0.0 <= comps["connectivity"] <= 1.0
        assert 0.0 <= comps["salience"] <= 1.0
        assert e["verdict"] in (bm.FRESH, bm.AGING, bm.STALE)


# --------------------------------------------------------------------------- #
# 2. STRUCTURAL-ONLY is honest when there is no recency signal — the recency
#    component is None (no fabricated timestamp) and the label is never upgraded.
# --------------------------------------------------------------------------- #
def test_structural_only_label_when_no_recency_signal():
    nodes = [
        {"id": "a", "degree": 10, "salience": 0.5},
        {"id": "b", "degree": 1, "salience": 0.01},
    ]
    agg = bm.compute_freshness(nodes, recency_field=None)
    assert agg["label"] == bm.STRUCTURAL_ONLY
    assert agg["recency_signal"] is False
    assert agg["recency_field"] is None
    assert agg["mode"] == "structural-only"
    assert agg["recency_measured_nodes"] == 0
    assert agg["recency_coverage"] == 0.0
    # the recency component is honestly absent (None), never a fabricated value.
    for e in agg["ranking"]:
        assert e["components"]["recency"] is None
        # STRUCTURAL-ONLY is the honest proxy label; it is never upgraded to MEASURED.
        assert e["label"] == bm.STRUCTURAL_ONLY
        assert e["label"] != "MEASURED"


def test_structural_only_missing_field_stays_structural():
    # RECENCY_FIELDS probed but none present -> honest STRUCTURAL-ONLY, not a fabricated MEASURED.
    nodes = [{"id": "x", "degree": 5, "salience": 0.2}]
    agg = bm.compute_freshness(nodes, recency_field="captured_at")
    assert agg["label"] == bm.STRUCTURAL_ONLY
    assert agg["recency_signal"] is False
    # NEVER upgraded to MEASURED without a real date.
    assert agg["label"] != bm.MEASURED


def test_unparseable_date_never_fabricates_measured():
    # a present-but-unparseable recency field is NOT a real date -> stays STRUCTURAL-ONLY.
    nodes = [{"id": "x", "degree": 5, "salience": 0.2, "captured_at": "not-a-date"}]
    agg = bm.compute_freshness(nodes, recency_field="captured_at")
    assert agg["label"] == bm.STRUCTURAL_ONLY
    assert agg["recency_signal"] is False
    assert agg["recency_measured_nodes"] == 0


# --------------------------------------------------------------------------- #
# 3. MEASURED only with a real capture date; recency is the LIVE age of that date.
# --------------------------------------------------------------------------- #
def test_measured_label_with_real_capture_date():
    now = 2_000_000_000.0
    day = bm._SECONDS_PER_DAY
    nodes = [
        {"id": "new", "degree": 5, "salience": 0.2, "captured_at": now - 5 * day},
        {"id": "old", "degree": 5, "salience": 0.2,
         "captured_at": now - (bm.RECENCY_HORIZON_DAYS + 30) * day},
    ]
    agg = bm.compute_freshness(nodes, recency_field="captured_at", now_ts=now)
    assert agg["label"] == bm.MEASURED
    assert agg["recency_signal"] is True
    assert agg["recency_field"] == "captured_at"
    assert agg["recency_granularity"] == "per-snapshot"
    assert agg["recency_horizon_days"] == bm.RECENCY_HORIZON_DAYS
    assert agg["recency_measured_nodes"] == 2 and agg["recency_coverage"] == 1.0
    # newer capture -> fresher; recency is the live decayed age, not a min-max rank.
    assert agg["ranking"][0]["id"] == "new"
    assert agg["ranking"][0]["components"]["recency"] > 0.9   # ~5 days old
    assert agg["ranking"][-1]["components"]["recency"] == 0.0  # past the horizon
    # each MEASURED entry echoes the REAL captured_at it used (never fabricated).
    for e in agg["ranking"]:
        assert e["recency_measured"] is True
        assert e["captured_at"] is not None


def test_measured_recency_is_live_now_dependent():
    # The recency component tracks now(): the SAME real date is fresher when read earlier.
    day = bm._SECONDS_PER_DAY
    node = [{"id": "r", "degree": 5, "salience": 0.2, "captured_at": 1_000_000_000.0}]
    early = bm.compute_freshness(node, recency_field="captured_at",
                                 now_ts=1_000_000_000.0 + 10 * day)
    late = bm.compute_freshness(node, recency_field="captured_at",
                                now_ts=1_000_000_000.0 + 100 * day)
    assert early["ranking"][0]["components"]["recency"] > late["ranking"][0]["components"]["recency"]


def test_measured_partial_coverage_undated_node_never_fabricated():
    # A node with no real capture date scores 0.0 on recency, recency_measured=false, and NEVER
    # gets a fabricated timestamp — while the surface stays MEASURED from the dated node.
    now = 2_000_000_000.0
    nodes = [
        {"id": "dated", "degree": 5, "salience": 0.5, "captured_at": now - bm._SECONDS_PER_DAY},
        {"id": "undated", "degree": 5, "salience": 0.5},
    ]
    agg = bm.compute_freshness(nodes, recency_field="captured_at", now_ts=now)
    assert agg["label"] == bm.MEASURED
    assert agg["recency_measured_nodes"] == 1
    assert 0.0 < agg["recency_coverage"] < 1.0
    undated = [e for e in agg["ranking"] if e["id"] == "undated"][0]
    assert undated["components"]["recency"] == 0.0
    assert undated["recency_measured"] is False
    assert undated["captured_at"] is None


def test_iso_capture_date_parses_as_recency():
    day = bm._SECONDS_PER_DAY
    now = bm._parse_ts("2026-07-08T00:00:00Z")
    nodes = [
        {"id": "new", "degree": 3, "salience": 0.1, "captured_at": "2026-07-01T00:00:00Z"},
        {"id": "old", "degree": 3, "salience": 0.1, "captured_at": "2020-01-01T00:00:00Z"},
    ]
    agg = bm.compute_freshness(nodes, recency_field="captured_at", now_ts=now)
    assert agg["label"] == bm.MEASURED
    assert agg["ranking"][0]["id"] == "new"


# --------------------------------------------------------------------------- #
# 4. Verdict transitions across the fixed thresholds.
# --------------------------------------------------------------------------- #
def test_verdict_transitions():
    assert bm._verdict(0.95) == bm.FRESH
    assert bm._verdict(bm.FRESH_MIN) == bm.FRESH
    assert bm._verdict(0.45) == bm.AGING
    assert bm._verdict(bm.AGING_MIN) == bm.AGING
    assert bm._verdict(0.10) == bm.STALE
    assert bm._verdict(0.0) == bm.STALE


def test_stale_node_carries_reharvest_note():
    nodes = [
        {"id": "hub", "degree": 100, "salience": 1.0},
        {"id": "orphan", "degree": 0, "salience": 0.0},
    ]
    agg = bm.compute_freshness(nodes, recency_field=None)
    orphan = [e for e in agg["ranking"] if e["id"] == "orphan"][0]
    assert orphan["verdict"] == bm.STALE
    # STALE nodes are flagged for re-harvest, never silently trusted.
    assert "re-harvest" in orphan["note"].lower()


# --------------------------------------------------------------------------- #
# 5. Receipt: deterministic UNSIGNED SHA-256 on write; a GET mints nothing.
# --------------------------------------------------------------------------- #
def test_receipt_deterministic_sha256_on_write():
    nodes = [{"id": "a", "degree": 3, "salience": 0.3}, {"id": "b", "degree": 1, "salience": 0.1}]
    agg = bm.compute_freshness(nodes, recency_field=None)
    r1 = bm.content_receipt(agg)
    r2 = bm.content_receipt(agg)
    assert r1["algorithm"] == "sha256"
    assert len(r1["content_sha256"]) == 64
    assert r1["content_sha256"] == r2["content_sha256"]
    assert r1["signed"] is False
    assert r1["mode"] == "UNSIGNED-CONTENT-DIGEST"


def test_receipt_differs_for_different_aggregate():
    a1 = bm.compute_freshness([{"id": "a", "degree": 3, "salience": 0.3}], recency_field=None)
    a2 = bm.compute_freshness([{"id": "a", "degree": 9, "salience": 0.9},
                               {"id": "b", "degree": 1, "salience": 0.1}], recency_field=None)
    assert bm.content_receipt(a1)["content_sha256"] != bm.content_receipt(a2)["content_sha256"]


def test_get_info_mints_no_receipt():
    info = bm.handle_info("a11oy")
    # RECEIPT-ON-WRITE-NOT-ON-READ: a GET read never mints a receipt.
    assert "receipt" not in info


# --------------------------------------------------------------------------- #
# 6. TestClient smoke over the three registered routes.
# --------------------------------------------------------------------------- #
def test_route_info(client):
    r = client.get(INFO)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["surface_id"] == "brainmemory"
    assert "formula" in j
    assert "receipt" not in j  # GET mints nothing


def test_route_ranking(client):
    r = client.get(RANK + "?top=8")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    # the label is one of the two honest options; MEASURED only ever appears with a real date.
    assert j["label"] in (bm.MEASURED, bm.STRUCTURAL_ONLY)
    assert isinstance(j["ranking"], list)
    for e in j["ranking"]:
        assert 0.0 <= e["freshness"] <= 1.0
        assert e["verdict"] in (bm.FRESH, bm.AGING, bm.STALE)
    assert "receipt" not in j  # GET mints nothing


def test_route_receipt_on_write(client):
    r = client.post(RECEIPT)
    assert r.status_code == 200
    j = r.json()
    rec = j["receipt"]
    assert rec["algorithm"] == "sha256"
    assert len(rec["content_sha256"]) == 64
    assert rec["signed"] is False


# --------------------------------------------------------------------------- #
# 8. The estate propagates a REAL committed capture date onto its org-repo nodes
#    (per-snapshot), and ONLY those nodes — never a fabricated per-node date.
# --------------------------------------------------------------------------- #
def test_graph_propagates_real_capture_date_onto_repo_nodes_only():
    import a11oy_brain_graph as bg

    snap = bg.ORG_REPOS_SNAPSHOT
    g = bg.get_brain_graph("a11oy")
    repos = [n for n in g["nodes"]
             if n.get("kind") == "repo" and n.get("layer") == 0
             and n.get("org") == snap["org"]]
    # every estate repo carries the REAL committed snapshot date, verbatim.
    assert len(repos) == len(snap["repos"])
    for n in repos:
        assert n["captured_at"] == snap["captured"]      # real, not fabricated
        assert n["captured_granularity"] == "per-snapshot"
        assert n["captured_source"] == snap["source"]
    # the harvested FIELD ring carries NO capture date (we must not invent one).
    field = [n for n in g["nodes"] if n.get("layer") == bg.FIELD_LAYER]
    assert field, "expected a harvested field ring in this build"
    assert all("captured_at" not in n for n in field)


def test_live_route_emits_measured_from_real_capture_date(client):
    # The live ranking reuses the honest graph; because the org-repo nodes now carry a REAL
    # captured_at, the surface reports MEASURED — and every MEASURED entry echoes a real date.
    r = client.get(RANK + "?top=5000")
    j = r.json()
    assert j["label"] == bm.MEASURED
    assert j["recency_signal"] is True
    assert j["recency_field"] == "captured_at"
    assert j["recency_granularity"] == "per-snapshot"
    assert j["recency_horizon_days"] == bm.RECENCY_HORIZON_DAYS
    # coverage is reported honestly (only the snapshot repos are dated) and never overclaimed.
    assert j["recency_measured_nodes"] > 0
    assert 0.0 < j["recency_coverage"] <= 1.0
    measured = [e for e in j["ranking"] if e.get("recency_measured")]
    assert measured, "expected some MEASURED (dated) nodes in the ranking"
    for e in measured:
        assert e["captured_at"] is not None          # real date, never fabricated
        assert e["components"]["recency"] > 0.0
    # nodes with no real date are honestly recency_measured=false with recency 0.0.
    undated = [e for e in j["ranking"] if e.get("recency_measured") is False]
    for e in undated:
        assert e["captured_at"] is None
        assert e["components"]["recency"] == 0.0


# --------------------------------------------------------------------------- #
# 7. Doctrine block.
# --------------------------------------------------------------------------- #
def test_doctrine_block():
    d = bm._doctrine()
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    # Lambda is Conjecture 1, never a theorem (honest advisory label).
    assert d["lambda"] == "Conjecture 1"
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97
    assert d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0


def test_labels_never_upgraded_in_vocabulary():
    # every emitted label stays within the honest vocabulary; nothing invented, nothing upgraded.
    assert bm.STRUCTURAL_ONLY in bm.HONEST_LABELS
    assert bm.MEASURED in bm.HONEST_LABELS
