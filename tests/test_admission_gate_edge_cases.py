# SPDX-License-Identifier: Apache-2.0
"""Focused admission-gate edge cases requested by issue #1626."""
from __future__ import annotations

import base64
import hashlib

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

import szl_claim_rupture_gate as claim_gate
import szl_confattest as confattest
import szl_dsse as dsse
import szl_public_verify as public_verify


def _check(result: dict[str, object], name: str) -> dict[str, object]:
    for row in result["checks"]:  # type: ignore[index]
        if row.get("check") == name:
            return row
    raise AssertionError(f"missing verifier check: {name}")


def _valid_untrusted_envelope() -> tuple[dict[str, object], ec.EllipticCurvePublicKey]:
    """Create a valid P-256 DSSE envelope whose signer is not in the trust ring."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    key_id = dsse.keyid_for_public_pem(public_pem)

    inner = {"claim": "signature is valid", "issuer": "untrusted-test-signer"}
    payload = {
        "body": inner,
        "payload_digest": hashlib.sha256(dsse.canonical_json(inner)).hexdigest(),
    }
    payload_bytes = dsse.canonical_json(payload)
    signed_bytes = dsse.pae(dsse.KHIPU_PAYLOAD_TYPE, payload_bytes)
    signature = private_key.sign(signed_bytes, ec.ECDSA(hashes.SHA256()))

    # Establish that the signature itself is cryptographically valid before the
    # repository trust policy rejects the unknown identity.
    public_key.verify(signature, signed_bytes, ec.ECDSA(hashes.SHA256()))
    return (
        {
            "payloadType": dsse.KHIPU_PAYLOAD_TYPE,
            "payload": base64.b64encode(payload_bytes).decode("ascii"),
            "signatures": [
                {
                    "keyid": key_id,
                    "sig": base64.b64encode(signature).decode("ascii"),
                }
            ],
        },
        public_key,
    )


def test_valid_signature_from_unknown_signer_is_denied() -> None:
    envelope, _ = _valid_untrusted_envelope()

    result = public_verify.verify_receipt(envelope=envelope)
    signature = _check(result, "signature")

    assert signature["status"] == public_verify.MISMATCH
    assert any(
        row.get("reason") == "unexpected keyid"
        for row in signature["signatures"]  # type: ignore[index]
    )
    assert result["verdict"] == "FAIL"


def test_corrupted_subject_digest_is_denied_after_signature_gate() -> None:
    inner = {"claim": "immutable artifact bytes", "value": 42}
    payload = {
        "body": inner,
        "payload_digest": "0" * 64,
    }
    envelope = {
        "payloadType": dsse.KHIPU_PAYLOAD_TYPE,
        "payload": base64.b64encode(dsse.canonical_json(payload)).decode("ascii"),
        "signatures": [{"keyid": "runtime-test-key", "sig": "AA=="}],
    }

    # Isolate the post-signature subject-binding boundary. Even when the runtime
    # signature verifier reports success, contradictory subject bytes must fail.
    result = public_verify.verify_receipt(
        envelope=envelope,
        runtime_verify_fn=lambda value: {
            "signature_valid": True,
            "keyid_verified": "runtime-test-key",
            "detail": "test fixture: signature gate admitted this envelope",
        },
    )
    signature = _check(result, "signature")
    digest = _check(result, "payload_digest")

    assert signature["status"] == public_verify.VERIFIED
    assert digest["status"] == public_verify.MISMATCH
    assert result["verdict"] == "FAIL"


def test_trust_score_at_the_ceiling_never_exceeds_point_97() -> None:
    assert confattest.TRUST_CEIL == pytest.approx(0.97)
    assert confattest._clamp(
        confattest.TRUST_CEIL, 0.0, confattest.TRUST_CEIL
    ) == pytest.approx(0.97)
    assert confattest._clamp(
        confattest.TRUST_CEIL + 0.01, 0.0, confattest.TRUST_CEIL
    ) == pytest.approx(0.97)

    modeled = confattest._lambda_axes(
        seed=42,
        subject="admission-boundary",
        quote_digest="f" * 64,
        attested=True,
        reversible=True,
    )
    scores = [row["score"] for row in modeled["axes"]]

    assert scores
    assert max(scores) <= confattest.TRUST_CEIL
    assert modeled["value"] <= confattest.TRUST_CEIL


def test_empty_claim_body_is_blocked_without_exception() -> None:
    parsed = claim_gate.parse_evaluate_request(
        {
            "claims": [
                {
                    "claim_id": "claim-empty",
                    "statement": "   ",
                    "atomic": True,
                    "evidence_refs": [],
                    "consequence_owner": {},
                }
            ]
        }
    )

    result = claim_gate.evaluate_claims(**parsed)
    row = result["claims"][0]

    # Claim Rupture Gate expresses the honest BLOCKED semantic as
    # UNKNOWN + ABSTAIN. It must not raise, approve, or silently disappear.
    assert row["state"] == claim_gate.UNKNOWN
    assert row["abstain_required"] is True
    assert "RG-001" in row["rubric_codes"]
    assert result["overall_state"] == claim_gate.UNKNOWN
    assert result["gate_outcome"] == "ABSTAIN"
