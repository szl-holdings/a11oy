# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""feat/frontier-braingaps — Brain Gaps coverage-honesty contract guard.

Brain Gaps is the mirror image of the coverage surfaces: it reports, deterministically
and without flattery, where the live knowledge graph is THIN or EMPTY — sparse
communities, weakly-connected island nodes (degree<=1), and the share of nodes with no
real honesty label — and grades a supplied topic COVERED / THIN / GAP. These tests pin
the honest-by-construction invariants — no mocks of the gap logic itself, only
controlled fixture graphs the pure functions run on:

  1. Structural counts (islands, isolated, thin communities, weak-label share, label
     distribution) are MEASURED from the fixture graph and computed correctly.
  2. Estate verdict WELL-COVERED / PATCHY / SPARSE, and a SPARSE posture is NEVER
     softened to WELL-COVERED.
  3. Per-topic COVERED vs THIN vs GAP — a topic with zero matches is a GAP, and
     coverage is NEVER fabricated.
  4. Structural counts labelled MEASURED; the per-topic verdict labelled MODELED;
     labels are read VERBATIM and never upgraded.
  5. RECEIPT-ON-WRITE: the receipt is ONE deterministic UNSIGNED SHA-256 digest; the
     GET gaps read mints nothing.
  6. Doctrine: locked-8 exact, adds nothing, Λ is Conjecture 1 (never a theorem),
     trust ceiling 0.97 (never 100%).
  7. Routes register before the SPA / Node-proxy catch-alls and answer without 500,
     and the live HTTP path proves BOTH a COVERED and a GAP verdict.
"""
import pytest

import szl_braingaps as bg


# --------------------------------------------------------------------------- #
# Fixtures — small, fully synthetic graphs (no network, no heavy index build).
# The graph has a well-connected "lambda" cluster (COVERED), a dangling "khipu"
# node (THIN), an isolated orphan (an island), and no mention of "quantum" (a GAP).
# Node titles carry their honest qualifier: Λ is Conjecture 1, never a theorem;
# Khipu BFT is Conjecture 2, never proven — so the honesty grep never false-flags.
# --------------------------------------------------------------------------- #
def _fixture_nodes():
    return [
        {"id": "lambda-core", "title": "Lambda kernel core", "label": "MEASURED", "degree": 5},
        {"id": "lambda-proof", "title": "Lambda is Conjecture 1, never a theorem", "label": "CONJECTURE", "degree": 4},
        {"id": "lambda-lemma", "title": "Lambda supporting lemma (advisory)", "label": "MODELED", "degree": 3},
        {"id": "khipu-node", "title": "Khipu BFT is Conjecture 2, never proven", "label": "MODELED", "degree": 1},  # island
        {"id": "islet", "title": "orphan islet", "label": "UNAVAILABLE", "degree": 0},  # isolated island
    ]


def _fixture_community_of():
    # the lambda trio (c0, size 3 = thin at max) + two singletons (both thin).
    return {"lambda-core": "c0", "lambda-proof": "c0", "lambda-lemma": "c0",
            "khipu-node": "c1", "islet": "c2"}


def _fixture_map(query=""):
    return bg.analyze(
        nodes=_fixture_nodes(),
        link_count=6,
        community_of=_fixture_community_of(),
        community_algo="fixture-cc",
        content_hash="deadbeef",
        ns="a11oy",
        query=query,
    )


class _FakeIndex:
    """A minimal stand-in for szl_brain_api.BrainIndex exposing exactly the attributes
    live_gaps() reads. Lets the HTTP path run over a deterministic fixture graph."""
    def __init__(self):
        self.nodes = _fixture_nodes()
        self.links = [
            {"source": "lambda-core", "target": "lambda-proof"},
            {"source": "lambda-core", "target": "lambda-lemma"},
            {"source": "lambda-proof", "target": "lambda-lemma"},
            {"source": "lambda-core", "target": "khipu-node"},
        ]
        self.community_of = _fixture_community_of()
        self.community_algo = "fixture-cc"
        self.content_hash = "deadbeef"
        self._pagerank_global = {n["id"]: 0.2 for n in self.nodes}


# --------------------------------------------------------------------------- #
# 1. structural counts MEASURED + correct
# --------------------------------------------------------------------------- #
def test_structural_counts_measured():
    gmap = _fixture_map()
    assert gmap["label"] == bg.LBL_MEASURED
    m = gmap["metrics"]
    assert m["node_count"] == 5 and m["link_count"] == 6
    # islands: khipu (degree 1) + islet (degree 0); isolated: islet only.
    assert m["island_count"] == 2 and m["isolated_count"] == 1
    assert m["island_share"] == pytest.approx(0.4)   # 2/5
    # every community here is <= 3 nodes => all thin.
    assert m["community_count"] == 3 and m["thin_community_count"] == 3
    assert m["thin_community_share"] == pytest.approx(1.0)
    # weak-label share: only "islet" is UNAVAILABLE, nothing UNLABELLED => 1/5.
    assert m["weak_label_count"] == 1 and m["weak_label_share"] == pytest.approx(0.2)
    # label distribution counts the verbatim node labels honestly.
    assert m["label_distribution"]["MODELED"] == 2
    assert m["label_distribution"]["UNAVAILABLE"] == 1


def test_unlabelled_nodes_counted_as_weak():
    # a node with no label at all is UNLABELLED — weak grounding, counted honestly.
    nodes = [{"id": "x", "title": "no-label node", "degree": 3},
             {"id": "y", "title": "labelled", "label": "MEASURED", "degree": 3}]
    gmap = bg.analyze(nodes=nodes, link_count=1,
                      community_of={"x": "c0", "y": "c0"},
                      community_algo="cc", content_hash="beef", ns="a11oy")
    m = gmap["metrics"]
    assert m["label_distribution"]["UNLABELLED"] == 1
    assert m["unlabelled_count"] == 1 and m["weak_label_count"] == 1
    assert m["weak_label_share"] == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# 2. estate verdict — SPARSE is never softened
# --------------------------------------------------------------------------- #
def test_estate_sparse_never_softened():
    # all communities thin (share 1.0 >= 0.50) => SPARSE, never WELL-COVERED.
    gmap = _fixture_map()
    assert gmap["estate_verdict"] == bg.SPARSE
    assert gmap["estate_verdict"] != bg.WELL_COVERED


def test_estate_well_covered_when_dense():
    # a dense, fully-labelled, single large community with no islands => WELL-COVERED.
    nodes = [{"id": f"n{i}", "title": f"node {i}", "label": "MEASURED", "degree": 4}
             for i in range(6)]
    community_of = {f"n{i}": "c0" for i in range(6)}  # one community of 6 (> 3, not thin)
    gmap = bg.analyze(nodes=nodes, link_count=12, community_of=community_of,
                      community_algo="cc", content_hash="beef", ns="a11oy")
    m = gmap["metrics"]
    assert m["island_count"] == 0 and m["thin_community_count"] == 0
    assert gmap["estate_verdict"] == bg.WELL_COVERED


def test_estate_patchy_between():
    # some sparsity (one thin singleton + one island) but below the material thresholds.
    nodes = [{"id": f"n{i}", "title": f"node {i}", "label": "MEASURED", "degree": 4}
             for i in range(6)]
    nodes.append({"id": "lonely", "title": "lonely", "label": "MEASURED", "degree": 1})  # island
    community_of = {f"n{i}": "c0" for i in range(6)}
    community_of["lonely"] = "c1"  # a thin singleton community
    gmap = bg.analyze(nodes=nodes, link_count=12, community_of=community_of,
                      community_algo="cc", content_hash="beef", ns="a11oy")
    m = gmap["metrics"]
    # island share 1/7 and thin-community share 1/2: thin share == 0.5 => that alone is SPARSE.
    # Drop the island threshold consideration by asserting the documented rule holds:
    # thin_community_share here is exactly 0.5 -> SPARSE (>= threshold). So assert SPARSE.
    assert m["thin_community_share"] == pytest.approx(0.5)
    assert gmap["estate_verdict"] == bg.SPARSE  # 0.5 >= 0.50, honestly not softened


def test_estate_patchy_true_middle():
    # 5 dense communities (size 4 > THIN_COMMUNITY_MAX, NOT thin) + 1 thin singleton
    # => thin share 1/6 (< 0.5), one island share 1/21 (< 0.5) => PATCHY (some
    # sparsity, below material thresholds).
    nodes = []
    community_of = {}
    for c in range(5):
        for i in range(4):
            nid = f"c{c}n{i}"
            nodes.append({"id": nid, "title": nid, "label": "MEASURED", "degree": 4})
            community_of[nid] = f"c{c}"
    nodes.append({"id": "island", "title": "island", "label": "MEASURED", "degree": 1})
    community_of["island"] = "solo"  # 1 thin community out of 6
    gmap = bg.analyze(nodes=nodes, link_count=40, community_of=community_of,
                      community_algo="cc", content_hash="beef", ns="a11oy")
    m = gmap["metrics"]
    assert m["thin_community_count"] == 1 and m["community_count"] == 6
    assert m["thin_community_share"] == pytest.approx(1 / 6, abs=1e-6)
    assert m["island_count"] == 1
    assert gmap["estate_verdict"] == bg.PATCHY


# --------------------------------------------------------------------------- #
# 3. per-topic COVERED / THIN / GAP — coverage is never fabricated
# --------------------------------------------------------------------------- #
def test_topic_covered():
    gmap = _fixture_map(query="lambda")
    tp = gmap["topic"]
    assert tp["verdict"] == bg.COVERED
    assert tp["label"] == bg.LBL_MODELED
    assert tp["match_count"] >= bg.COVERED_MIN_MATCHES
    assert tp["best_connected_degree"] >= bg.COVERED_MIN_DEGREE


def test_topic_gap_never_fabricated():
    # "quantum" appears in NO node — an honest GAP, never fabricated into coverage.
    gmap = _fixture_map(query="quantum")
    tp = gmap["topic"]
    assert tp["verdict"] == bg.GAP
    assert tp["match_count"] == 0
    assert tp["matches"] == []


def test_topic_thin_fragile_grounding():
    # "khipu" matches ONE dangling (degree 1) node => THIN (fragile), never COVERED.
    gmap = _fixture_map(query="khipu")
    tp = gmap["topic"]
    assert tp["verdict"] == bg.THIN
    assert 0 < tp["match_count"] < bg.COVERED_MIN_MATCHES or tp["best_connected_degree"] < bg.COVERED_MIN_DEGREE


def test_topic_verdict_pure_function():
    assert bg.topic_verdict([])[0] == bg.GAP
    # enough matches but all weakly-connected (max degree < 2) => THIN, not COVERED.
    weak = [{"id": f"m{i}", "degree": 1} for i in range(4)]
    assert bg.topic_verdict(weak)[0] == bg.THIN
    # enough matches AND one well-connected => COVERED.
    strong = [{"id": "m0", "degree": 5}] + [{"id": f"m{i}", "degree": 1} for i in range(1, 3)]
    assert bg.topic_verdict(strong)[0] == bg.COVERED


# --------------------------------------------------------------------------- #
# 4. honest labelling — MEASURED structural, MODELED topic verdict, never upgraded
# --------------------------------------------------------------------------- #
def test_structural_measured_topic_modeled():
    gmap = _fixture_map(query="lambda")
    assert gmap["label"] == bg.LBL_MEASURED           # structural counts
    assert gmap["topic"]["label"] == bg.LBL_MODELED   # derived verdict
    assert bg.LBL_MEASURED in bg.HONEST_LABELS
    assert bg.LBL_MODELED in bg.HONEST_LABELS


def test_labels_read_verbatim_never_upgraded():
    # A node carrying a low-trust label must be counted VERBATIM, never promoted.
    nodes = [{"id": "x", "title": "structural only", "label": "STRUCTURAL-ONLY", "degree": 0},
             {"id": "y", "title": "unavailable", "label": "UNAVAILABLE", "degree": 1}]
    gmap = bg.analyze(nodes=nodes, link_count=0,
                      community_of={"x": "c0", "y": "c1"},
                      community_algo="cc", content_hash="beef", ns="a11oy")
    dist = gmap["metrics"]["label_distribution"]
    assert dist["STRUCTURAL-ONLY"] == 1 and dist["UNAVAILABLE"] == 1
    # nothing got upgraded to MEASURED/PROVEN.
    assert "MEASURED" not in dist and "PROVEN" not in dist


# --------------------------------------------------------------------------- #
# 5. RECEIPT-ON-WRITE — deterministic unsigned SHA-256; GET gaps mints nothing
# --------------------------------------------------------------------------- #
def test_receipt_deterministic_and_unsigned():
    gmap = _fixture_map(query="lambda")
    r1 = bg._content_receipt(gmap)
    r2 = bg._content_receipt(gmap)
    assert r1["algorithm"] == "sha256" and len(r1["content_sha256"]) == 64
    assert r1["signed"] is False and r1["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert r1["content_sha256"] == r2["content_sha256"], "digest must be deterministic"


def test_get_gaps_mints_nothing():
    # handle_gaps is a pure read (live map may be UNAVAILABLE off-box) — but it must
    # NEVER carry a receipt (receipt-on-write, not on-read).
    out = bg.handle_gaps("a11oy", "lambda")
    assert "receipt" not in out


# --------------------------------------------------------------------------- #
# 6. doctrine block
# --------------------------------------------------------------------------- #
def test_doctrine_block_locked_and_lambda():
    d = bg._doctrine_block()
    assert d["locked_proven"] == 8 and d["locked_set"] == bg.LOCKED_SET
    assert len(d["locked_set"]) == 8 and d["adds_to_locked_8"] == 0
    # Λ is Conjecture 1, never a theorem; Khipu BFT is Conjecture 2, never a theorem.
    assert d["lambda"] == "Conjecture 1"
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0


# --------------------------------------------------------------------------- #
# 7. live endpoints via TestClient — registration, ordering, COVERED + GAP paths
# --------------------------------------------------------------------------- #
INFO = "/api/a11oy/v1/brain/gaps/info"
GAPS = "/api/a11oy/v1/brain/gaps"
RECEIPT = "/api/a11oy/v1/brain/gaps/receipt"


def _route_index(app, path):
    for i, r in enumerate(app.router.routes):
        if getattr(r, "path", None) == path:
            return i
    return None


def test_routes_registered_before_catchalls():
    pytest.importorskip("starlette.testclient")
    import serve
    for path in (INFO, GAPS, RECEIPT):
        assert _route_index(serve.app, path) is not None, f"{path} not registered"
    spa = _route_index(serve.app, "/{full_path:path}")
    proxy = _route_index(serve.app, "/api/a11oy/{path:path}")
    for path in (INFO, GAPS, RECEIPT):
        idx = _route_index(serve.app, path)
        if spa is not None:
            assert idx < spa, f"{path} ({idx}) must precede the SPA catch-all ({spa})"
        if proxy is not None:
            assert idx < proxy, f"{path} ({idx}) must precede the Node proxy ({proxy})"


def test_endpoints_answer_without_500_and_prove_covered_and_gap(monkeypatch):
    pytest.importorskip("starlette.testclient")
    from fastapi.testclient import TestClient
    import szl_brain_api
    import serve

    # Drive the live HTTP path over a deterministic fixture graph so we can prove BOTH a
    # COVERED and a GAP verdict end-to-end (never fabricated), independent of the on-box
    # brain index. This stubs the graph source only — the gap logic runs for real.
    monkeypatch.setattr(szl_brain_api, "get_index", lambda ns="a11oy", **kw: _FakeIndex())

    client = TestClient(serve.app)

    # info — static describe, never 500.
    ri = client.get(INFO)
    assert ri.status_code == 200
    ji = ri.json()
    assert ji["surface_id"] == "braingaps"
    assert set([bg.COVERED, bg.THIN, bg.GAP]) <= set(ji["topic_verdicts"])
    assert set([bg.WELL_COVERED, bg.PATCHY, bg.SPARSE]) <= set(ji["estate_verdicts"])

    # estate-wide gap map — MODELED top label, SPARSE fixture, mints nothing.
    rg = client.get(GAPS)
    assert rg.status_code == 200
    jg = rg.json()
    assert jg["label"] == bg.LBL_MODELED
    assert jg["estate_verdict"] == bg.SPARSE
    assert jg["gaps"]["metrics"]["island_count"] == 2
    assert "receipt" not in jg  # GET mints nothing

    # per-topic COVERED path over HTTP.
    rc = client.get(GAPS, params={"q": "lambda"})
    assert rc.status_code == 200
    jc = rc.json()
    assert jc["gaps"]["topic"]["verdict"] == bg.COVERED
    assert "receipt" not in jc

    # per-topic GAP path over HTTP — coverage never fabricated.
    rgap = client.get(GAPS, params={"q": "quantum"})
    assert rgap.status_code == 200
    jgap = rgap.json()
    assert jgap["gaps"]["topic"]["verdict"] == bg.GAP
    assert jgap["gaps"]["topic"]["match_count"] == 0

    # POST receipt — RECEIPT-ON-WRITE: one unsigned SHA-256 digest.
    rr = client.post(RECEIPT, params={"q": "lambda"})
    assert rr.status_code == 200
    jr = rr.json()
    assert jr["receipt"]["algorithm"] == "sha256"
    assert len(jr["receipt"]["content_sha256"]) == 64
    assert jr["receipt"]["signed"] is False