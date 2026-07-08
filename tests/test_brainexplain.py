# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""feat/frontier-brainexplain — Brain Explain retrieval-explainability contract guard.

Brain Explain turns the brain's REAL retrieval (szl_brain_api.get_index().ask) into a
deterministic, plain-language account of WHY it retrieved what it did: which query
terms matched which seed nodes, why each supporting node ranked where it did (ppr vs
salience), which communities were traversed, and each supporting node's OWN honesty
label VERBATIM. These tests pin the honest-by-construction invariants — no mocks of the
trace logic itself, only controlled synthetic retrieval fixtures the pure functions run
on:

  1. The trace is MODELED, deterministic, and DESCRIPTIVE — same retrieval => same
     account; per-node basis is attributed from the real signal, never invented.
  2. Node/seed honesty labels are read VERBATIM and NEVER upgraded.
  3. OPAQUE when retrieval returns too little to explain (no query-matched seed); no
     query-relevance rationale is fabricated.
  4. PARTIALLY-EXPLAINABLE when the anchor is only a MODELED similarity proxy /
     traversal, or a supporting node is unattributed — never softened to EXPLAINABLE.
  5. RECEIPT-ON-WRITE: the digest is a deterministic UNSIGNED SHA-256 over the trace,
     minted ONLY on POST; the GET explain read mints nothing.
  6. Doctrine: locked-8 exact, adds 0, Λ is Conjecture 1 (never a theorem), trust
     ceiling 0.97 (never 100%), 0 runtime CDN.
  7. Routes register before the SPA / Node-proxy catch-alls and answer without 500,
     proving BOTH an EXPLAINABLE-capable path and an honest OPAQUE path.
"""
import pytest

import szl_brainexplain as bx


# --------------------------------------------------------------------------- #
# Fixtures — small, fully synthetic retrievals (no network, no heavy index build).
# --------------------------------------------------------------------------- #
def _seeds_direct():
    # a seed whose OWN text literally carries the query terms "brain graph".
    return [
        {"id": "n1", "title": "brain graph harvest", "kind": "module", "score": 0.8,
         "node_label": "HARVESTED",
         "match": {"exact_token_overlap": 0.5, "vector_cosine": 0.3, "substring": False}},
    ]


def _grounding_direct():
    return [
        {"id": "n1", "title": "brain graph harvest", "kind": "module",
         "node_label": "HARVESTED", "community": "c0", "salience": 0.10, "ppr": 0.30},
        {"id": "n2", "title": "estate ledger", "kind": "module",
         "node_label": "MODELED", "community": "c0", "salience": 0.05, "ppr": 0.12},
    ]


def _comms():
    return [{"id": "c0", "size": 2, "summary": "community c0: 2 nodes"}]


def _trace_direct():
    return bx.build_trace(
        query="brain graph", seeds=_seeds_direct(),
        grounding_nodes=_grounding_direct(), community_summaries=_comms(),
        ns="a11oy", content_hash="deadbeef")


# --------------------------------------------------------------------------- #
# 1. MODELED + deterministic + descriptive (basis attributed, not invented).
# --------------------------------------------------------------------------- #
def test_trace_is_modeled_and_explainable():
    t = _trace_direct()
    assert t["label"] == bx.LBL_MODELED
    assert t["verdict"] == bx.EXPLAINABLE
    sup = t["supporting_nodes"]
    # deterministic ordering: strongest ppr first.
    assert [s["id"] for s in sup] == ["n1", "n2"]
    # n1 is anchored by a DIRECT term match; its matched terms are the literal overlap.
    assert sup[0]["basis"] == bx.BASIS_DIRECT
    assert sup[0]["matched_terms"] == ["brain", "graph"]
    # n2 carries none of the query terms — reached by transparent graph traversal, and
    # the trace says so honestly rather than inventing a term match.
    assert sup[1]["basis"] == bx.BASIS_TRAVERSAL
    assert sup[1]["matched_terms"] == []
    # ppr_gain is the measured lift over baseline salience (descriptive, not re-ranked).
    assert sup[0]["ppr_gain"] == pytest.approx(0.20)


def test_trace_is_deterministic():
    a = dict(_trace_direct()); a.pop("timestamp_utc")
    b = dict(_trace_direct()); b.pop("timestamp_utc")
    assert a == b, "same retrieval must yield the same account"


def test_receipt_core_excludes_timestamp():
    # the digest attests the verdict+evidence, not the clock.
    t1 = _trace_direct()
    t2 = _trace_direct()
    assert bx._canonical_core(t1) == bx._canonical_core(t2)


# --------------------------------------------------------------------------- #
# 2. labels read VERBATIM, never upgraded.
# --------------------------------------------------------------------------- #
def test_labels_read_verbatim_never_upgraded():
    seeds = [{"id": "x", "title": "structural stub", "kind": "module", "score": 0.3,
              "node_label": "STRUCTURAL-ONLY",
              "match": {"exact_token_overlap": 0.5, "vector_cosine": 0.0,
                        "substring": False}}]
    grounding = [
        {"id": "x", "title": "structural stub", "kind": "module",
         "node_label": "STRUCTURAL-ONLY", "community": "c0", "salience": 0.1, "ppr": 0.2},
        {"id": "y", "title": "unavailable node", "kind": "module",
         "node_label": "UNAVAILABLE", "community": "c0", "salience": 0.0, "ppr": 0.05},
    ]
    t = bx.build_trace(query="structural stub", seeds=seeds,
                       grounding_nodes=grounding, community_summaries=[],
                       ns="a11oy", content_hash="beef")
    labels = {s["id"]: s["node_label"] for s in t["supporting_nodes"]}
    assert labels["x"] == "STRUCTURAL-ONLY" and labels["y"] == "UNAVAILABLE"
    # a low-trust node label is NEVER promoted to MEASURED/PROVEN.
    assert "MEASURED" not in labels.values() and "PROVEN" not in labels.values()
    # seed labels are verbatim too.
    assert t["seed_matches"][0]["node_label"] == "STRUCTURAL-ONLY"


def test_missing_label_is_unlabelled_not_fabricated():
    seeds = [{"id": "z", "title": "brain graph", "kind": "module", "score": 0.4,
              "match": {"exact_token_overlap": 0.5}}]  # no node_label key
    grounding = [{"id": "z", "title": "brain graph", "kind": "module",
                  "community": "c0", "salience": 0.1, "ppr": 0.2}]  # no node_label
    t = bx.build_trace(query="brain graph", seeds=seeds, grounding_nodes=grounding,
                       community_summaries=[], ns="a11oy")
    assert t["supporting_nodes"][0]["node_label"] == "UNLABELLED"
    assert t["seed_matches"][0]["node_label"] == "UNLABELLED"


# --------------------------------------------------------------------------- #
# 3. OPAQUE when retrieval returns too little — no fabricated rationale.
# --------------------------------------------------------------------------- #
def test_no_seed_is_opaque():
    # Λ is Conjecture 1, never a theorem: with no query-matched seed the honest verdict
    # is OPAQUE — the grounding would be generic global salience, not query-driven.
    t = bx.build_trace(query="brain graph", seeds=[],
                       grounding_nodes=_grounding_direct(),
                       community_summaries=_comms(), ns="a11oy")
    assert t["verdict"] == bx.OPAQUE
    assert t["summary"]["seed_count"] == 0
    assert "fabricated" in t["verdict_reason"]


def test_no_supporting_nodes_is_opaque():
    # A seed with an empty grounding subgraph is also OPAQUE (nothing to explain);
    # this is an honest BLOCKED, never a fake green EXPLAINABLE.
    t = bx.build_trace(query="brain graph", seeds=_seeds_direct(),
                       grounding_nodes=[], community_summaries=[], ns="a11oy")
    assert t["verdict"] == bx.OPAQUE
    assert t["summary"]["supporting_count"] == 0


# --------------------------------------------------------------------------- #
# 4. PARTIALLY-EXPLAINABLE — never softened to EXPLAINABLE.
# --------------------------------------------------------------------------- #
def test_vector_only_anchor_is_partial():
    # seed matched by a MODELED hash-embedding proxy only (no literal term overlap);
    # Λ = Conjecture 1, so a similarity proxy is never promoted to a proven match.
    seeds = [{"id": "v1", "title": "alpha", "kind": "module", "score": 0.2,
              "node_label": "MODELED",
              "match": {"exact_token_overlap": 0.0, "vector_cosine": 0.4,
                        "substring": False}}]
    grounding = [{"id": "v1", "title": "alpha", "kind": "module",
                  "node_label": "MODELED", "community": "c1", "salience": 0.05,
                  "ppr": 0.20}]
    t = bx.build_trace(query="zulu quebec", seeds=seeds, grounding_nodes=grounding,
                       community_summaries=[], ns="a11oy")
    assert t["verdict"] == bx.PARTIALLY_EXPLAINABLE
    assert t["supporting_nodes"][0]["basis"] == bx.BASIS_VECTOR


def test_unattributed_node_forces_partial():
    # a node in the grounding with no term/similarity/traversal signal is reported
    # honestly as unattributed and forces PARTIALLY-EXPLAINABLE — never rationalized.
    seeds = _seeds_direct()
    grounding = _grounding_direct() + [
        {"id": "n3", "title": "orphan", "kind": "module", "node_label": "MODELED",
         "community": "c2", "salience": 0.0, "ppr": 0.0}]  # zero ppr => no traversal signal
    t = bx.build_trace(query="brain graph", seeds=seeds, grounding_nodes=grounding,
                       community_summaries=_comms(), ns="a11oy")
    assert t["verdict"] == bx.PARTIALLY_EXPLAINABLE
    bases = {s["id"]: s["basis"] for s in t["supporting_nodes"]}
    assert bases["n3"] == bx.BASIS_UNATTRIBUTED
    assert t["summary"]["unattributed_count"] == 1


# --------------------------------------------------------------------------- #
# 5. RECEIPT-ON-WRITE — deterministic unsigned SHA-256 on write; GET mints nothing.
# --------------------------------------------------------------------------- #
def test_receipt_deterministic_and_unsigned():
    t = _trace_direct()
    r1 = bx._content_receipt(t)
    r2 = bx._content_receipt(t)
    assert r1["algorithm"] == "sha256" and len(r1["content_sha256"]) == 64
    assert r1["signed"] is False and r1["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert r1["content_sha256"] == r2["content_sha256"], "digest must be deterministic"


def test_get_explain_mints_nothing():
    # handle_explain is a pure read (live snapshot may be OPAQUE/UNAVAILABLE off-box) —
    # but it must NEVER carry a receipt (receipt-on-write, not on-read).
    out = bx.handle_explain("a11oy", "")
    assert "receipt" not in out


# --------------------------------------------------------------------------- #
# 6. doctrine block.
# --------------------------------------------------------------------------- #
def test_doctrine_block_locked_and_lambda():
    d = bx._doctrine_block()
    assert d["locked_proven"] == 8 and d["locked_set"] == bx.LOCKED_SET
    assert len(d["locked_set"]) == 8 and d["adds_to_locked_8"] == 0
    # Λ is Conjecture 1, never a theorem; Khipu BFT is Conjecture 2, never a theorem.
    assert d["lambda"] == "Conjecture 1"
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    assert d["kernel_commit"] == bx.KERNEL_COMMIT


# --------------------------------------------------------------------------- #
# 7. live endpoints via TestClient (registration, ordering, honest responses).
# --------------------------------------------------------------------------- #
INFO = "/api/a11oy/v1/brain/explain/info"
EXPLAIN = "/api/a11oy/v1/brain/explain"
RECEIPT = "/api/a11oy/v1/brain/explain/receipt"


def _route_index(app, path):
    for i, r in enumerate(app.router.routes):
        if getattr(r, "path", None) == path:
            return i
    return None


def test_routes_registered_before_catchalls():
    pytest.importorskip("starlette.testclient")
    import serve
    for path in (INFO, EXPLAIN, RECEIPT):
        assert _route_index(serve.app, path) is not None, f"{path} not registered"
    spa = _route_index(serve.app, "/{full_path:path}")
    proxy = _route_index(serve.app, "/api/a11oy/{path:path}")
    for path in (INFO, EXPLAIN, RECEIPT):
        idx = _route_index(serve.app, path)
        if spa is not None:
            assert idx < spa, f"{path} ({idx}) must precede the SPA catch-all ({spa})"
        if proxy is not None:
            assert idx < proxy, f"{path} ({idx}) must precede the Node proxy ({proxy})"


def test_endpoints_answer_without_500():
    pytest.importorskip("starlette.testclient")
    from fastapi.testclient import TestClient
    import serve
    client = TestClient(serve.app)

    # info — static describe, never 500.
    ri = client.get(INFO)
    assert ri.status_code == 200
    ji = ri.json()
    assert ji["surface_id"] == "brainexplain"
    assert set(ji["verdicts"]) == {bx.EXPLAINABLE, bx.PARTIALLY_EXPLAINABLE, bx.OPAQUE}
    assert ji["label"] == bx.LBL_MODELED

    # explain (real query) — MODELED trace or an honest UNAVAILABLE off-box; mints nothing.
    re_ = client.get(EXPLAIN, params={"q": "brain graph", "k": 8})
    assert re_.status_code == 200
    je = re_.json()
    assert "receipt" not in je
    assert je["verdict"] in (bx.EXPLAINABLE, bx.PARTIALLY_EXPLAINABLE, bx.OPAQUE)
    assert je["label"] in (bx.LBL_MODELED, bx.LBL_UNAVAILABLE)

    # explain (empty query) — an honest OPAQUE path: no query-matched seed, no
    # fabricated rationale.
    re0 = client.get(EXPLAIN, params={"q": ""})
    assert re0.status_code == 200
    je0 = re0.json()
    assert je0["verdict"] == bx.OPAQUE
    assert "receipt" not in je0

    # receipt (POST) — the trace + an unsigned SHA-256 content digest (receipt-on-write).
    rc = client.post(RECEIPT, json={"q": "brain graph", "k": 8})
    assert rc.status_code == 200
    jc = rc.json()
    assert jc["receipt"]["algorithm"] == "sha256"
    assert len(jc["receipt"]["content_sha256"]) == 64
    assert jc["receipt"]["signed"] is False

    # a malformed POST body degrades to an empty query, never a 500.
    rb = client.post(RECEIPT, data="{not json", headers={"content-type": "application/json"})
    assert rb.status_code != 500
