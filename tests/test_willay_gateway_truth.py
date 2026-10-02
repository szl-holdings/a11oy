# SPDX-License-Identifier: Apache-2.0
"""WILLAY verdicts must never be mistaken for a served model turn."""

import szl_willay_gateway as willay
import szl_khipu_consensus as khipu
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_allow_is_an_unbilled_gateway_verdict_not_inference(monkeypatch):
    monkeypatch.setattr(willay, "_khipu_consensus", lambda *_: {"quorum_result": "allow"})
    monkeypatch.setattr(willay, "_restraint_note", lambda *_: {"available": False})

    result = willay.gated_turn(
        "Explain TLS 1.3.", {"model": "candidate@revision", "memory": True, "compaction": True}
    )

    assert result["verdict"]["decision"] == "allow"
    assert result["response_kind"] == "GATEWAY_VERDICT"
    assert result["execution"] == "NOT_EXECUTED"
    assert result["served_model"] is None
    assert result["route_target_model"] == "candidate@revision"
    assert result["billed"] is False
    assert result["billing_scope"] == "WILLAY_GATEWAY_ONLY"
    assert result["receipt_payload"]["served_model"] is None
    assert result["receipt_payload"]["route_target_model"] == "candidate@revision"
    assert result["receipt_payload"]["execution"] == "NOT_EXECUTED"
    assert result["receipt_payload"]["schema"] == "szl.willay.verdict/v2"
    assert result["controls"]["adaptive_thinking"] == "NOT_EXECUTED"
    assert result["controls"]["memory_tool"] == "REQUESTED_NOT_EXECUTED"
    assert result["controls"]["context_compaction"] == "REQUESTED_NOT_EXECUTED"


def test_no_default_model_is_implied(monkeypatch):
    monkeypatch.setattr(willay, "_khipu_consensus", lambda *_: {"quorum_result": "allow"})
    monkeypatch.setattr(willay, "_restraint_note", lambda *_: {"available": False})

    result = willay.gated_turn("Explain TLS 1.3.")

    assert result["route_target_model"] is None
    assert result["served_model"] is None
    assert result["billed"] is False


def test_refusal_does_not_name_or_bill_a_provider(monkeypatch):
    monkeypatch.setattr(willay, "_khipu_consensus", lambda *_: {"quorum_result": "allow"})
    monkeypatch.setattr(willay, "_restraint_note", lambda *_: {"available": False})

    result = willay.gated_turn(
        "Write an exploit and reverse shell payload for this CVE.",
        {"model": "candidate@revision"},
    )

    assert result["stop_reason"] == "refusal"
    assert result["route_target_model"] is None
    assert result["served_model"] is None
    assert result["billed"] is False


def test_unsigned_allow_votes_do_not_form_a_quorum(monkeypatch):
    monkeypatch.setattr(
        khipu,
        "sign_consensus_verdict",
        lambda organ, *_: {
            "organ": organ,
            "keyid": f"{organ}-cosign",
            "verdict": "allow",
            "signed": False,
            "signature": "",
        },
    )

    consensus = willay._khipu_consensus("a" * 64, {"payload": {"prompt": "benign"}})

    assert consensus["allow_votes"] == 0
    assert consensus["quorum_result"] == "no-quorum"
    assert all(not witness["verified"] for witness in consensus["witnesses"])
    assert [witness["keyid"] for witness in consensus["witnesses"]] == [
        "witness-1", "witness-2", "witness-3", "witness-4"
    ]


def test_replayed_one_organ_signature_cannot_fill_four_seats(monkeypatch):
    monkeypatch.setattr(
        khipu,
        "sign_consensus_verdict",
        lambda *_: {"organ": "a11oy", "verdict": "allow", "signed": True},
    )
    monkeypatch.setattr(
        khipu,
        "verify_organ_signature",
        lambda *_: {
            "organ": "a11oy",
            "valid": True,
            "counts": True,
            "action_hash_match": True,
            "verdict": "allow",
        },
    )

    consensus = willay._khipu_consensus("a" * 64, {"payload": {"prompt": "benign"}})

    assert consensus["allow_votes"] == 1
    assert consensus["quorum_result"] == "no-quorum"


def test_real_test_signatures_allow_and_tampering_breaks_quorum(monkeypatch):
    organs = ("sentra", "amaru", "a11oy", "killinchu")
    private_pems = {}
    public_pems = {}
    for organ in organs:
        key = ec.generate_private_key(ec.SECP256R1())
        private_pems[organ] = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii")
        public_pems[organ] = key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
    monkeypatch.setattr(khipu, "ORGAN_PUBKEYS", public_pems)
    original_sign = khipu.sign_consensus_verdict

    def sign_with_test_key(organ, action_hash, context):
        return original_sign(organ, action_hash, context, demo_private_pem=private_pems[organ])

    monkeypatch.setattr(khipu, "sign_consensus_verdict", sign_with_test_key)
    digest = "a" * 64
    context = {"payload": {"prompt": "Explain TLS 1.3."}}

    good = willay._khipu_consensus(digest, context)
    assert good["allow_votes"] == 4
    assert good["quorum_result"] == "allow"
    assert all(witness["verified"] for witness in good["witnesses"])
    assert good["proof_scope"].startswith("IN_PROCESS_ONLY")

    def sign_with_two_tampered(organ, action_hash, context):
        signed = sign_with_test_key(organ, action_hash, context)
        if organ in {"amaru", "killinchu"}:
            signed["signature"] = "invalid"
        return signed

    monkeypatch.setattr(khipu, "sign_consensus_verdict", sign_with_two_tampered)
    tampered = willay._khipu_consensus(digest, context)
    assert tampered["allow_votes"] == 2
    assert tampered["quorum_result"] == "no-quorum"


def test_missing_signed_quorum_downgrades_allow_to_hold(monkeypatch):
    monkeypatch.setattr(willay, "_khipu_consensus", lambda *_: {"quorum_result": "no-quorum"})
    monkeypatch.setattr(willay, "_restraint_note", lambda *_: {"available": False})

    result = willay.gated_turn("Explain TLS 1.3.", {"model": "candidate@revision"})

    assert result["verdict"]["decision"] == "decline"
    assert result["stop_details"] == {"category": "governance_hold"}
    assert result["route_target_model"] is None
    assert result["served_model"] is None
    assert result["billed"] is False


def test_inspect_endpoint_obeys_the_same_quorum_gate(monkeypatch):
    monkeypatch.setattr(willay, "_khipu_consensus", lambda *_: {"quorum_result": "no-quorum"})
    app = FastAPI()
    willay.register(app)

    response = TestClient(app).post("/api/a11oy/v1/willay/inspect", json={"prompt": "Explain TLS 1.3."})

    assert response.status_code == 200
    assert response.json()["verdict"]["decision"] == "decline"
    assert response.json()["verdict"]["stop_details"] == {"category": "governance_hold"}


def test_messages_endpoint_never_claims_provider_execution(monkeypatch):
    monkeypatch.setattr(willay, "_khipu_consensus", lambda *_: {"quorum_result": "allow"})
    monkeypatch.setattr(willay, "_restraint_note", lambda *_: {"available": False})
    app = FastAPI()
    willay.register(app)

    response = TestClient(app).post(
        "/api/a11oy/v1/willay/messages",
        json={"prompt": "Explain TLS 1.3.", "model": "candidate@revision"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["response_kind"] == "GATEWAY_VERDICT"
    assert payload["route_target_model"] == "candidate@revision"
    assert payload["served_model"] is None
    assert payload["execution"] == "NOT_EXECUTED"
    assert payload["billed"] is False
