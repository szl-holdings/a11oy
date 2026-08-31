# SPDX-License-Identifier: Apache-2.0
"""Tests for szl_brainserve — governed bridge to the estate's served brain model.

All tests are network-free: _call_model is monkeypatched so no real Space is dialled.
"""
import szl_brainserve as bs


def _fake_ok_response(repo=bs.EXPECTED_REPO, rev=bs.EXPECTED_REVISION,
                      sig="UNSIGNED", covers=False):
    return {
        "model": f"{repo}@{rev}",
        "choices": [{"message": {"content": "Ok"}}],
        "szl_provenance": {
            "schema": "szl.openai-compat-provenance/v1",
            "model": {"repo": repo, "revision": rev, "file": "f.gguf", "sha256": "abc123"},
            "runtime": {"space": "SZLHOLDINGS/szl-model-inference-lab", "service_level": "BEST_EFFORT_NO_SLA"},
            "receipts": {"status": "DECLARED_KEY_SIGNATURES_VALID", "covers_this_output": covers},
            "output": {"signature_status": sig},
        },
    }


def test_committed_default_and_override():
    cfg = bs.read_env(environ={})
    assert cfg["url"] == bs.DEFAULT_URL and cfg["model"] == bs.DEFAULT_MODEL
    assert cfg["source"] == "committed-default"
    cfg2 = bs.read_env(environ={bs.ENV_URL: "https://x", bs.ENV_MODEL: "m"})
    assert cfg2["url"] == "https://x" and cfg2["source"] == "operator-override"


def test_live_answer_matching_provenance_is_measured_serving(monkeypatch):
    monkeypatch.setattr(bs, "_call_model", lambda u, m, p, timeout=30.0: (_fake_ok_response(), None))
    r = bs.probe(ns="a11oy")
    assert r["label"] == bs.LBL_MEASURED
    assert r["verdict"] == bs.VERDICT_SERVING
    assert r["answered"] is True
    assert r["provenance_matches_expected"] is True
    assert r["answer_sample"] == "Ok"


def test_provenance_mismatch_is_surfaced_not_hidden(monkeypatch):
    # served model self-reports a DIFFERENT revision -> mismatch, but reading is still real
    monkeypatch.setattr(bs, "_call_model",
                        lambda u, m, p, timeout=30.0: (_fake_ok_response(rev="0" * 40), None))
    r = bs.probe(ns="a11oy")
    assert r["label"] == bs.LBL_MEASURED       # a real answer was received
    assert r["verdict"] == bs.VERDICT_MISMATCH # but we refuse to call it the expected model
    assert r["provenance_matches_expected"] is False


def test_unsigned_and_uncovered_caveats_propagated_never_upgraded(monkeypatch):
    monkeypatch.setattr(bs, "_call_model",
                        lambda u, m, p, timeout=30.0: (_fake_ok_response(sig="UNSIGNED", covers=False), None))
    r = bs.probe(ns="a11oy")
    prov = r["provenance"]
    assert prov["output_signature_status"] == "UNSIGNED"       # stays UNSIGNED
    assert prov["receipts_cover_this_output"] is False          # never upgraded to True
    assert "UNSIGNED" in prov["caveat"] or "unsigned" in prov["caveat"].lower()


def test_no_answer_is_unavailable_never_fabricated(monkeypatch):
    monkeypatch.setattr(bs, "_call_model",
                        lambda u, m, p, timeout=30.0: (None, "TimeoutError: Space asleep"))
    r = bs.probe(ns="a11oy")
    assert r["label"] == bs.LBL_UNAVAILABLE
    assert r["verdict"] == bs.VERDICT_UNAVAILABLE
    assert r["measured"] is False and r["answered"] is False
    assert "asleep" in r["transport_error"]


def test_receipt_deterministic_unsigned_write_only(monkeypatch):
    monkeypatch.setattr(bs, "_call_model", lambda u, m, p, timeout=30.0: (_fake_ok_response(), None))
    r1 = bs.handle_serve("a11oy")
    r2 = bs.handle_serve("a11oy")
    assert "receipt" not in r1  # GET serve mints nothing
    rec = bs.content_receipt(r1)
    rec2 = bs.content_receipt(r2)
    assert rec["content_sha256"] == rec2["content_sha256"]  # same reading -> same digest
    assert len(rec["content_sha256"]) == 64 and rec["signed"] is False
    assert "receipt" in bs.handle_receipt("a11oy")  # POST mints one
    assert "receipt" not in bs.handle_info("a11oy")


def test_receipt_never_claims_to_sign_the_model_output():
    # our receipt binds OUR reading; it must not claim to sign the upstream (UNSIGNED) output
    rec = bs.content_receipt({"label": bs.LBL_MEASURED, "provenance": {"output_signature_status": "UNSIGNED"}})
    assert rec["signed"] is False
    assert "does NOT sign the model" in rec["note"] or "UNSIGNED" in rec["note"]


def test_manifest_native_ok_and_invariants():
    man = bs.handle_manifest("selftest")
    assert man["surface_id"] == "brainserve" and man["data_label"] == bs.LBL_MODELED
    inv = man["honesty_invariants"]
    assert all(inv.values())
    assert inv["unsigned_output_stays_unsigned"] is True
    assert inv["receipt_never_overclaims_coverage"] is True
    assert inv["provenance_mismatch_surfaced_not_hidden"] is True
    assert inv["trains_nothing"] is True
    assert inv["admits_to_gradients_zero"] is True


def test_doctrine_honest():
    d = bs._doctrine_block()
    assert d["lambda"] == "Conjecture 1" and d["adds_to_locked_8"] == 0
    assert d["is_model_training"] is False and d["sentience_claim"] is False
    assert d["admits_to_gradients"] == 0
    assert bs.LBL_MEASURED in bs.HONEST_LABELS and bs.LBL_UNAVAILABLE in bs.HONEST_LABELS


def test_selftest_passes():
    out = bs._selftest()
    assert out["ok"] is True and out["checks"] >= 5
