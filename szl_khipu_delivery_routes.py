# SPDX-License-Identifier: Apache-2.0
"""provenance/: explicit replication POSTs with confirmed snapshot barriers."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from urllib.parse import urlsplit

import anyio
from fastapi import Request
from fastapi.responses import JSONResponse, Response
import lmdb

from khipu_lmdb import KhipuLMDB
from khipu_lmdb import delivery, outbox
from khipu_lmdb.core import _finite_canon, _verified_origin
from szl_operator_auth import operator_refusal

CONFIG_ENV = "KHIPU_HTTPS_PEERS_JSON"


class StateOwnerUnavailable(ValueError):
    """This consumer has no qualified managed owner for the requested effect."""


def _configured(ns):
    raw = os.environ.get(CONFIG_ENV, "[]")
    if len(raw.encode("utf-8")) > 65536:
        raise ValueError("CONFIG_INVALID")
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("CONFIG_INVALID")
            result[key] = value
        return result
    values = json.loads(raw, object_pairs_hook=unique_fields)
    if type(values) is not list or len(values) > 64:
        raise ValueError("CONFIG_INVALID")
    peers = {}
    for item in values:
        if type(item) is not dict or set(item) != {"direction", "peer_id", "endpoint",
                "source_organ", "source_ns", "credential_env"} or item["direction"] not in ("inbound", "outbound"):
            raise ValueError("CONFIG_INVALID")
        peer = delivery.Peer(**{key: value for key, value in item.items() if key != "direction"})
        key = (item["direction"], peer.peer_id)
        if key in peers:
            raise ValueError("CONFIG_INVALID")
        if item["direction"] == "inbound" and urlsplit(peer.endpoint).path != (
                f"/api/{ns}/v2/khipu/replicate/batch/{peer.peer_id}"):
            raise ValueError("CONFIG_INVALID")
        peers[key] = peer
    return peers


def _state(source, mirror):
    # A missing qualified owner (including Killinchu today) refuses before write.
    try:
        import a11oy_state_store
    except ImportError:
        raise StateOwnerUnavailable("QUALIFIED_STATE_OWNER_UNAVAILABLE") from None
    state = a11oy_state_store.active()
    if state is None:
        raise StateOwnerUnavailable("QUALIFIED_STATE_OWNER_UNAVAILABLE")
    for label, live in (("khipu_lmdb", source), ("khipu_repl", mirror)):
        if Path(live._abspath).resolve() != state.local_path(label).resolve():
            raise ValueError("MANAGED_STORE_PATH_MISMATCH")
        if a11oy_state_store._registered_lmdb_env(state.local_path(label)) is not live._env:
            raise ValueError("MANAGED_STORE_HANDLE_MISMATCH")
    return state


def _read_snapshot(path, organ, ns, predicate):
    env = lmdb.open(str(path), readonly=True, lock=False, create=False, subdir=True, max_dbs=0)
    try:
        # Use only the existing read validators; the constructor would write.
        view = object.__new__(KhipuLMDB)
        view.organ, view.ns, view._env, view._lock = organ, ns, env, threading.RLock()
        with env.begin() as txn:
            return predicate(view, txn) is True
    finally:
        env.close()


def _pending_contains(path, source, peer, batch):
    def matches(view, txn):
        keys = outbox._identity(view, peer.peer_id, peer.binding_sha256)
        state, raw = outbox._load(view, txn, peer.peer_id, peer.binding_sha256, keys)
        return (state is not None and raw == batch["body"] and state["pending"] is not None
                and state["pending"]["batch_id"] == batch["batch_id"]
                and state["next_seq"] == batch["first_seq"]
                and state["pending"]["next_seq"] == batch["next_seq"])
    return _read_snapshot(path, source.organ, source.ns, matches)


def _ack_contains(path, source, peer, batch):
    def matches(view, txn):
        state, raw = outbox._load(view, txn, peer.peer_id, peer.binding_sha256,
                                  outbox._identity(view, peer.peer_id, peer.binding_sha256))
        receipts = json.loads(batch["body"])["receipts"]
        return (state is not None and raw is None and state["pending"] is None
                and state["next_seq"] == batch["next_seq"]
                and state["acknowledged_digest"] == receipts[-1]["digest"])
    return _read_snapshot(path, source.organ, source.ns, matches)


def _received_contains(path, mirror, peer, raw):
    batch = json.loads(raw)
    def matches(view, txn):
        key = b"meta:https-inbound:" + hashlib.sha256(peer.peer_id.encode("ascii")).hexdigest().encode("ascii")
        state = outbox._strict_json(txn.get(key), delivery.MAX_ACK_BYTES)
        expected = {"binding_sha256": peer.binding_sha256, "next_seq": batch["next_seq"],
                    "last_digest": batch["receipts"][-1]["digest"],
                    "last_batch_id": hashlib.sha256(raw).hexdigest(), "last_first_seq": batch["first_seq"]}
        if _finite_canon(state) != _finite_canon(expected):
            return False
        return all(view._origin_lookup(txn, receipt, _verified_origin(receipt)) is not None
                   for receipt in batch["receipts"])
    return _read_snapshot(path, mirror.organ, mirror.ns, matches)


def register(app, *, ns, source, mirror):
    """Reuse the sole live handles; no background worker, new store or GET write."""
    try:
        peers, config_error = _configured(ns), False
    except (ValueError, TypeError, UnicodeError, RecursionError):
        peers, config_error = {}, True
    # Outbound waits on a remote receiver. Never hold an inbound operation's
    # lock across that wait: two peers can dispatch toward each other at once.
    locks = {key: threading.Lock() for key in peers}

    def blocked(reason, status=503):
        return JSONResponse({"status": "BLOCKED", "reason": reason,
                             "execution_authorized": False}, status_code=status)

    def run(direction, peer, raw=None, authorization=None):
        with locks[(direction, peer.peer_id)]:
            state = _state(source, mirror)
            if not state.begin_write():
                raise ValueError("STATE_WRITE_FENCE")
            try:
                state.confirmed_writer()
                if direction == "outbound":
                    delivery._credential(peer)  # fail before preparing any metadata
                    if (source.organ, source.ns) != (peer.source_organ, peer.source_ns):
                        raise ValueError("SOURCE_BINDING_MISMATCH")
                    batch = source.prepare_replication_batch(peer.peer_id, peer.binding_sha256)
                    if batch is None:
                        return JSONResponse({"delivered": 0, "batch_id": None, "execution_authorized": False})
                    state.snapshot_confirmed("khipu_lmdb",
                        lambda path: _pending_contains(path, source, peer, batch))
                    state.confirmed_writer()
                    result = delivery.deliver_once(source, peer, expected_batch_id=batch["batch_id"])
                    state.snapshot_confirmed("khipu_lmdb",
                        lambda path: _ack_contains(path, source, peer, batch))
                    return JSONResponse({**result, "execution_authorized": False})
                ack = delivery.accept_batch(mirror, peer, raw,
                    authorization=authorization)
                state.snapshot_confirmed("khipu_repl",
                    lambda path: _received_contains(path, mirror, peer, raw))
                return Response(ack, media_type="application/json")
            finally:
                state.end_write()

    @app.post(f"/api/{ns}/v2/khipu/replicate/dispatch/{{peer_id}}")
    async def dispatch(peer_id: str, request: Request):
        refusal = operator_refusal(request, "Durable Khipu replication dispatch")
        if refusal is not None:
            return refusal
        peer = peers.get(("outbound", peer_id))
        if config_error or peer is None:
            return blocked("PEER_UNCONFIGURED")
        try:
            return await anyio.to_thread.run_sync(run, "outbound", peer)
        except StateOwnerUnavailable:
            return blocked("QUALIFIED_STATE_OWNER_UNAVAILABLE")
        except Exception:
            return blocked("REPLICATION_DELIVERY_UNCONFIRMED")

    @app.post(f"/api/{ns}/v2/khipu/replicate/batch/{{peer_id}}")
    async def receive(peer_id: str, request: Request):
        peer = peers.get(("inbound", peer_id))
        if config_error or peer is None:
            return blocked("PEER_UNCONFIGURED")
        try:
            expected = "Bearer " + delivery._credential(peer)
        except delivery.DeliveryError:
            return blocked("PEER_CREDENTIAL_UNAVAILABLE")
        presented = request.headers.get("authorization", "")
        if (not presented.isascii() or len(presented) > 8200
                or not hmac.compare_digest(presented, expected)):
            return blocked("PEER_AUTHENTICATION_REQUIRED", 401)
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > outbox.MAX_BATCH_BYTES:
                return blocked("BATCH_TOO_LARGE", 413)
            raw.extend(chunk)
        try:
            return await anyio.to_thread.run_sync(run, "inbound", peer, bytes(raw), presented)
        except StateOwnerUnavailable:
            return blocked("QUALIFIED_STATE_OWNER_UNAVAILABLE")
        except Exception:
            return blocked("REPLICATION_RECEIVE_UNCONFIRMED")

    return {"configured_peers": len(peers), "configuration_valid": not config_error,
            "mode": "EXPLICIT_DISPATCH_ONLY", "execution_authorized": False}
