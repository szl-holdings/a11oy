from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

import szl_compute_pool_contract as contract
import szl_dsse


def _pool(reachable: bool = True) -> dict:
    return {
        "cached_at": "2026-07-16T20:00:00Z",
        "nodes": [{
            "name": "local-test", "kind": "sovereign-gpu", "sovereign": True,
            "endpoint": "sovereign node - private tailnet", "reachable": reachable,
        }],
    }


def _payload(now: datetime, *, serving: bool = False) -> dict:
    return {
        "schema_version": contract.RECEIPT_SCHEMA,
        "node_id": "local-test",
        "model_id": "szl-test:exact",
        "model_digest_sha256": "a" * 64,
        "observed_at": now.isoformat().replace("+00:00", "Z"),
        "request_sha256": "b" * 64,
        "response_sha256": "c" * 64,
        "duration_ms": 41.5,
        "success": True,
        "serving": serving,
        "bounds": {"timeout_ms": 5000, "max_input_tokens": 64, "max_output_tokens": 32},
        "issuer": "a11oy-pool-attester",
        "audience": "a11oy-compute-pool",
        "predicate_type": "szl.compute-pool.inference-qualification/v1",
        "measurement_contract": "szl.compute-pool.measurement-contract/v1",
    }


def _write_signed(tmp_path, monkeypatch, payload: dict) -> None:
    private = ec.generate_private_key(ec.SECP256R1())
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    public_der = private.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_PEM", public_pem)
    monkeypatch.setenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_SHA256", hashlib.sha256(public_der).hexdigest())
    monkeypatch.setenv("A11OY_COMPUTE_POOL_RECEIPT_DIR", str(tmp_path))
    body = szl_dsse.canonical_json(payload)
    signature = private.sign(
        szl_dsse.pae(contract.RECEIPT_PAYLOAD_TYPE, body),
        ec.ECDSA(hashes.SHA256()),
    )
    envelope = {
        "payloadType": contract.RECEIPT_PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [{
            "keyid": "a11oy-pool-attester-v1",
            "sig": base64.b64encode(signature).decode("ascii"),
        }],
    }
    (tmp_path / "receipt.dsse.json").write_text(json.dumps(envelope), encoding="utf-8")


def test_reachability_alone_is_never_ready(monkeypatch):
    monkeypatch.delenv("A11OY_COMPUTE_POOL_RECEIPT_DIR", raising=False)
    monkeypatch.delenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_PEM", raising=False)
    monkeypatch.delenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_SHA256", raising=False)
    result = contract.build_compute_pool_contract(_pool(), datetime(2026, 7, 16, 20, 0, tzinfo=timezone.utc))
    assert result["nodes"][0]["state"] == "REACHABLE"
    assert result["nodes"][0]["ready"] is False
    assert result["counts"]["ready"] == 0


@pytest.mark.parametrize("serving,expected", [(False, "QUALIFIED"), (True, "SERVING")])
def test_fresh_signed_bounded_receipt_is_ready(tmp_path, monkeypatch, serving, expected):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _write_signed(tmp_path, monkeypatch, _payload(now, serving=serving))
    result = contract.build_compute_pool_contract(_pool(), now)
    node = result["nodes"][0]
    assert node["state"] == expected
    assert node["ready"] is True
    assert node["inference_receipt"]["verified"] is True
    assert node["inference_receipt"]["receipt_sha256"]


def test_stale_signed_receipt_only_proves_discovery(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _write_signed(tmp_path, monkeypatch, _payload(now - timedelta(hours=2), serving=True))
    result = contract.build_compute_pool_contract(_pool(), now)
    assert result["nodes"][0]["state"] == "DISCOVERED"
    assert result["nodes"][0]["ready"] is False


def test_unsigned_or_content_bearing_receipt_cannot_promote(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    payload = _payload(now, serving=True)
    payload["raw_prompt"] = "must never enter a pool receipt"
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    envelope = {
        "payloadType": contract.RECEIPT_PAYLOAD_TYPE,
        "payload": __import__("base64").b64encode(body).decode(),
        "signatures": [],
    }
    monkeypatch.setenv("A11OY_COMPUTE_POOL_RECEIPT_DIR", str(tmp_path))
    (tmp_path / "bad.dsse.json").write_text(json.dumps(envelope), encoding="utf-8")
    result = contract.build_compute_pool_contract(_pool(), now)
    assert result["nodes"][0]["state"] == "REACHABLE"
    assert result["nodes"][0]["ready"] is False


def test_non_object_envelope_is_ignored_not_raised(tmp_path, monkeypatch):
    private = ec.generate_private_key(ec.SECP256R1())
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    public_der = private.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_PEM", public_pem)
    monkeypatch.setenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_SHA256", hashlib.sha256(public_der).hexdigest())
    monkeypatch.setenv("A11OY_COMPUTE_POOL_RECEIPT_DIR", str(tmp_path))
    (tmp_path / "receipt.dsse.json").write_text("[]", encoding="utf-8")
    result = contract.build_compute_pool_contract(_pool())
    assert result["nodes"][0]["state"] == "REACHABLE"
    assert result["nodes"][0]["ready"] is False


def test_wrong_or_missing_pool_trust_root_cannot_promote(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _write_signed(tmp_path, monkeypatch, _payload(now))
    monkeypatch.setenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_SHA256", "0" * 64)
    assert contract.build_compute_pool_contract(_pool(), now)["nodes"][0]["ready"] is False
    monkeypatch.delenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_PEM")
    assert contract.build_compute_pool_contract(_pool(), now)["nodes"][0]["ready"] is False


def test_invalid_and_duplicate_node_descriptors_are_excluded(monkeypatch):
    monkeypatch.delenv("A11OY_COMPUTE_POOL_RECEIPT_DIR", raising=False)
    pool = _pool()
    pool["nodes"] = [
        {},
        {"name": "valid", "endpoint": "redacted", "reachable": True},
        {"name": "valid", "endpoint": "redacted", "reachable": True},
        "not-a-node",
    ]
    result = contract.build_compute_pool_contract(pool)
    assert [node["node_id"] for node in result["nodes"]] == ["valid"]


def test_static_schema_accepts_generated_contract(monkeypatch):
    jsonschema = pytest.importorskip("jsonschema")
    monkeypatch.delenv("A11OY_COMPUTE_POOL_RECEIPT_DIR", raising=False)
    schema = json.loads((Path(__file__).parents[1] / "schemas/compute-pool/compute-pool.v1.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(contract.build_compute_pool_contract(_pool()))
