# SPDX-License-Identifier: Apache-2.0
"""Tests for szl_braincite — verifiable claim->source citations.

Doctrine note: the strings below that resemble a bad claim are NEGATIVE examples the estate
never asserts — Lambda is Conjecture 1, never a theorem. They exist only to prove the surface
never fabricates a citation and never upgrades a label.
"""
import json
import szl_braincite as bc


def test_cite_term_binds_only_real_backing_node():
    nodes = [{"id": "n1", "title": "energy ledger receipt", "node_label": "MODELED"}]
    # a term present in a real title is CITED to that node
    got = bc._cite_term("energy", nodes)
    assert got and got[0]["id"] == "n1" and got[0]["node_label"] == "MODELED"
    # a term absent from every title is UNCITED (empty) — never fabricated
    assert bc._cite_term("zzqqxx", nodes) == []


def test_node_label_carried_verbatim_never_upgraded():
    nodes = [{"id": "n1", "title": "governance doctrine node", "node_label": "STRUCTURAL-ONLY"}]
    got = bc._cite_term("doctrine", nodes)
    assert got[0]["node_label"] == "STRUCTURAL-ONLY"  # verbatim, not upgraded to MEASURED


def test_verdict_thresholds_honest():
    assert bc._verdict(1.0) == bc.VERDICT_FULLY_CITED
    assert bc._verdict(0.75) == bc.VERDICT_PARTIALLY_CITED
    assert bc._verdict(0.5) == bc.VERDICT_PARTIALLY_CITED
    assert bc._verdict(0.25) == bc.VERDICT_UNCITED_DOMINANT
    assert bc._verdict(None) == bc.VERDICT_NO_CLAIMS


def test_no_claim_terms_is_honest_no_claims():
    r = bc.evaluate("the a an of to by", ns="selftest")
    assert r["verdict"] == bc.VERDICT_NO_CLAIMS
    assert r["total_claims"] == 0
    assert r["citation_coverage"] is None  # never fabricated to 0.0 or 1.0


def test_claim_terms_extraction_drops_stopwords_and_short():
    terms = bc._claim_terms("what is the energy ledger receipt")
    assert "energy" in terms and "ledger" in terms and "receipt" in terms
    assert "the" not in terms and "is" not in terms  # stopwords dropped


def test_receipt_deterministic_unsigned_and_write_only():
    sample = {
        "label": "MODELED", "verdict": bc.VERDICT_FULLY_CITED, "query": "energy",
        "citation_coverage": 1.0, "cited_count": 1, "total_claims": 1,
        "claims": [{"claim": "energy", "status": bc.CITED, "sources": [{"id": "n1"}]}],
    }
    r1 = bc.content_receipt(sample)
    r2 = bc.content_receipt(sample)
    assert r1["content_sha256"] == r2["content_sha256"]
    assert len(r1["content_sha256"]) == 64
    assert r1["signed"] is False
    assert r1["mode"] == "UNSIGNED-CONTENT-DIGEST"
    # GET reads (info / cite result) never carry a receipt
    assert "receipt" not in bc.handle_info("selftest")


def test_handle_receipt_mints_receipt_get_cite_does_not():
    # handle_cite is a pure read; handle_receipt (POST path) mints one
    cite = bc.handle_cite("selftest", "the a an", 12)
    assert "receipt" not in cite
    rec = bc.handle_receipt("selftest", "the a an", 12)
    assert "receipt" in rec and rec["receipt"]["signed"] is False


def test_manifest_native_ok_shape_and_invariants():
    man = bc.handle_manifest("selftest")
    assert man["surface_id"] == "braincite"
    assert man["data_label"] == "MODELED"
    assert man["label"] in bc.HONEST_LABELS
    inv = man["honesty_invariants"]
    assert all(inv.values()), "every declared honesty invariant must be true"
    assert inv["no_fabricated_citation"] is True
    assert inv["lambda_is_conjecture_not_theorem"] is True
    assert inv["no_consciousness_claim"] is True


def test_doctrine_block_honest():
    d = bc._doctrine_block()
    assert d["locked_proven"] == 8 and d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1"  # Lambda is Conjecture 1, never a theorem
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["sentience_claim"] is False and d["is_model_training"] is False


def test_label_top_is_in_honest_vocabulary():
    assert bc.LBL_MODELED in bc.HONEST_LABELS
    assert bc.LBL_UNAVAILABLE in bc.HONEST_LABELS
    assert "MEASURED" in bc.HONEST_LABELS  # exists but this surface never emits it fabricated


def test_evaluate_with_stubbed_retrieval_cited_and_uncited(monkeypatch):
    # Stub the brain retrieval so we can prove both a CITED and an UNCITED claim deterministically.
    def fake_ask(ns, q, k):
        return {"grounding_subgraph": {"nodes": [
            {"id": "a", "title": "energy ledger", "node_label": "MODELED"},
            {"id": "b", "title": "provenance chain", "node_label": "STRUCTURAL-ONLY"},
        ]}}
    monkeypatch.setattr(bc, "_ask", fake_ask)
    # 'energy' backed by node a (CITED); 'zqxwv' backed by nothing (UNCITED)
    r = bc.evaluate("energy zqxwv", ns="a11oy")
    by = {c["claim"]: c for c in r["claims"]}
    assert by["energy"]["status"] == bc.CITED and by["energy"]["sources"][0]["id"] == "a"
    assert by["zqxwv"]["status"] == bc.UNCITED and by["zqxwv"]["sources"] == []
    assert r["cited_count"] == 1 and r["total_claims"] == 2
    assert r["citation_coverage"] == 0.5
    assert r["verdict"] == bc.VERDICT_PARTIALLY_CITED


def test_evaluate_fully_cited_path(monkeypatch):
    def fake_ask(ns, q, k):
        return {"grounding_subgraph": {"nodes": [
            {"id": "a", "title": "energy ledger receipt provenance", "node_label": "MODELED"},
        ]}}
    monkeypatch.setattr(bc, "_ask", fake_ask)
    r = bc.evaluate("energy provenance", ns="a11oy")
    assert r["verdict"] == bc.VERDICT_FULLY_CITED
    assert r["citation_coverage"] == 1.0
    assert all(c["status"] == bc.CITED for c in r["claims"])


def test_evaluate_uncited_dominant_path(monkeypatch):
    def fake_ask(ns, q, k):
        return {"grounding_subgraph": {"nodes": [
            {"id": "a", "title": "energy ledger", "node_label": "MODELED"},
        ]}}
    monkeypatch.setattr(bc, "_ask", fake_ask)
    # energy CITED; two nonsense terms UNCITED -> 1/3 coverage -> UNCITED-DOMINANT
    r = bc.evaluate("energy zqxwv qqzzt", ns="a11oy")
    assert r["citation_coverage"] < 0.5
    assert r["verdict"] == bc.VERDICT_UNCITED_DOMINANT


def test_retrieval_unreachable_is_unavailable_never_fabricated(monkeypatch):
    def boom(ns, q, k):
        raise RuntimeError("brain unreachable")
    monkeypatch.setattr(bc, "_ask", boom)
    r = bc.evaluate("energy ledger", ns="a11oy")
    assert r["label"] == bc.LBL_UNAVAILABLE
    assert all(c["status"] == bc.UNCITED for c in r["claims"])  # nothing fabricated
    assert r["cited_count"] == 0


def test_selftest_passes():
    out = bc._selftest()
    assert out["ok"] is True and out["checks"] >= 6
