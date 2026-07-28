"""Runtime truth-layer tests for the public Forge family wall."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "a11oy_forge_family.py"
SPEC = importlib.util.spec_from_file_location("a11oy_forge_family", MODULE_PATH)
assert SPEC and SPEC.loader
FORGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FORGE)

PUBLIC_HEAD = "2e62cb5f8e6a17052da532305a467861094a2109"


def _signed_files() -> dict[str, bytes]:
    private_key = Ed25519PrivateKey.generate()
    spki = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    spki_b64 = base64.b64encode(spki).decode("ascii")
    key_id = hashlib.sha256(spki).hexdigest()[:16]
    owner = {
        "algo": "ed25519",
        "keyId": key_id,
        "publicKeySpkiBase64": spki_b64,
    }

    training_payload = {
        "kind": "training-receipt",
        "keyId": key_id,
        "baseModel": "Qwen/Qwen2.5-1.5B-Instruct",
        "trainedAt": "2026-07-01T00:00:00Z",
        "finalTrainLoss": 0.25,
    }
    training_canonical = FORGE._canonical(training_payload)
    training = {
        "payload": training_payload,
        "canonical": training_canonical,
        "signatureBase64": base64.b64encode(
            private_key.sign(training_canonical.encode("utf-8"))
        ).decode("ascii"),
        "publicKeySpkiBase64": spki_b64,
        "keyId": key_id,
    }

    evaluation_payload = {
        "kind": "evaluation-receipt",
        "keyId": key_id,
        "evaluatedAt": "2026-07-02T00:00:00Z",
        "trainingReceiptSha256": hashlib.sha256(
            training_canonical.encode("utf-8")
        ).hexdigest(),
        "planValid": 6,
        "planTotal": 6,
        "groundingCorrect": 6,
        "groundingTotal": 6,
        "abstainCorrect": 2,
        "abstainTotal": 6,
        "hallucinatedCitationCount": 0,
    }
    evaluation_canonical = FORGE._canonical(evaluation_payload)
    evaluation = {
        "payload": evaluation_payload,
        "canonical": evaluation_canonical,
        "signatureBase64": base64.b64encode(
            private_key.sign(evaluation_canonical.encode("utf-8"))
        ).decode("ascii"),
        "publicKeySpkiBase64": spki_b64,
        "keyId": key_id,
    }
    return {
        "owner_pubkey.json": json.dumps(owner).encode("utf-8"),
        "training_receipt.signed.json": json.dumps(training).encode("utf-8"),
        "eval_receipt.signed.json": json.dumps(evaluation).encode("utf-8"),
    }


def _receipt_agent_config() -> dict:
    return next(
        config for config in FORGE._MODELS if config["model"] == "receiptagent"
    )


def _khipu_config() -> dict:
    return next(config for config in FORGE._MODELS if config["model"] == "khipu")


def test_receipt_agent_exposes_distinct_verified_truth_layers(monkeypatch):
    monkeypatch.delenv("A11OY_OWNER_KEYID", raising=False)
    band = FORGE._band_for_model(
        _receipt_agent_config(),
        _signed_files(),
        0.0,
        PUBLIC_HEAD,
    )

    assert band["verified"] is True
    assert band["profileState"] == FORGE._RECONCILIATION_STATE
    layers = band["verificationLayers"]
    assert layers["receiptSignatureValidity"]["verified"] is True
    assert layers["exactQualifiedArtifactBinding"]["verified"] is True
    assert layers["currentPublicHeadEquivalence"] == {
        "verified": True,
        "state": "INFERENCE_BEARING_BLOBS_EQUIVALENT_TO_QUALIFIED_REVISION",
        "observedHead": PUBLIC_HEAD,
        "reconciledHead": PUBLIC_HEAD,
        "failClosedOnHeadChange": True,
    }
    assert layers["promotion"] == {
        "authorized": False,
        "state": "NOT_PROMOTED",
    }


def test_khipu_artifact_state_is_not_reinterpreted_by_receipt_agent_relock(
    monkeypatch,
):
    monkeypatch.delenv("A11OY_KHIPU_OWNER_KEYID", raising=False)
    band = FORGE._band_for_model(_khipu_config(), _signed_files(), 0.0)

    assert band["verified"] is True
    assert band["profileState"] is None
    layers = band["verificationLayers"]
    assert layers["exactQualifiedArtifactBinding"] == {
        "verified": None,
        "state": "NOT_EVALUATED_FOR_THIS_PROFILE",
    }
    assert layers["currentPublicHeadEquivalence"]["verified"] is None


def test_receipt_agent_public_head_drift_fails_closed_without_erasing_signatures(
    monkeypatch,
):
    monkeypatch.delenv("A11OY_OWNER_KEYID", raising=False)
    changed_head = "0" * 40
    band = FORGE._band_for_model(
        _receipt_agent_config(),
        _signed_files(),
        0.0,
        changed_head,
    )

    assert band["verified"] is False
    assert band["profileState"] == "ARTIFACT_RECONCILIATION_FAILED_CLOSED"
    layers = band["verificationLayers"]
    assert layers["receiptSignatureValidity"]["verified"] is True
    assert layers["exactQualifiedArtifactBinding"]["verified"] is True
    assert layers["currentPublicHeadEquivalence"]["verified"] is False
    assert (
        layers["currentPublicHeadEquivalence"]["state"]
        == "PUBLIC_HEAD_CHANGED_RECONCILIATION_REQUIRED"
    )
    assert "ARTIFACT_RECONCILIATION_FAILED_CLOSED" in band["status"]


def test_reconciliation_self_digest_tamper_is_a_runtime_refusal(
    monkeypatch,
    tmp_path,
):
    tampered = json.loads(FORGE._RECONCILIATION_PATH.read_text(encoding="utf-8"))
    tampered["authorization"]["promoted"] = True
    path = tmp_path / "tampered-reconciliation.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    monkeypatch.setattr(FORGE, "_RECONCILIATION_PATH", path)

    with pytest.raises(ValueError, match="self-digest mismatch"):
        FORGE._load_receipt_agent_reconciliation()


def test_public_head_fetch_requires_lowercase_hex():
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"sha": "Z" * 40}

    class FakeClient:
        async def get(self, _url):
            return FakeResponse()

    with pytest.raises(ValueError, match="lowercase hex head"):
        asyncio.run(FORGE._fetch_public_head(FakeClient(), "owner/repository"))
