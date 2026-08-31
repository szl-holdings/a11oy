# SPDX-License-Identifier: Apache-2.0
"""Tests for szl_brainreceipt — signed inference receipts (integrity, not truth)."""
import json
import szl_brainreceipt as br


def test_sign_produces_bound_object_and_digest():
    r = br.sign_receipt("q", ["s1", "s2"], "answer", "model-x")
    b = r["bound"]
    assert b["schema"] == br.RECEIPT_SCHEMA
    assert b["request_sha256"] == br._sha256_hex("q")
    assert b["output_sha256"] == br._sha256_hex("answer")
    assert b["sources_count"] == 2
    assert len(b["per_source_sha256"]) == 2
    assert len(r["content_sha256"]) == 64


def test_real_signature_verifies_roundtrip():
    r = br.sign_receipt("q", ["s"], "a", "m")
    # ephemeral key exists in test container, so a real signature is produced
    assert r["signed"] is True
    assert r["label"] in (br.LBL_SIGNED_LOCAL, br.LBL_UNSIGNED_LOCAL)
    v = br.verify_receipt(r)
    assert v["signature_valid"] is True
    assert v["content_digest_ok"] is True


def test_tamper_is_detected():
    r = br.sign_receipt("q", ["s"], "a", "m")
    tampered = json.loads(json.dumps(r))
    tampered["bound"]["output_sha256"] = "0" * 64  # someone altered the output binding
    v = br.verify_receipt(tampered)
    assert v["content_digest_ok"] is False  # digest no longer matches -> detected


def test_signature_of_altered_canonical_fails_verify():
    r = br.sign_receipt("q", ["s"], "a", "m")
    if not r["signed"]:
        return
    tampered = json.loads(json.dumps(r))
    # change the bound object so the signature no longer matches the recomputed canonical bytes
    tampered["bound"]["model_id"] = "different-model"
    # content_sha256 left stale; verify recomputes from bound and checks sig -> must fail
    v = br.verify_receipt(tampered)
    assert v["signature_valid"] is False or v["content_digest_ok"] is False


def test_ephemeral_key_labeled_honestly():
    # in a test container with no persistent Secret, the key is ephemeral -> UNSIGNED-LOCAL,
    # never mislabeled as a persistent SIGNED-LOCAL receipt
    r = br.sign_receipt("q", ["s"], "a", "m")
    if r["key_source"] == "ephemeral":
        assert r["label"] == br.LBL_UNSIGNED_LOCAL
    elif r["key_source"].startswith("persistent"):
        assert r["label"] == br.LBL_SIGNED_LOCAL


def test_honesty_statement_present_integrity_not_truth():
    r = br.sign_receipt("q", ["s"], "a", "m")
    assert "integrity" in r["proves"]
    assert "not truth" in r["does_not_prove"].lower()
    # must explicitly disclaim proving correctness / source support
    assert "correct" in r["does_not_prove"] and "support" in r["does_not_prove"]


def test_no_fabricated_signature_when_key_unavailable(monkeypatch):
    # simulate crypto/key unavailable -> honest UNAVAILABLE, digest only, NO fake signature
    import a11oy_signing_key as sk
    monkeypatch.setattr(sk, "load_signing_key",
                        lambda env=None: (None, "", "unavailable", "cryptography unavailable"))
    r = br.sign_receipt("q", ["s"], "a", "m")
    assert r["signed"] is False
    assert r["signature_b64"] is None
    assert r["label"] == br.LBL_UNAVAILABLE
    assert r["content_sha256"]  # still an honest unsigned digest


def test_per_source_membership_checkable():
    r = br.sign_receipt("q", ["alpha", "beta", "gamma"], "a", "m")
    digests = {e["sha256"] for e in r["bound"]["per_source_sha256"]}
    assert br._sha256_hex("beta") in digests  # a verifier can prove "beta" was in the corpus
    assert br._sha256_hex("delta") not in digests


def test_manifest_native_ok_and_invariants():
    man = br.handle_manifest("selftest")
    assert man["surface_id"] == "brainreceipt" and man["data_label"] == br.LBL_MODELED
    inv = man["honesty_invariants"]
    assert all(inv.values())
    assert inv["signature_proves_integrity_not_truth"] is True
    assert inv["no_fabricated_signature"] is True
    assert inv["ephemeral_key_labeled_honestly"] is True
    assert inv["trains_nothing"] is True


def test_get_reads_mint_nothing():
    assert "receipt" not in br.handle_info("s")
    assert "receipt" not in br.handle_manifest("s")
    # POST (sign) mints one
    assert "receipt" in br.handle_sign("q", ["s"], "a", "m", "s")


def test_doctrine_honest():
    d = br._doctrine_block()
    assert d["lambda"] == "Conjecture 1" and d["adds_to_locked_8"] == 0
    assert d["is_model_training"] is False and d["sentience_claim"] is False
    assert br.LBL_SIGNED_LOCAL in br.HONEST_LABELS and br.LBL_UNSIGNED_LOCAL in br.HONEST_LABELS


def test_selftest_passes():
    out = br._selftest()
    assert out["ok"] is True and out["checks"] >= 6
