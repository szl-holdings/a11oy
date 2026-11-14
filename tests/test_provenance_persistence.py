# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Managed provenance restart, retained-byte acknowledgment and refusal contracts."""
import asyncio
import base64
import hashlib
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_state_store as ss
import a11oy_signing_key
import szl_be_hardening
import szl_dsse
import szl_operator_auth as auth
import szl_provenance as provenance
from tests.state_store_support import FakeClock, FakeHeadBackend, replica, make_db

OPERATOR = "synthetic-provenance-operator-not-real"
SIGN = "/api/a11oy/khipu/sign"
LEDGER = "/api/a11oy/khipu/ledger"

def app_client():
    app = FastAPI()
    auth.install_gate(app)
    ss.register(app)
    provenance.register_provenance(app, "a11oy")
    return app, TestClient(app)

@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("A11OY_STATE_STORE", "v2")
    monkeypatch.setenv(auth.OPERATOR_KEY_ENV, OPERATOR)
    monkeypatch.setenv("A11OY_RECEIPT_KEY_DIR", str(tmp_path / "keys"))
    for name in szl_dsse.PRIVATE_KEY_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("A11OY_RECEIPT_KEY_PEM", raising=False)
    monkeypatch.delenv("A11OY_RECEIPT_KEY_PATH", raising=False)
    monkeypatch.setattr(a11oy_signing_key, "_KEY_CACHE", {})
    monkeypatch.setattr(szl_dsse, "_RUNTIME_PUBLIC_KEYS", {})
    monkeypatch.setattr(szl_dsse, "_ACTIVE_RUNTIME_KEYID", None)
    key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode("ascii"))
    objects = ss.LocalDirObjectStore(tmp_path / "objects")
    backend, clock = FakeHeadBackend(), FakeClock()
    writer = replica(tmp_path, "writer", objects, backend, clock)
    writer.boot()
    writer.heartbeat_once()
    # The existing DurableKhipu bootstrap owns creation of this shared database.
    make_db(writer.local_path("khipu"), 2)
    monkeypatch.setattr(ss, "_ACTIVE", writer)
    app, client = app_client()
    yield dict(root=tmp_path, writer=writer, objects=objects, backend=backend,
               clock=clock, key=key, app=app, client=client, monkeypatch=monkeypatch)
    client.close()
    writer._close_watchers()

def sign(world, nonce="synthetic"):
    return world["client"].post(SIGN, headers={"Authorization": "Bearer " + OPERATOR},
                                json={"receipt": {"schema": "test/proof", "nonce": nonce}})

def verify_signature(world, envelope):
    body = base64.b64decode(envelope["payload"])
    typ = envelope["payloadType"].encode()
    message = b"DSSEv1 " + str(len(typ)).encode() + b" " + typ + b" " + str(len(body)).encode() + b" " + body
    world["key"].public_key().verify(base64.b64decode(envelope["signatures"][0]["sig"]),
                                    message, ec.ECDSA(hashes.SHA256()))

def snapshot_file(world):
    return world["writer"].local_path("khipu")

def no_sign(*args, **kwargs):
    pytest.fail("read or refused request signed")

def test_sign_confirms_exact_snapshot_and_survives_successor_restore(world):
    response = sign(world)
    assert response.status_code == 200
    signed = response.json()
    assert signed["signed"] is True
    verify_signature(world, signed["dsse"])
    retention = signed["retention"]
    assert retention["state"] == "IMMUTABLE_SNAPSHOT_CONFIRMED"
    assert retention["confirmed"] is True and retention["execution_authorized"] is False
    head = world["backend"].head()
    assert head["snapshots"]["khipu"]["sha256"] == retention["snapshot_sha256"]
    before = world["client"].get(LEDGER).json()["nodes"]
    assert before[0]["dsse"] == signed["dsse"]
    with sqlite3.connect(snapshot_file(world)) as db:
        legacy_rows = db.execute("SELECT * FROM receipts ORDER BY id").fetchall()
        assert len(legacy_rows) == 2
    # Restore into a new local root from immutable objects, not the previous live DB.
    world["writer"].close()
    successor = replica(world["root"], "successor", world["objects"], world["backend"], world["clock"])
    successor.boot()
    successor.heartbeat_once()
    world["monkeypatch"].setattr(ss, "_ACTIVE", successor)
    app, client = app_client()
    try:
        assert client.get(LEDGER).json()["nodes"] == before
        with sqlite3.connect(successor.local_path("khipu")) as db:
            assert db.execute("SELECT * FROM receipts ORDER BY id").fetchall() == legacy_rows
        with world["monkeypatch"].context() as mp:
            mp.setattr(szl_dsse, "sign_payload", no_sign)
            assert client.get(LEDGER).json()["count"] == 1
        result = client.post(SIGN, headers={"Authorization": "Bearer " + OPERATOR},
                             json={"receipt": {"schema": "test/proof", "nonce": "next"}})
        assert result.status_code == 200 and result.json()["index"] == 1
        nodes = client.get(LEDGER).json()["nodes"]
        assert nodes[1]["parents"] == [before[0]["digest"]]
        verify_signature(world, nodes[1]["dsse"])
    finally:
        client.close()
        successor._close_watchers()

def test_empty_and_recorded_gets_never_create_tables_write_or_sign(world):
    path = snapshot_file(world)
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    with world["monkeypatch"].context() as mp:
        mp.setattr(szl_dsse, "sign_payload", no_sign)
        mp.setattr(szl_dsse, "_load_private_key", no_sign)
        mp.setattr(a11oy_signing_key, "load_signing_key", no_sign)
        assert world["client"].get(LEDGER).json()["count"] == 0
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    assert sign(world).status_code == 200
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    with world["monkeypatch"].context() as mp:
        mp.setattr(szl_dsse, "sign_payload", no_sign)
        mp.setattr(szl_dsse, "_load_private_key", no_sign)
        mp.setattr(a11oy_signing_key, "load_signing_key", no_sign)
        for _ in range(2):
            assert world["client"].get(LEDGER).json()["count"] == 1
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before

@pytest.mark.parametrize("role", [ss.ROLE_FENCED, ss.ROLE_BLOCKED, ss.ROLE_RELEASED, ss.ROLE_UNFENCED_WRITER])
def test_nonwriter_or_unfenced_refuses_before_signing(world, role):
    world["writer"].role = role
    if role == ss.ROLE_UNFENCED_WRITER:
        world["writer"].mode = ss.MODE_UNFENCED
    world["monkeypatch"].setattr(szl_dsse, "sign_payload", no_sign)
    assert sign(world).status_code == 503
    assert world["writer"]._inflight == 0

def test_unactivated_owner_does_not_create_database_or_sign(world):
    path = snapshot_file(world)
    before = path.read_bytes()
    world["monkeypatch"].setattr(ss, "_ACTIVE", None)
    world["monkeypatch"].setattr(szl_dsse, "sign_payload", no_sign)
    assert sign(world).status_code == 503
    assert path.read_bytes() == before

def test_anonymous_request_never_creates_table_or_signs(world):
    path = snapshot_file(world)
    before = path.read_bytes()
    world["monkeypatch"].setattr(szl_dsse, "sign_payload", no_sign)
    assert world["client"].post(SIGN, json={"receipt": {"nonce": "denied"}}).status_code == 401
    assert path.read_bytes() == before

def test_missing_managed_database_never_recreates_or_falls_back(world):
    snapshot_file(world).unlink()
    world["monkeypatch"].setattr(szl_dsse, "sign_payload", no_sign)
    assert sign(world).status_code == 503
    assert world["client"].get(LEDGER).status_code == 503
    assert not snapshot_file(world).exists()

def test_import_failure_with_managed_intent_never_falls_back(world):
    world["monkeypatch"].setattr(provenance, "_state_store", None)
    app, client = app_client()
    world["monkeypatch"].setattr(szl_dsse, "sign_payload", no_sign)
    try:
        assert client.get(LEDGER).status_code == 503
        assert client.post(SIGN, headers={"Authorization": "Bearer " + OPERATOR},
                           json={"receipt": {"nonce": "not-memory"}}).status_code == 503
    finally:
        client.close()

def test_blocked_store_does_not_abort_route_registration(world):
    world["writer"].stores["khipu"].health = "BLOCKED"
    app, client = app_client()
    world["monkeypatch"].setattr(szl_dsse, "sign_payload", no_sign)
    try:
        assert client.get(LEDGER).status_code == 503
        assert client.post(SIGN, headers={"Authorization": "Bearer " + OPERATOR},
                           json={"receipt": {"nonce": "blocked"}}).status_code == 503
    finally:
        client.close()

@pytest.mark.parametrize("damage", ["DROP TABLE provenance_nodes",
                                    "DROP TABLE provenance_heads",
                                    "DELETE FROM provenance_nodes"])
def test_missing_table_or_truncated_tail_refuses_reinitialization(world, damage):
    assert sign(world).status_code == 200
    with sqlite3.connect(snapshot_file(world)) as db:
        db.execute(damage)
    world["monkeypatch"].setattr(szl_dsse, "sign_payload", no_sign)
    assert world["client"].get(LEDGER).status_code == 503
    assert sign(world, "after-loss").status_code == 503

def test_corrupt_retained_node_refuses_reads_and_new_signatures(world):
    assert sign(world).status_code == 200
    with sqlite3.connect(snapshot_file(world)) as db:
        db.execute("UPDATE provenance_nodes SET node_json='{}'")
    world["monkeypatch"].setattr(szl_dsse, "sign_payload", no_sign)
    assert world["client"].get(LEDGER).status_code == 503
    assert sign(world, "after-corruption").status_code == 503

def test_inconsistent_parent_chain_refuses_even_with_matching_row_checksum(world):
    assert sign(world).status_code == 200
    with sqlite3.connect(snapshot_file(world)) as db:
        node = json.loads(db.execute("SELECT node_json FROM provenance_nodes").fetchone()[0])
        node["parents"] = ["a" * 64]
        encoded = json.dumps(node, sort_keys=True, separators=(",", ":"))
        db.execute("UPDATE provenance_nodes SET node_json=?,node_sha256=?",
                   (encoded, hashlib.sha256(encoded.encode()).hexdigest()))
    assert world["client"].get(LEDGER).status_code == 503

def test_local_commit_failure_never_returns_success_or_updates_memory(world):
    assert sign(world).status_code == 200
    with sqlite3.connect(snapshot_file(world)) as db:
        db.execute("CREATE TRIGGER refuse_node BEFORE INSERT ON provenance_nodes "
                   "BEGIN SELECT RAISE(ABORT, 'synthetic write failure'); END")
    response = sign(world, "failed")
    assert response.status_code == 503
    assert "dsse" not in response.json()
    assert world["client"].get(LEDGER).json()["count"] == 1
    assert world["writer"]._inflight == 0

@pytest.mark.parametrize("failure", ["upload", "readback", "cas"])
def test_snapshot_failure_never_claims_confirmed_success(world, failure):
    writer = world["writer"]
    def broken(*args, **kwargs):
        raise ss.StorageBlocked("SYNTHETIC_CONFIRMATION_FAILURE")
    if failure == "upload":
        world["monkeypatch"].setattr(world["objects"], "put_file", broken)
    elif failure == "readback":
        world["monkeypatch"].setattr(writer, "_download", broken)
    else:
        world["monkeypatch"].setattr(writer, "_advance_snapshot", broken)
    response = sign(world, failure)
    assert response.status_code == 503
    assert response.json()["retention_confirmed"] is False
    assert "dsse" not in response.json()
    assert writer._inflight == 0

def test_ledger_and_health_gets_complete_while_signing_snapshot_is_waiting(world):
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = world["writer"].snapshot_confirmed

    def waiting_snapshot(*args, **kwargs):
        started.set()
        try:
            if not release.wait(timeout=3):
                raise ss.StorageBlocked("SYNTHETIC_SNAPSHOT_TIMEOUT")
            return original(*args, **kwargs)
        finally:
            finished.set()

    world["monkeypatch"].setattr(world["writer"], "snapshot_confirmed", waiting_snapshot)

    # Exercise the real liveness/readiness routes, including the distinct
    # DurableKhipu reader sharing the same managed SQLite file.
    szl_be_hardening.harden(world["app"], organ="a11oy")

    async def exercise():
        # Both requests use the same event loop, as they do in one ASGI worker.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=world["app"]),
                                     base_url="http://test") as client:
            pending = asyncio.create_task(client.post(
                SIGN, headers={"Authorization": "Bearer " + OPERATOR},
                json={"receipt": {"nonce": "slow-retention"}}))
            try:
                assert await asyncio.to_thread(started.wait, 2)
                ledger = await asyncio.wait_for(client.get(LEDGER), timeout=1)
                assert ledger.status_code == 200 and ledger.json()["count"] == 1
                # Local bytes may be visible before confirmation; no retention
                # acknowledgment is stored in or inferred from that node.
                assert "retention" not in ledger.json()["nodes"][0]
                response = await asyncio.wait_for(client.get("/healthz"), timeout=1)
                assert response.status_code == 200 and response.json()["status"] == "ok"
                storage = await asyncio.wait_for(
                    client.get("/api/a11oy/v1/storage/status"), timeout=1)
                assert storage.status_code == 200 and storage.json()["role"] == ss.ROLE_WRITER
                ready = await asyncio.wait_for(client.get("/readyz"), timeout=1)
                assert ready.status_code == 200 and ready.json()["khipu_chain_ok"] is True
                assert not finished.is_set() and not pending.done()
                assert world["writer"]._inflight > 0
                # Existing async callers use the synchronous helper. Its local
                # append must not wait behind this strict remote confirmation.
                internal = world["app"].state.szl_emit_signed_receipt({"nonce": "local-audit"})
                assert internal["index"] == 1 and "retention" not in internal
                assert not finished.is_set() and not pending.done()
            finally:
                release.set()
                result = await asyncio.wait_for(pending, timeout=5)
            assert result.status_code == 200 and result.json()["retention"]["confirmed"] is True
            assert world["writer"]._inflight == 0

    asyncio.run(exercise())

def test_internal_receipts_use_local_admission_without_remote_lease_io(world):
    def forbidden(*args, **kwargs):
        pytest.fail("locally pending receipt must not perform remote confirmation")
    world["monkeypatch"].setattr(world["writer"], "confirmed_writer", forbidden)
    world["monkeypatch"].setattr(world["writer"], "snapshot_confirmed", forbidden)
    node = world["app"].state.szl_emit_signed_receipt({"nonce": "local-admitted-audit"})
    assert node["signed"] is True and "retention" not in node
    assert world["client"].get(LEDGER).json()["nodes"] == [node]
    assert world["writer"]._inflight == 0

def test_two_independent_dag_instances_serialize_the_authoritative_tail(world):
    first, second = provenance._KhipuDAG("a11oy"), provenance._KhipuDAG("a11oy")
    with ThreadPoolExecutor(max_workers=2) as workers:
        nodes = list(workers.map(lambda pair: pair[0].append_signed({"nonce": pair[1]}),
                                 [(first, "one"), (second, "two")]))
    assert sorted(n["index"] for n in nodes) == [0, 1]
    retained = first.nodes
    assert len(retained) == 2 and retained[1]["parents"] == [retained[0]["digest"]]
    assert second.nodes == retained
    # Mutating returned objects cannot change the retained bytes.
    nodes[0]["receipt"]["nonce"] = "mutated"
    assert first.nodes == retained

def test_concurrent_reader_observes_a_consistent_chain_and_tail(world):
    reader, writer = provenance._KhipuDAG("a11oy"), provenance._KhipuDAG("a11oy")
    def append_many():
        for index in range(20):
            writer.append_signed({"nonce": index})
    def read_many():
        for _ in range(40):
            nodes = reader.nodes
            assert [node["index"] for node in nodes] == list(range(len(nodes)))
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(append_many), workers.submit(read_many)]
        for future in futures:
            future.result(timeout=20)
    assert len(reader.nodes) == 20

def test_standalone_mode_preserves_memory_contract(world):
    world["monkeypatch"].delenv("A11OY_STATE_STORE")
    world["monkeypatch"].setattr(ss, "_ACTIVE", None)
    app, client = app_client()
    try:
        response = client.post(SIGN, headers={"Authorization": "Bearer " + OPERATOR},
                               json={"receipt": {"nonce": "standalone"}})
        assert response.status_code == 200 and response.json()["signed"] is True
        assert response.json()["retention"] == {"state": "PROCESS_MEMORY", "confirmed": False}
        assert client.get(LEDGER).json()["count"] == 1
    finally:
        client.close()

