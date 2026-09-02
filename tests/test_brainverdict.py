# SPDX-License-Identifier: Apache-2.0
"""Tests for szl_brainverdict — the composed verifiable answer (integrity, not truth)."""
import json
import szl_brainverdict as bv
import szl_brainserve as bs
import szl_braincite as bc
import szl_braineval as be


def test_assurance_never_above_components():
    # no live model -> unverifiable, regardless of citation/eval strength
    assert bv._derive_assurance(False, "FULLY-CITED", "REFUSAL-HONEST") == bv.ASSURANCE_NO_MODEL
    # best case
    assert bv._derive_assurance(True, "FULLY-CITED", "REFUSAL-HONEST") == bv.ASSURANCE_VERIFIABLE
    # partial citation -> partial
    assert bv._derive_assurance(True, "PARTIALLY-CITED", "REFUSAL-HONEST") == bv.ASSURANCE_PARTIAL
    # fabrication or uncited-dominant -> weak, even with a live model
    assert bv._derive_assurance(True, "UNCITED-DOMINANT", "REFUSAL-HONEST") == bv.ASSURANCE_WEAK
    assert bv._derive_assurance(True, "FULLY-CITED", "FABRICATION-DETECTED") == bv.ASSURANCE_WEAK


def test_no_model_means_unverifiable(monkeypatch):
    monkeypatch.setattr(bs, "probe", lambda environ=None, ns="a11oy": {"label": "UNAVAILABLE", "verdict": "UNAVAILABLE"})
    monkeypatch.setattr(bc, "evaluate", lambda q, k=12, ns="a11oy": {"label": "MODELED", "verdict": "FULLY-CITED", "citation_coverage": 1.0})
    monkeypatch.setattr(be, "evaluate", lambda environ=None, timeout=8.0, ns="a11oy": {"label": "MEASURED", "verdict": "REFUSAL-HONEST", "refusal_rate": 0.97})
    v = bv.compose("q", ns="a11oy")
    assert v["assurance_level"] == bv.ASSURANCE_NO_MODEL  # weakest link forces it
    assert "served_model" in v["weakest_link"]


def test_grounded_when_all_measured_and_strong(monkeypatch):
    monkeypatch.setattr(bs, "probe", lambda environ=None, ns="a11oy": {"label": "MEASURED", "verdict": "SERVING-EXPECTED", "provenance_matches_expected": True, "served_model_id": "m@rev"})
    monkeypatch.setattr(bc, "evaluate", lambda q, k=12, ns="a11oy": {"label": "MODELED", "verdict": "FULLY-CITED", "citation_coverage": 1.0, "cited_count": 3, "total_claims": 3})
    monkeypatch.setattr(be, "evaluate", lambda environ=None, timeout=8.0, ns="a11oy": {"label": "MEASURED", "verdict": "REFUSAL-HONEST", "refusal_rate": 0.97})
    v = bv.compose("q", ns="a11oy")
    assert v["assurance_level"] == bv.ASSURANCE_VERIFIABLE
    assert "none" in v["weakest_link"].lower()


def test_fabrication_forces_weak(monkeypatch):
    monkeypatch.setattr(bs, "probe", lambda environ=None, ns="a11oy": {"label": "MEASURED", "verdict": "SERVING-EXPECTED", "provenance_matches_expected": True, "served_model_id": "m"})
    monkeypatch.setattr(bc, "evaluate", lambda q, k=12, ns="a11oy": {"label": "MODELED", "verdict": "FULLY-CITED", "citation_coverage": 1.0})
    monkeypatch.setattr(be, "evaluate", lambda environ=None, timeout=8.0, ns="a11oy": {"label": "MEASURED", "verdict": "FABRICATION-DETECTED", "refusal_rate": 0.5})
    v = bv.compose("q", ns="a11oy")
    assert v["assurance_level"] == bv.ASSURANCE_WEAK
    assert "FABRICATION" in v["weakest_link"]


def test_no_fabricated_component_on_error(monkeypatch):
    # a component that raises must be recorded UNAVAILABLE, never faked into a healthy reading
    def boom(*a, **k): raise RuntimeError("down")
    monkeypatch.setattr(bs, "probe", boom)
    monkeypatch.setattr(bc, "evaluate", lambda q, k=12, ns="a11oy": {"label": "MODELED", "verdict": "FULLY-CITED", "citation_coverage": 1.0})
    monkeypatch.setattr(be, "evaluate", lambda environ=None, timeout=8.0, ns="a11oy": {"label": "UNAVAILABLE", "verdict": "UNAVAILABLE"})
    v = bv.compose("q", ns="a11oy")
    assert v["components"]["served_model"]["label"] == "UNAVAILABLE"
    assert v["assurance_level"] == bv.ASSURANCE_NO_MODEL


def test_sign_binds_chain_and_self_verifies(monkeypatch):
    monkeypatch.setattr(bs, "probe", lambda environ=None, ns="a11oy": {"label": "MEASURED", "verdict": "SERVING-EXPECTED", "provenance_matches_expected": True, "served_model_id": "m@rev"})
    monkeypatch.setattr(bc, "evaluate", lambda q, k=12, ns="a11oy": {"label": "MODELED", "verdict": "FULLY-CITED", "citation_coverage": 1.0})
    monkeypatch.setattr(be, "evaluate", lambda environ=None, timeout=8.0, ns="a11oy": {"label": "MEASURED", "verdict": "REFUSAL-HONEST", "refusal_rate": 0.97})
    out = bv.sign_verdict("what is lambda", k=4, ns="a11oy")
    rc = out["receipt"]; v = out["self_verification"]
    assert rc["signed"] is True  # ephemeral/persistent key present in test container
    assert v["signature_valid"] is True and v["content_digest_ok"] is True
    # the signed output is the composed verdict; the sources bind the component verdicts
    assert out["verdict"]["assurance_level"] == bv.ASSURANCE_VERIFIABLE


def test_signature_is_integrity_not_truth():
    assert "INTEGRITY only" in bv.PROVES
    assert "not truth" in bv.DOES_NOT_PROVE.lower()
    assert "correct" in bv.DOES_NOT_PROVE


def test_manifest_native_ok_and_invariants():
    man = bv.handle_manifest("selftest")
    assert man["surface_id"] == "brainverdict" and man["data_label"] == bv.LBL_MODELED
    inv = man["honesty_invariants"]
    assert all(inv.values())
    assert inv["assurance_never_above_components"] is True
    assert inv["no_model_means_unverifiable"] is True
    assert inv["no_fabricated_component"] is True
    assert inv["weakest_link_always_named"] is True
    assert inv["signature_proves_integrity_not_truth"] is True


def test_get_reads_mint_nothing():
    assert "receipt" not in bv.handle_info("s")
    assert "receipt" not in bv.handle_manifest("s")


def test_doctrine_honest():
    d = bv._doctrine_block()
    assert d["lambda"] == "Conjecture 1" and d["adds_to_locked_8"] == 0
    assert d["is_model_training"] is False and d["sentience_claim"] is False


def test_spec_doc_exists_and_states_integrity_not_truth():
    with open("docs/verifiable-answer-receipt.md") as f:
        spec = f.read()
    assert "szl.brain.verifiable-answer-receipt/v1" in spec
    assert "INTEGRITY, not TRUTH" in spec or "integrity, not truth" in spec.lower()


def test_selftest_passes():
    out = bv._selftest()
    assert out["ok"] is True and out["checks"] >= 5
