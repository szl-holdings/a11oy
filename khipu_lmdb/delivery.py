# VENDORED FROM szl-holdings/platform@a7071642fc902e0aa4af075cddb71626104ab6b1 — packages/khipu-lmdb/khipu_lmdb/delivery.py
# DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
# SPDX-License-Identifier: Apache-2.0
"""Explicit, one-attempt delivery. No peer provisioning or automatic activation."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import http.client
import math
import os
import re
import ssl
from urllib.parse import urlsplit

from .core import _GENESIS, _finite_canon, _verified_origin
from .outbox import MAX_BATCH_BYTES, MAX_RECORDS, MAX_PEERS, _strict_json, _uint

MAX_ACK_BYTES = 4096


class DeliveryError(ValueError):
    """Public reason codes never contain endpoints, credentials or raw errors."""


def _fail(reason):
    raise DeliveryError("REPLICATION_DELIVERY_" + reason)


@dataclass(frozen=True)
class Peer:
    """Operator-supplied fixed destination and source; no secret value is retained."""

    peer_id: str
    endpoint: str
    source_organ: str
    source_ns: str
    credential_env: str

    def __post_init__(self):
        if (type(self.peer_id) is not str
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", self.peer_id)
                or type(self.credential_env) is not str
                or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", self.credential_env)):
            _fail("INVALID_PEER")
        if any(type(value) is not str or not 1 <= len(value.encode("utf-8")) <= 128
               for value in (self.source_organ, self.source_ns)):
            _fail("INVALID_PEER")
        if (type(self.endpoint) is not str or not 1 <= len(self.endpoint) <= 2048
                or any(ord(char) <= 32 or ord(char) >= 127 for char in self.endpoint)):
            _fail("INVALID_ENDPOINT")
        try:
            url = urlsplit(self.endpoint)
            if (url.scheme != "https" or not url.hostname or url.username is not None
                    or url.password is not None or url.query or url.fragment
                    or not url.path.startswith("/") or "\\" in self.endpoint
                    or url.port == 0 or url.netloc.endswith(":")):
                _fail("INVALID_ENDPOINT")
        except ValueError:
            _fail("INVALID_ENDPOINT")

    @property
    def binding_sha256(self):
        return hashlib.sha256(_finite_canon({"schema": "khipu-https-peer/1",
            "peer_id": self.peer_id, "endpoint": self.endpoint,
            "source_organ": self.source_organ, "source_ns": self.source_ns,
            "credential_env": self.credential_env})).hexdigest()


def _credential(peer):
    token = os.environ.get(peer.credential_env, "")
    if not 16 <= len(token) <= 8192 or any(ord(char) <= 32 or ord(char) >= 127 for char in token):
        _fail("CREDENTIAL_UNAVAILABLE")
    return token


def _ack(peer, batch_id, first, end):
    return {"schema": 1, "batch_id": batch_id, "peer_id": peer.peer_id,
            "binding_sha256": peer.binding_sha256, "source_organ": peer.source_organ,
            "source_ns": peer.source_ns, "first_seq": first, "next_seq": end,
            "accepted": end - first, "rejected": 0}


def deliver_once(store, peer, *, timeout=10, ca_file=None, expected_batch_id=None):
    """Send pending bytes once; only a verified exact ACK advances durable state.

    Missing credentials fail before registration. Failed/ambiguous delivery leaves
    pending bytes unchanged. A later explicit call replays them; there is no retry
    loop, redirect following, environment proxy, or persistent enabled flag.
    """
    if not isinstance(peer, Peer) or (store.organ, store.ns) != (peer.source_organ, peer.source_ns):
        _fail("SOURCE_BINDING_MISMATCH")
    if expected_batch_id is not None and (type(expected_batch_id) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", expected_batch_id)):
        _fail("INVALID_EXPECTED_BATCH")
    token = _credential(peer)
    if (type(timeout) not in (int, float) or not math.isfinite(timeout)
            or not 0 < timeout <= 30):
        _fail("INVALID_TIMEOUT")
    try:
        context = ssl.create_default_context(cafile=ca_file)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
    except (OSError, ssl.SSLError):
        _fail("TLS_CONFIGURATION_UNAVAILABLE")
    batch = store.prepare_replication_batch(peer.peer_id, peer.binding_sha256)
    if expected_batch_id is not None and (batch is None or batch["batch_id"] != expected_batch_id):
        _fail("PREPARED_BATCH_CHANGED")
    if batch is None:
        return {"delivered": 0, "batch_id": None}
    url = urlsplit(peer.endpoint)
    connection = http.client.HTTPSConnection(url.hostname, url.port or 443,
                                             timeout=timeout, context=context)
    try:
        connection.request("POST", url.path, batch["body"], headers={
            "Content-Type": "application/json", "Accept": "application/json",
            "Authorization": "Bearer " + token})
        response = connection.getresponse()
        if response.status in (401, 403):
            _fail("AUTHENTICATION_REQUIRED")
        if response.status != 200:
            _fail("RESPONSE_REJECTED")
        if response.getheader("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            _fail("ACK_INVALID")
        raw = response.read(MAX_ACK_BYTES + 1)
        try:
            ack = _strict_json(raw, MAX_ACK_BYTES)
        except (ValueError, TypeError):
            _fail("ACK_INVALID")
        expected = _ack(peer, batch["batch_id"], batch["first_seq"], batch["next_seq"])
        # Canonical byte equality also rejects bool-as-int and unknown fields.
        if _finite_canon(ack) != _finite_canon(expected):
            _fail("ACK_INVALID")
    except DeliveryError:
        raise
    except (OSError, http.client.HTTPException, UnicodeError, ValueError):
        _fail("TRANSPORT_UNAVAILABLE")
    finally:
        connection.close()
    store.acknowledge_replication_batch(peer.peer_id, peer.binding_sha256, batch["batch_id"])
    return {"delivered": batch["next_seq"] - batch["first_seq"], "batch_id": batch["batch_id"]}


def accept_batch(store, peer, raw, *, authorization):
    """Authenticate and validate a bounded batch before mirror writes.

    The HTTP host must bind this function to the configured exact endpoint and
    bound request reads. The peer configuration must be locally provisioned, never
    learned from the request. Receipt wrappers, origin indexes and a bound inbound
    cursor commit together. Only the next contiguous batch or an exact replay of
    the last committed batch is acknowledged. No partial batch is acknowledged.
    """
    if not isinstance(peer, Peer):
        _fail("INVALID_PEER")
    expected_auth = "Bearer " + _credential(peer)
    if (type(authorization) is not str or not authorization.isascii()
            or not hmac.compare_digest(authorization, expected_auth)):
        _fail("AUTHENTICATION_REQUIRED")
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_BATCH_BYTES:
        _fail("BATCH_INVALID")
    try:
        batch = _strict_json(raw, MAX_BATCH_BYTES)
        if (type(batch) is not dict or set(batch) != {"schema", "peer_id", "binding_sha256",
                "source_organ", "source_ns", "first_seq", "next_seq", "receipts"}
                or type(batch["schema"]) is not int or batch["schema"] != 1
                or batch["peer_id"] != peer.peer_id or batch["binding_sha256"] != peer.binding_sha256
                or batch["source_organ"] != peer.source_organ or batch["source_ns"] != peer.source_ns
                or not _uint(batch["first_seq"]) or not _uint(batch["next_seq"])
                or type(batch["receipts"]) is not list or not 1 <= len(batch["receipts"]) <= MAX_RECORDS
                or batch["next_seq"] != batch["first_seq"] + len(batch["receipts"])):
            _fail("BATCH_INVALID")
        previous = _GENESIS if batch["first_seq"] == 0 else None
        for seq, receipt in enumerate(batch["receipts"], batch["first_seq"]):
            _verified_origin(receipt)
            if (type(receipt["seq"]) is not int or receipt["seq"] != seq
                    or receipt["organ"] != peer.source_organ or receipt["ns"] != peer.source_ns
                    or (previous is not None and receipt["prev"] != previous)):
                _fail("BATCH_INVALID")
            previous = receipt["digest"]
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        _fail("BATCH_INVALID")
    batch_id = hashlib.sha256(raw).hexdigest()
    prefix = b"meta:https-inbound:"
    key = prefix + hashlib.sha256(peer.peer_id.encode("ascii")).hexdigest().encode("ascii")
    with store._lock, store._env.begin(write=True) as txn:
        state_raw = txn.get(key)
        state = None if state_raw is None else _strict_json(state_raw, MAX_ACK_BYTES)
        if state is not None:
            if (type(state) is not dict or set(state) != {"binding_sha256", "next_seq",
                    "last_digest", "last_batch_id", "last_first_seq"}
                    or state["binding_sha256"] != peer.binding_sha256
                    or not _uint(state["next_seq"]) or not _uint(state["last_first_seq"])
                    or not state["last_first_seq"] < state["next_seq"]
                    or any(type(state[field]) is not str or not re.fullmatch(r"[0-9a-f]{64}", state[field])
                           for field in ("last_digest", "last_batch_id"))):
                _fail("INBOUND_STATE_INVALID")
            try:
                index = txn.get(b"origin:" + state["last_digest"].encode("ascii"))
                local_seq = int(index)
                if str(local_seq).encode() != index or not 0 <= local_seq < store._count(txn):
                    _fail("INBOUND_STATE_INVALID")
                origin = store._replication_record(txn, local_seq)["payload"]["origin"]
                if (origin["digest"] != state["last_digest"] or origin["seq"] != state["next_seq"] - 1
                        or origin["organ"] != peer.source_organ or origin["ns"] != peer.source_ns
                        or store._origin_lookup(txn, origin, _verified_origin(origin)) is None):
                    _fail("INBOUND_STATE_INVALID")
            except (ValueError, TypeError, KeyError, UnicodeError):
                _fail("INBOUND_STATE_INVALID")
        else:
            cursor, peers = txn.cursor(), 0
            if cursor.set_range(prefix):
                for existing_key, _ in cursor:
                    if not existing_key.startswith(prefix):
                        break
                    peers += 1
                    if peers >= MAX_PEERS:
                        _fail("PEER_LIMIT")
        store._backfill_origins(txn)
        replay = state is not None and state["last_batch_id"] == batch_id
        if replay:
            if (state["last_first_seq"] != batch["first_seq"] or state["next_seq"] != batch["next_seq"]
                    or state["last_digest"] != batch["receipts"][-1]["digest"]):
                _fail("INBOUND_STATE_INVALID")
        elif (batch["first_seq"] != (state["next_seq"] if state else 0)
                or batch["receipts"][0]["prev"] != (state["last_digest"] if state else _GENESIS)):
            _fail("SOURCE_DISCONTINUITY")
        for receipt in batch["receipts"]:
            existing = store._origin_lookup(txn, receipt, _verified_origin(receipt))
            if existing is None:
                if replay:
                    _fail("INBOUND_STATE_INVALID")
                wrapper = store._append_txn(txn, "replicated", {"origin": receipt})
                txn.put(b"origin:" + receipt["digest"].encode("ascii"), str(wrapper["seq"]).encode())
                txn.put(b"meta:origin-indexed-count", str(wrapper["seq"] + 1).encode())
        if not replay:
            txn.put(key, _finite_canon({"binding_sha256": peer.binding_sha256,
                "next_seq": batch["next_seq"], "last_digest": batch["receipts"][-1]["digest"],
                "last_batch_id": batch_id, "last_first_seq": batch["first_seq"]}))
    return _finite_canon(_ack(peer, batch_id, batch["first_seq"], batch["next_seq"]))
