# SPDX-License-Identifier: Apache-2.0
"""Focused admission-gate edge cases requested by issue #1626."""
from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

import szl_claim_rupture_gate as claim_gate
import szl_confattest as confattest
import szl_dsse as dsse
import szl_public_verify as public_verify


def _valid_untrusted_envelope() -> tuple[dict[str, object], ec.EllipticCurvePublicKey]:
    """Create a correctly signed DSSE envelope whose signer is not trusted."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    key_id = dsse._key_id(public_key)
    assert key_id not in dsse.TRUSTED_KEY_IDS

    payload_bytes = dsse.canonical_json_bytes(
        {"schema": "szl.test/unknown-signer", "claim": "signature is valid"}
    )
    pae = dsse._pae(dsse.ENV_PAYLOAD_TYPE, payload_bytes)
    signature = private_key.sign(pae, ec.ECDSA(hashes.SHA256()))

    # Establish that the signature itself is cryptographically valid before the
    # repository trust policy rejects the unknown key identity.
    public_key.verify(signature, pae, ec.ECDSA(hashes.SHA256()))
    return (
        {
            "payloadType": dsse.ENV_PAYLOAD_TYPE,
            "payload": dsse.b64url(payload_bytes),
            "signatures": [{"keyid": key_id, "sig": dsse.b64url(signature)}],
        },
        public_key,
    )


def test_valid_signature_from_unknown_signer_is_denied() -> None:
    envelope, _ = _valid_untrusted_envelope()

    verified, reason = dsse.verify_envelope(envelope)

    assert verified is False
    assert reason == "key_id unknown"


def test_corrupted_subject_digest_is_denied_after_signature_gate(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "artifact.bin"
    target.write_bytes(b"actual immutable artifact bytes")
    statement = {
        "subject": [
            {
                "name": target.name,
                "digest": {"sha256": "0" * 64},
            }
        ]
    }
    envelope = {
        "payload": dsse.b64url(dsse.canonical_json_bytes(statement)),
    }
    target.with_suffix(target.suffix + ".dsse.json").write_text(
        json.dumps(envelope), encoding="utf-8"
    )

    # Isolate the subject-binding boundary: even an envelope admitted by the
    # signature verifier cannot authorize bytes whose digest does not match.
    monkeypatch.setattr(public_verify, "verify_envelope", lambda value: (True, "ok"))
    with pytest.raises(AssertionError, match="digest mismatch"):
        public_verify._check_digest(str(target))


def test_trust_score_at_the_ceiling_never_exceeds_point_97() -> None:
    assert confattest.TRUST_CEIL == pytest.approx(0.97)
    assert confattest._clamp(
        confattest.TRUST_CEIL, 0.0, confattest.TRUST_CEIL
    ) == pytest.approx(0.97)
    assert confattest._clamp(1.0, 0.0, confattest.TRUST_CEIL) == pytest.approx(
        0.97
    )

    axes = confattest._lambda_axes(
        "f" * 64,
        "r" * 64,
    )
    assert axes
    assert all(0.0 <= value <= confattest.TRUST_CEIL for value in axes.values())


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
