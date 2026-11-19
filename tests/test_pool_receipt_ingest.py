from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

import szl_compute_pool_contract as contract
import szl_dsse
import szl_pool_receipt_ingest as ingest

starlette_testclient = pytest.importorskip("starlette.testclient")
TestClient = starlette_testclient.TestClient

_TOKEN = "test-ingest-secret-not-real"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv(ingest.INGEST_TOKEN_ENV, _TOKEN)
    app = pytest.importorskip("fastapi").FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    ingest.register(app, ns="a11oy")
    assert [getattr(item, "path", None) for item in app.router.routes] == [
        "/api/a11oy/v1/compute-pool/receipts"
    ]
    return TestClient(app)


def _payload(now: datetime, *, node_id: str = "omen-betterwithage") -> dict:
    return {
        "schema_version": contract.RECEIPT_SCHEMA,
        "node_id": node_id,
        "model_id": "llama3.1:8b",
        "model_digest_sha256": "a" * 64,
        "observed_at": now.isoformat().replace("+00:00", "Z"),
        "request_sha256": "b" * 64,
        "response_sha256": "c" * 64,
        "duration_ms": 321.5,
        "success": True,
        "serving": True,
        "bounds": {"timeout_ms": 10000, "max_input_tokens": 128, "max_output_tokens": 32},
        "issuer": "a11oy-pool-attester",
        "audience": "a11oy-compute-pool",
        "predicate_type": "szl.compute-pool.inference-qualification/v1",
        "measurement_contract": "szl.compute-pool.measurement-contract/v1",
    }


def _envelope(private_key, payload: dict, keyid: str = "a11oy-pool-attester-v1") -> bytes:
    body = szl_dsse.canonical_json(payload)
    signature = private_key.sign(
        szl_dsse.pae(contract.RECEIPT_PAYLOAD_TYPE, body),
        ec.ECDSA(hashes.SHA256()),
    )
    envelope = {
        "payloadType": contract.RECEIPT_PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [{"keyid": keyid, "sig": base64.b64encode(signature).decode("ascii")}],
    }
    return json.dumps(envelope).encode("utf-8")


@pytest.fixture()
def trust_root(monkeypatch, tmp_path):
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
    return private, tmp_path


def _post(client, raw: bytes, *, token: str = _TOKEN):
    return client.post(
        "/api/a11oy/v1/compute-pool/receipts",
        content=raw,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )


def test_no_ingest_token_configured_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv(ingest.INGEST_TOKEN_ENV, raising=False)
    app = pytest.importorskip("fastapi").FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    ingest.register(app, ns="a11oy")
    raw = json.dumps({"payloadType": contract.RECEIPT_PAYLOAD_TYPE, "payload": "", "signatures": []}).encode()
    response = TestClient(app).post("/api/a11oy/v1/compute-pool/receipts", content=raw)
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"


def test_missing_or_wrong_bearer_is_refused(client, trust_root):
    private, _ = trust_root
    raw = _envelope(private, _payload(datetime.now(timezone.utc)))
    assert _post(client, raw, token="wrong").status_code == 403
    wrong_scheme = client.post(
        "/api/a11oy/v1/compute-pool/receipts",
        content=raw,
        headers={"Authorization": f"Basic {_TOKEN}"},
    )
    assert wrong_scheme.status_code == 403


def test_unconfigured_trust_root_never_accepts(client, monkeypatch, trust_root):
    private, _ = trust_root
    monkeypatch.delenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_PEM")
    raw = _envelope(private, _payload(datetime.now(timezone.utc)))
    assert _post(client, raw).status_code == 503


def test_pinned_sha_mismatch_never_accepts(client, monkeypatch, trust_root):
    private, _ = trust_root
    monkeypatch.setenv("A11OY_POOL_RECEIPT_PUBLIC_KEY_SHA256", "0" * 64)
    raw = _envelope(private, _payload(datetime.now(timezone.utc)))
    assert _post(client, raw).status_code == 503


def test_verified_receipt_is_stored_byte_exact_and_idempotent(client, trust_root):
    private, root = trust_root
    raw = _envelope(private, _payload(datetime.now(timezone.utc)))
    response = _post(client, raw)
    assert response.status_code == 202
    body = response.json()
    assert body["accepted"] is True
    assert body["node_id"] == "omen-betterwithage"
    assert body["receipt_sha256"] == hashlib.sha256(raw).hexdigest()
    stored = root / body["stored_as"]
    assert stored.read_bytes() == raw
    again = _post(client, raw)
    assert again.status_code == 202
    assert again.json()["stored_as"] == body["stored_as"]
    assert len(list(root.glob("*.dsse.json"))) == 1
    # And the standing contract verifier promotes the node from the stored bytes.
    pool = {"nodes": [{"name": "omen-betterwithage", "kind": "sovereign-gpu", "sovereign": True,
                       "endpoint": "sovereign node - private tailnet", "reachable": True}]}
    promoted = contract.build_compute_pool_contract(pool, datetime.now(timezone.utc))
    assert promoted["nodes"][0]["state"] == "SERVING"
    assert promoted["nodes"][0]["ready"] is True


def test_bad_signature_is_refused_without_storage(client, trust_root):
    private, root = trust_root
    other = ec.generate_private_key(ec.SECP256R1())
    assert private.public_key() != other.public_key()
    raw = _envelope(other, _payload(datetime.now(timezone.utc)))
    assert _post(client, raw).status_code == 422
    assert list(root.glob("*.dsse.json")) == []


def test_content_bearing_payload_is_refused(client, trust_root):
    private, root = trust_root
    payload = _payload(datetime.now(timezone.utc))
    payload["raw_prompt"] = "must never enter a pool receipt"
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    forged = {
        "payloadType": contract.RECEIPT_PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [],
    }
    raw = json.dumps(forged).encode()
    assert _post(client, raw).status_code == 422
    assert list(root.glob("*.dsse.json")) == []


def test_oversized_envelope_is_refused(client, trust_root):
    private, _ = trust_root
    raw = _envelope(private, _payload(datetime.now(timezone.utc)))
    padded = json.dumps(
        {"payloadType": contract.RECEIPT_PAYLOAD_TYPE, "payload": "x" * (ingest._MAX_ENVELOPE_BYTES + 64), "signatures": []}
    ).encode()
    assert len(padded) > ingest._MAX_ENVELOPE_BYTES
    response = client.post(
        "/api/a11oy/v1/compute-pool/receipts",
        content=padded,
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert response.status_code == 413


def test_receipt_dir_unconfigured_fails_closed(client, monkeypatch, trust_root):
    private, _ = trust_root
    monkeypatch.delenv("A11OY_COMPUTE_POOL_RECEIPT_DIR")
    raw = _envelope(private, _payload(datetime.now(timezone.utc)))
    assert _post(client, raw).status_code == 503


def test_storage_is_pruned_to_the_contract_selection_window(client, trust_root):
    private, root = trust_root
    base = datetime.now(timezone.utc)
    for index in range(contract._MAX_RECEIPTS + 6):
        payload = _payload(base.fromtimestamp(base.timestamp() - (contract._MAX_RECEIPTS + 6 - index), tz=timezone.utc))
        payload["model_digest_sha256"] = f"{index:064x}"
        raw = _envelope(private, payload)
        response = _post(client, raw)
        assert response.status_code == 202
    names = [item.name for item in root.glob("*.dsse.json")]
    assert len(names) == contract._MAX_RECEIPTS
    assert all(ingest._RECEIPT_NAME_RE.match(name) for name in names)


def test_future_dated_receipt_is_refused_without_storage(client, trust_root):
    private, root = trust_root
    raw = _envelope(private, _payload(datetime.now(timezone.utc) + timedelta(hours=1)))
    response = _post(client, raw)
    assert response.status_code == 422
    assert response.json()["error"] == "receipt outside freshness window"
    assert list(root.iterdir()) == []


def test_stale_receipt_is_refused_without_storage(client, trust_root):
    private, root = trust_root
    max_age = contract._freshness_seconds()
    raw = _envelope(private, _payload(datetime.now(timezone.utc) - timedelta(seconds=max_age + 60)))
    response = _post(client, raw)
    assert response.status_code == 422
    assert response.json()["error"] == "receipt outside freshness window"
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("offset_s", [10, -(contract._freshness_seconds() - 30)])
def test_receipt_inside_freshness_window_is_accepted(client, trust_root, offset_s):
    private, root = trust_root
    raw = _envelope(private, _payload(datetime.now(timezone.utc) + timedelta(seconds=offset_s)))
    assert _post(client, raw).status_code == 202
    assert len(list(root.glob("*.dsse.json"))) == 1


def test_refused_freshness_post_leaves_stored_receipt_untouched(client, trust_root):
    private, root = trust_root
    good = _envelope(private, _payload(datetime.now(timezone.utc)))
    stored = root / _post(client, good).json()["stored_as"]
    future = _envelope(private, _payload(datetime.now(timezone.utc) + timedelta(hours=1)))
    assert _post(client, future).status_code == 422
    assert [item.name for item in root.iterdir()] == [stored.name]
    assert stored.read_bytes() == good


_KEY_B = "a11oy-pool-attester-rtx-v1"


@pytest.fixture()
def second_root(monkeypatch, trust_root):
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key()
    pem = public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    der = public.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    entry = {
        "keyid": _KEY_B, "public_key_pem": pem, "sha256": hashlib.sha256(der).hexdigest(),
        "node_ids": ["rtx-betterwithage"],
    }
    monkeypatch.setenv("A11OY_POOL_RECEIPT_TRUST_ROOTS", json.dumps([entry]))
    return private, entry


def test_second_attester_key_is_accepted_for_its_bound_node(client, trust_root, second_root):
    legacy, root = trust_root
    private, _ = second_root
    raw = _envelope(private, _payload(datetime.now(timezone.utc), node_id="rtx-betterwithage"), _KEY_B)
    response = _post(client, raw)
    assert response.status_code == 202
    assert response.json()["node_id"] == "rtx-betterwithage"
    assert _post(client, _envelope(legacy, _payload(datetime.now(timezone.utc)))).status_code == 202
    assert len(list(root.glob("*.dsse.json"))) == 2


def test_second_attester_key_is_refused_for_an_unbound_node(client, trust_root, second_root):
    _, root = trust_root
    private, _ = second_root
    raw = _envelope(private, _payload(datetime.now(timezone.utc), node_id="omen-betterwithage"), _KEY_B)
    assert _post(client, raw).status_code == 422
    assert list(root.iterdir()) == []


def test_second_attester_key_without_map_is_refused(client, monkeypatch, trust_root, second_root):
    _, root = trust_root
    private, _ = second_root
    monkeypatch.delenv("A11OY_POOL_RECEIPT_TRUST_ROOTS")
    raw = _envelope(private, _payload(datetime.now(timezone.utc), node_id="rtx-betterwithage"), _KEY_B)
    assert _post(client, raw).status_code == 422
    assert list(root.iterdir()) == []


def test_malformed_trust_root_map_refuses_even_the_legacy_key(client, monkeypatch, trust_root, second_root):
    legacy, root = trust_root
    _, entry = second_root
    monkeypatch.setenv("A11OY_POOL_RECEIPT_TRUST_ROOTS", json.dumps([{**entry, "sha256": "0" * 64}]))
    assert _post(client, _envelope(legacy, _payload(datetime.now(timezone.utc)))).status_code == 503
    assert list(root.iterdir()) == []
