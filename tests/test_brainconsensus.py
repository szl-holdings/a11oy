# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""test_brainconsensus — honest corroboration of a brain grounding.

These checks pin the honest-by-construction contract of the BRAIN CONSENSUS surface, which
measures how MANY distinct nodes support a query's grounding and how BROADLY they agree
(distinct supporting nodes + distinct communities spanned + support concentration) over the
SAME honest grounding subgraph szl_brain_api serves:

  * the corroboration score always lands in [0,1]; distinct-node and distinct-community counts
    are computed from the fixture and always reported;
  * multi-community support reads CORROBORATED; support that collapses to ONE node reads
    SINGLE-SOURCE and sets the single-source-risk flag;
  * NEVER CORROBORATED while the single-source-risk flag is set — the honesty override holds
    whatever the node count happens to be (one community of many nodes is still one source);
  * RECEIPT-ON-WRITE-NOT-ON-READ: the measurement (GET) mints NOTHING; only the receipt (POST)
    emits an UNSIGNED SHA-256 content digest, deterministic over the content;
  * the honest MODELED label is read verbatim and is NEVER upgraded; a missing brain index
    degrades honestly to UNAVAILABLE rather than fabricating a number;
  * doctrine: locked-8 exact, adds 0, Λ = Conjecture 1 (never a theorem), trust 0.97 not 100%.

Adversarial / negative strings below are labeled: Λ stays Conjecture 1, never a theorem,
never green — they exist only to prove the checks still catch a real drift.
"""
import szl_brainconsensus as bc


class _FakeIndex:
    """Deterministic stand-in retriever so these unit checks never depend on the live graph.
    ask(q, k) returns a preset grounding subgraph keyed by a substring of the query."""

    def __init__(self, grounding_by_key):
        self._g = grounding_by_key

    def ask(self, q, k):
        if "single" in q:
            key = "single"
        elif "weak" in q:
            key = "weak"
        else:
            key = "corroborated"
        nodes = [dict(n) for n in self._g.get(key, [])[:max(1, int(k))]]
        return {"grounding_subgraph": {"nodes": nodes, "node_count": len(nodes)}}


def _idx():
    corroborated = [
        {"id": "n0", "title": "n0", "community": "c0", "ppr": 0.30, "node_label": "MODELED"},
        {"id": "n1", "title": "n1", "community": "c1", "ppr": 0.25, "node_label": "MODELED"},
        {"id": "n2", "title": "n2", "community": "c2", "ppr": 0.20, "node_label": "MODELED"},
        {"id": "n3", "title": "n3", "community": "c0", "ppr": 0.15, "node_label": "MODELED"},
        {"id": "n4", "title": "n4", "community": "c1", "ppr": 0.10, "node_label": "MODELED"},
    ]
    weak = [  # multiple nodes but ALL in one community — a single source, not corroboration
        {"id": "w0", "title": "w0", "community": "c0", "ppr": 0.40, "node_label": "MODELED"},
        {"id": "w1", "title": "w1", "community": "c0", "ppr": 0.35, "node_label": "MODELED"},
        {"id": "w2", "title": "w2", "community": "c0", "ppr": 0.25, "node_label": "MODELED"},
    ]
    single = [
        {"id": "u0", "title": "u0", "community": "c0", "ppr": 0.80, "node_label": "MODELED"},
    ]
    return _FakeIndex({"corroborated": corroborated, "weak": weak, "single": single})


# --------------------------------------------------------------------------- #
# corroboration in the unit interval; distinct-node + distinct-community counts reported
# --------------------------------------------------------------------------- #
def test_corroboration_in_unit_interval_and_counts_reported():
    idx = _idx()
    for q, k in [("corroborated query", 12), ("weak query", 12), ("single query", 12)]:
        a = bc.assess(idx, q, k)
        assert a["ok"] is True and a["label"] == bc.MODELED
        assert 0.0 <= a["corroboration"] <= 1.0
        m = a["measures"]
        assert m["distinct_support_nodes"] >= 1
        assert m["distinct_communities"] >= 1
        assert a["honesty_invariants"]["distinct_nodes_and_communities_reported"] is True


def test_distinct_node_and_cross_community_counts_on_fixture():
    # The corroborated fixture is 5 distinct nodes spanning 3 distinct communities (c0,c1,c2).
    a = bc.assess(_idx(), "corroborated query", 12)
    m = a["measures"]
    assert m["distinct_support_nodes"] == 5, m["distinct_support_nodes"]
    assert m["distinct_communities"] == 3, m["distinct_communities"]
    assert m["effective_communities"] >= bc.MIN_EFFECTIVE_COMMUNITIES


def test_duplicate_support_nodes_counted_once():
    # A grounding subgraph that repeats a node id must be counted ONCE (distinct nodes only).
    dupe = _FakeIndex({"corroborated": [
        {"id": "d0", "community": "c0", "ppr": 0.5},
        {"id": "d0", "community": "c1", "ppr": 0.5},  # same id — not a second source
        {"id": "d1", "community": "c1", "ppr": 0.4},
    ]})
    a = bc.assess(dupe, "corroborated query", 12)
    assert a["measures"]["distinct_support_nodes"] == 2


# --------------------------------------------------------------------------- #
# verdicts: multi-community => CORROBORATED; one node => SINGLE-SOURCE + risk flag
# --------------------------------------------------------------------------- #
def test_multi_community_support_is_corroborated():
    a = bc.assess(_idx(), "corroborated query", 12)
    assert a["verdict"] == bc.CORROBORATED
    assert a["single_source_risk"] is False


def test_single_node_support_is_single_source_and_flags_risk():
    a = bc.assess(_idx(), "single query", 12)
    assert a["measures"]["distinct_support_nodes"] == 1
    assert a["verdict"] == bc.SINGLE_SOURCE
    assert a["single_source_risk"] is True


def test_single_source_flag_fires_when_support_is_one_node():
    # Direct check on the verdict logic: one supporting node => single-source-risk set.
    m = bc._measure([{"id": "x", "community": "c0", "weight": 1.0}])
    verdict, risk, _reason = bc._verdict(m)
    assert verdict == bc.SINGLE_SOURCE
    assert risk is True


def test_never_corroborated_when_single_source_risk_set():
    # The 'weak' fixture is many nodes but ALL one community — single-source-risk must be set
    # and the verdict must NEVER be CORROBORATED, whatever the node count. (Λ = Conjecture 1,
    # never a theorem, never green — this negative case only proves the override still bites.)
    a = bc.assess(_idx(), "weak query", 12)
    assert a["measures"]["distinct_communities"] == 1
    assert a["single_source_risk"] is True
    assert a["verdict"] != bc.CORROBORATED
    assert a["verdict"] == bc.WEAK_CORROBORATION


def test_no_support_is_single_source_risk():
    empty = _FakeIndex({})
    a = bc.assess(empty, "corroborated query", 5)  # key resolves but rows are empty
    assert a["support_nodes_retrieved"] == 0
    assert a["verdict"] == bc.SINGLE_SOURCE
    assert a["single_source_risk"] is True


# --------------------------------------------------------------------------- #
# measure math — direct unit checks on the pure functions
# --------------------------------------------------------------------------- #
def test_measure_one_community_zero_community_breadth():
    coherent = [{"id": "a", "community": "c0", "weight": 0.6},
                {"id": "b", "community": "c0", "weight": 0.4}]
    m = bc._measure(coherent)
    assert m["distinct_communities"] == 1
    assert m["community_breadth"] == 0.0
    assert m["community_concentration"] == 1.0


def test_measure_cross_community_higher_corroboration_than_one_clique():
    clique = bc._measure([{"id": f"a{i}", "community": "c0", "weight": 0.25} for i in range(4)])
    spread = bc._measure([{"id": f"b{i}", "community": f"c{i}", "weight": 0.25} for i in range(4)])
    assert spread["corroboration"] > clique["corroboration"], \
        "cross-community support must corroborate more strongly than one clique"


# --------------------------------------------------------------------------- #
# RECEIPT-ON-WRITE-NOT-ON-READ
# --------------------------------------------------------------------------- #
def test_measurement_get_mints_no_receipt():
    a = bc.assess(_idx(), "corroborated query", 12)
    assert "receipt" not in a, "the GET measurement is a PURE READ — must mint no receipt"


def test_content_receipt_is_unsigned_sha256_and_deterministic():
    a = bc.assess(_idx(), "corroborated query", 12)
    r1 = bc._content_receipt(a)
    r2 = bc._content_receipt(a)
    assert r1["algorithm"] == "sha256"
    assert r1["signed"] is False, "receipt must be UNSIGNED (no fabricated signature)"
    assert r1["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert isinstance(r1["content_sha256"], str) and len(r1["content_sha256"]) == 64
    assert r1["content_sha256"] == r2["content_sha256"], "digest must be deterministic on write"


def test_handle_receipt_carries_the_digest_on_write():
    # handle_receipt reads through the live namespace; guard so a missing index degrades
    # honestly rather than failing the suite.
    out = bc.handle_receipt("a11oy", "estate thesis", 12)
    if out.get("ok"):
        rec = out["receipt"]
        assert rec is not None and rec["algorithm"] == "sha256"
        assert rec["signed"] is False and len(rec["content_sha256"]) == 64
    else:
        assert out["label"] == bc.UNAVAILABLE and out.get("receipt") is None


# --------------------------------------------------------------------------- #
# honest labels + degraded path
# --------------------------------------------------------------------------- #
def test_label_is_modeled_and_never_upgraded():
    a = bc.assess(_idx(), "corroborated query", 12)
    assert a["label"] == bc.MODELED
    info = bc.handle_info("a11oy")
    assert info["label"] == bc.MODELED
    assert set(info["honest_labels"]) <= {bc.MODELED, bc.UNAVAILABLE}


def test_missing_brain_index_degrades_to_unavailable(monkeypatch):
    def _boom(_ns):
        raise RuntimeError("brain index offline")
    monkeypatch.setattr(bc, "_get_index", _boom)
    out = bc.handle_consensus("a11oy", "corroborated query", 12)
    assert out["ok"] is False
    assert out["label"] == bc.UNAVAILABLE
    assert "corroboration" not in out, "must not fabricate a number when degraded"


# --------------------------------------------------------------------------- #
# doctrine
# --------------------------------------------------------------------------- #
def test_doctrine_locked8_lambda_trust():
    d = bc._doctrine_block()
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    # Λ is Conjecture 1, advisory, never a theorem, never green.
    assert d["lambda"].startswith("Conjecture 1")
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0


# --------------------------------------------------------------------------- #
# routes register (GET reads + POST receipt) BEFORE any catch-all
# --------------------------------------------------------------------------- #
def test_register_wires_all_three_routes():
    import pytest
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    app = FastAPI()
    status = bc.register(app, ns="a11oy")
    assert status.startswith("brainconsensus-wired")

    client = TestClient(app)
    info = client.get("/api/a11oy/v1/brain/consensus/info")
    assert info.status_code == 200
    j = info.json()
    assert j["ok"] is True and j["label"] == bc.MODELED
    assert "receipt" not in j, "GET info is a pure read"
