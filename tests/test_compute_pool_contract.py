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


def _write_signed(tmp_path, monkeypatch, payload: dict, filename: str = "receipt.dsse.json", private=None):
    private = private or ec.generate_private_key(ec.SECP256R1())
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
    (tmp_path / filename).write_text(json.dumps(envelope), encoding="utf-8")
    return private


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


def test_future_dated_receipt_does_not_mask_fresh_one(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    fresh = _payload(now, serving=True)
    private = _write_signed(tmp_path, monkeypatch, fresh, "a-fresh.dsse.json")
    _write_signed(tmp_path, monkeypatch, _payload(now + timedelta(hours=1), serving=True), "b-future.dsse.json", private)
    node = contract.build_compute_pool_contract(_pool(), now)["nodes"][0]
    assert node["state"] == "SERVING"
    assert node["ready"] is True
    assert node["inference_receipt"]["observed_at"] == fresh["observed_at"]


def test_future_dated_receipt_alone_only_proves_discovery(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _write_signed(tmp_path, monkeypatch, _payload(now + timedelta(hours=1), serving=True))
    node = contract.build_compute_pool_contract(_pool(), now)["nodes"][0]
    assert node["state"] == "DISCOVERED"
    assert node["ready"] is False
    assert node["inference_receipt"]["reason"] == "verified receipt is stale or future-dated"


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


_KEY_B = "a11oy-pool-attester-node-b-v1"


def _two_node_pool() -> dict:
    return {"nodes": [
        {"name": name, "kind": "sovereign-gpu", "sovereign": True, "endpoint": "redacted", "reachable": True}
        for name in ("node-a", "node-b")
    ]}


def _public(private) -> tuple:
    public = private.public_key()
    pem = public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    der = public.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return pem, hashlib.sha256(der).hexdigest()


def _root_entry(private, keyid: str = _KEY_B, node_ids=("node-b",)) -> dict:
    pem, pin = _public(private)
    return {"keyid": keyid, "public_key_pem": pem, "sha256": pin, "node_ids": list(node_ids)}


def _place(tmp_path, private, keyid: str, node_id: str, now: datetime, filename: str) -> None:
    payload = _payload(now, serving=True)
    payload["node_id"] = node_id
    body = szl_dsse.canonical_json(payload)
    signature = private.sign(szl_dsse.pae(contract.RECEIPT_PAYLOAD_TYPE, body), ec.ECDSA(hashes.SHA256()))
    envelope = {
        "payloadType": contract.RECEIPT_PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [{"keyid": keyid, "sig": base64.b64encode(signature).decode("ascii")}],
    }
    (tmp_path / filename).write_text(json.dumps(envelope), encoding="utf-8")


@pytest.fixture()
def two_keys(tmp_path, monkeypatch):
    key_a = ec.generate_private_key(ec.SECP256R1())
    key_b = ec.generate_private_key(ec.SECP256R1())
    pem, pin = _public(key_a)
    monkeypatch.setenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_PEM", pem)
    monkeypatch.setenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_SHA256", pin)
    monkeypatch.setenv("A11OY_COMPUTE_POOL_RECEIPT_DIR", str(tmp_path))
    monkeypatch.setenv("A11OY_POOL_RECEIPT_TRUST_ROOTS", json.dumps([_root_entry(key_b)]))
    return key_a, key_b


def _states(now: datetime) -> dict:
    result = contract.build_compute_pool_contract(_two_node_pool(), now)
    return {node["node_id"]: node for node in result["nodes"]} | {"counts": result["counts"]}


def test_second_attester_key_qualifies_only_its_bound_node(tmp_path, two_keys):
    _, key_b = two_keys
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _place(tmp_path, key_b, _KEY_B, "node-b", now, "b.dsse.json")
    states = _states(now)
    assert states["node-b"]["state"] == "SERVING" and states["node-b"]["ready"] is True
    assert states["node-a"]["ready"] is False
    assert states["counts"]["ready"] == 1


def test_bound_key_cannot_attest_another_node(tmp_path, two_keys):
    _, key_b = two_keys
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _place(tmp_path, key_b, _KEY_B, "node-a", now, "a.dsse.json")
    states = _states(now)
    assert states["node-a"]["ready"] is False
    assert states["node-a"]["inference_receipt"]["evidence_class"] == "UNAVAILABLE"
    assert states["counts"]["ready"] == 0


def test_two_nodes_two_keys_both_serving(tmp_path, two_keys):
    key_a, key_b = two_keys
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _place(tmp_path, key_a, "a11oy-pool-attester-v1", "node-a", now, "a.dsse.json")
    _place(tmp_path, key_b, _KEY_B, "node-b", now, "b.dsse.json")
    counts = _states(now)["counts"]
    assert counts["ready"] == 2
    assert counts["serving"] == 2


def test_signature_keyid_selects_key_no_cross_key_fallback(tmp_path, two_keys):
    key_a, key_b = two_keys
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _place(tmp_path, key_b, "a11oy-pool-attester-v1", "node-b", now, "b-as-a.dsse.json")
    _place(tmp_path, key_a, _KEY_B, "node-b", now, "a-as-b.dsse.json")
    _place(tmp_path, key_b, "a11oy-pool-attester-v1", "node-a", now, "b-as-a-2.dsse.json")
    states = _states(now)
    assert states["counts"]["ready"] == 0
    assert states["node-a"]["inference_receipt"]["verified"] is False
    assert states["node-b"]["inference_receipt"]["verified"] is False


def test_map_absent_legacy_key_still_attests_any_declared_node(tmp_path, two_keys, monkeypatch):
    key_a, key_b = two_keys
    monkeypatch.delenv("A11OY_POOL_RECEIPT_TRUST_ROOTS")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _place(tmp_path, key_a, "a11oy-pool-attester-v1", "node-a", now, "a.dsse.json")
    _place(tmp_path, key_a, "a11oy-pool-attester-v1", "node-b", now, "b.dsse.json")
    assert _states(now)["counts"]["ready"] == 2
    (tmp_path / "b.dsse.json").unlink()
    _place(tmp_path, key_b, _KEY_B, "node-b", now, "b.dsse.json")
    assert _states(now)["counts"]["ready"] == 1


def test_trust_root_map_without_legacy_key_binds_every_key(tmp_path, two_keys, monkeypatch):
    key_a, key_b = two_keys
    monkeypatch.delenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_PEM")
    monkeypatch.delenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_SHA256")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _place(tmp_path, key_a, "a11oy-pool-attester-v1", "node-a", now, "a.dsse.json")
    _place(tmp_path, key_b, _KEY_B, "node-b", now, "b.dsse.json")
    states = _states(now)
    assert states["node-b"]["ready"] is True
    assert states["node-a"]["ready"] is False


def _malformed_maps(key_a, key_b) -> dict:
    good = _root_entry(key_b)
    other = ec.generate_private_key(ec.SECP256R1())
    p384_pem, p384_pin = _public(ec.generate_private_key(ec.SECP384R1()))
    return {
        "bad_json": "[{",
        "non_list": json.dumps({"roots": [good]}),
        "empty_list": "[]",
        "non_object_entry": json.dumps(["x"]),
        "too_many": json.dumps([
            _root_entry(ec.generate_private_key(ec.SECP256R1()), f"a11oy-pool-attester-n{i}-v1") for i in range(9)
        ]),
        "extra_key": json.dumps([{**good, "note": "x"}]),
        "missing_key": json.dumps([{k: v for k, v in good.items() if k != "node_ids"}]),
        "pin_mismatch": json.dumps([{**good, "sha256": "0" * 64}]),
        "not_p256": json.dumps([{**good, "public_key_pem": p384_pem, "sha256": p384_pin}]),
        "legacy_keyid": json.dumps([{**good, "keyid": "a11oy-pool-attester-v1"}]),
        "bad_keyid": json.dumps([{**good, "keyid": "some-other-key"}]),
        "duplicate_keyid": json.dumps([good, _root_entry(other)]),
        "duplicate_public_key": json.dumps([good, _root_entry(key_b, "a11oy-pool-attester-node-c-v1")]),
        "duplicate_of_legacy_key": json.dumps([_root_entry(key_a)]),
        "empty_node_ids": json.dumps([{**good, "node_ids": []}]),
        "blank_node_id": json.dumps([{**good, "node_ids": [" "]}]),
        "non_string_node_id": json.dumps([{**good, "node_ids": [7]}]),
        "too_many_node_ids": json.dumps([{**good, "node_ids": [f"n{i}" for i in range(17)]}]),
    }


@pytest.mark.parametrize("case", [
    "bad_json", "non_list", "empty_list", "non_object_entry", "too_many", "extra_key", "missing_key",
    "pin_mismatch", "not_p256", "legacy_keyid", "bad_keyid", "duplicate_keyid", "duplicate_public_key",
    "duplicate_of_legacy_key", "empty_node_ids", "blank_node_id", "non_string_node_id", "too_many_node_ids",
])
def test_malformed_trust_root_map_fails_closed(tmp_path, two_keys, monkeypatch, case):
    key_a, key_b = two_keys
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _place(tmp_path, key_a, "a11oy-pool-attester-v1", "node-a", now, "a.dsse.json")
    _place(tmp_path, key_b, _KEY_B, "node-b", now, "b.dsse.json")
    assert _states(now)["counts"]["ready"] == 2
    monkeypatch.setenv("A11OY_POOL_RECEIPT_TRUST_ROOTS", _malformed_maps(key_a, key_b)[case])
    states = _states(now)
    assert states["counts"]["ready"] == 0
    assert states["node-a"]["inference_receipt"]["verified"] is False


def test_valid_map_with_broken_legacy_pin_fails_closed(tmp_path, two_keys, monkeypatch):
    _, key_b = two_keys
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _place(tmp_path, key_b, _KEY_B, "node-b", now, "b.dsse.json")
    monkeypatch.setenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_SHA256", "0" * 64)
    assert _states(now)["counts"]["ready"] == 0
