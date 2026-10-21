# VENDORED FROM szl-holdings/platform@a7071642fc902e0aa4af075cddb71626104ab6b1 — packages/khipu-lmdb/khipu_lmdb/outbox.py
# DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
# SPDX-License-Identifier: Apache-2.0
"""Bounded local delivery state. No transport, peer authentication or activation."""
from __future__ import annotations

import hashlib
import json
import re

from .core import _GENESIS, _MAX_ORIGIN_BYTES, _finite_canon, _seq_key, _verified_origin

MAX_RECORDS = 1000
MAX_BATCH_BYTES = 4 * 1024 * 1024
MAX_PEERS = 64
MAX_STATE_BYTES = 4096
_PREFIX = b"meta:outbound:"
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _fail(reason):
    raise ValueError("REPLICATION_OUTBOUND_" + reason)


def _identity(store, peer_id, binding_sha256):
    if (type(peer_id) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", peer_id)
            or type(binding_sha256) is not str or not _HEX.fullmatch(binding_sha256)):
        _fail("INVALID_BINDING")
    if any(type(value) is not str or not 1 <= len(value.encode("utf-8")) <= 128
           for value in (store.organ, store.ns)):
        _fail("INVALID_SOURCE_IDENTITY")
    suffix = hashlib.sha256(peer_id.encode("ascii")).hexdigest().encode("ascii")
    return _PREFIX + suffix, b"outbound:pending:" + suffix


def _strict_json(raw, bound):
    if raw is None or len(raw) > bound:
        _fail("CORRUPT_STATE")

    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                _fail("CORRUPT_STATE")
            obj[key] = value
        return obj

    try:
        value = json.loads(raw, object_pairs_hook=pairs)
        if _finite_canon(value) != raw:
            _fail("CORRUPT_STATE")
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("REPLICATION_OUTBOUND_CORRUPT_STATE") from error


def _uint(value):
    return type(value) is int and 0 <= value <= 2**63 - 1


def _record(store, txn, seq):
    raw = txn.get(_seq_key(seq))
    try:
        receipt = _strict_json(raw, _MAX_ORIGIN_BYTES)
        if (_verified_origin(receipt) != raw or type(receipt["seq"]) is not int
                or receipt["seq"] != seq or receipt["organ"] != store.organ
                or receipt["ns"] != store.ns):
            _fail("SOURCE_INVALID")
        return raw, receipt
    except (ValueError, KeyError, TypeError, UnicodeError, RecursionError) as error:
        raise ValueError("REPLICATION_OUTBOUND_SOURCE_INVALID") from error


def _total(store, txn):
    raw = txn.get(b"meta:count")
    try:
        total = int(raw)
        if not _uint(total) or str(total).encode("ascii") != raw:
            _fail("SOURCE_INVALID")
        head = _record(store, txn, total - 1)[1]["digest"] if total else _GENESIS
        if txn.get(b"meta:head") != head.encode("ascii"):
            _fail("SOURCE_INVALID")
        return total
    except (ValueError, TypeError, UnicodeError) as error:
        raise ValueError("REPLICATION_OUTBOUND_SOURCE_INVALID") from error


def _header(state, end):
    return {"schema": 1, "peer_id": state["peer_id"], "binding_sha256": state["binding_sha256"],
            "source_organ": state["source_organ"], "source_ns": state["source_ns"],
            "first_seq": state["next_seq"], "next_seq": end, "receipts": []}


def _body(state, raws):
    # Each raw receipt was checked against its strict canonical encoding. Joining
    # these exact bytes preserves auxiliary metadata as well as digest fields.
    header = _finite_canon(_header(state, state["next_seq"] + len(raws)))
    return header.replace(b'"receipts":[]', b'"receipts":[' + b",".join(raws) + b"]", 1)


def _load(store, txn, peer_id, binding_sha256, keys):
    raw, pending_raw = txn.get(keys[0]), txn.get(keys[1])
    if raw is None:
        if pending_raw is not None:
            _fail("CORRUPT_STATE")
        return None, None
    state = _strict_json(raw, MAX_STATE_BYTES)
    if (type(state) is not dict or set(state) != {"schema", "peer_id", "binding_sha256",
            "source_organ", "source_ns", "next_seq", "acknowledged_digest", "pending"}
            or type(state["schema"]) is not int or state["schema"] != 1
            or not _uint(state["next_seq"]) or type(state["acknowledged_digest"]) is not str
            or not _HEX.fullmatch(state["acknowledged_digest"])):
        _fail("CORRUPT_STATE")
    if (state["peer_id"] != peer_id or state["binding_sha256"] != binding_sha256
            or state["source_organ"] != store.organ or state["source_ns"] != store.ns):
        _fail("BINDING_CONFLICT")
    total = _total(store, txn)
    start = state["next_seq"]
    if start > total:
        _fail("CORRUPT_STATE")
    previous = _record(store, txn, start - 1)[1]["digest"] if start else _GENESIS
    if previous != state["acknowledged_digest"]:
        _fail("CORRUPT_STATE")
    pending = state["pending"]
    if pending is None:
        if pending_raw is not None:
            _fail("CORRUPT_STATE")
        return state, None
    if (type(pending) is not dict or set(pending) != {"batch_id", "first_seq", "next_seq",
            "last_digest", "bytes"} or not _uint(pending["first_seq"])
            or pending["first_seq"] != start or not _uint(pending["next_seq"])
            or not start < pending["next_seq"] <= min(total, start + MAX_RECORDS)
            or type(pending["bytes"]) is not int or not 1 <= pending["bytes"] <= MAX_BATCH_BYTES
            or type(pending["batch_id"]) is not str or not _HEX.fullmatch(pending["batch_id"])
            or type(pending["last_digest"]) is not str or not _HEX.fullmatch(pending["last_digest"])):
        _fail("CORRUPT_STATE")
    decoded = _strict_json(pending_raw, MAX_BATCH_BYTES)
    if (len(pending_raw) != pending["bytes"]
            or hashlib.sha256(pending_raw).hexdigest() != pending["batch_id"]
            or type(decoded) is not dict):
        _fail("CORRUPT_STATE")
    raws = []
    for seq in range(start, pending["next_seq"]):
        record_raw, receipt = _record(store, txn, seq)
        if receipt["prev"] != previous:
            _fail("SOURCE_INVALID")
        previous = receipt["digest"]
        raws.append(record_raw)
    if previous != pending["last_digest"] or _body(state, raws) != pending_raw:
        _fail("CORRUPT_STATE")
    return state, pending_raw


def read(store, peer_id, binding_sha256):
    """Read/validate existing state only; never register a peer or repair state."""
    keys = _identity(store, peer_id, binding_sha256)
    with store._lock, store._env.begin() as txn:
        return _load(store, txn, peer_id, binding_sha256, keys)[0]


def _result(state, raw):
    if raw is None:
        return None
    return {"batch_id": state["pending"]["batch_id"], "first_seq": state["next_seq"],
            "next_seq": state["pending"]["next_seq"], "body": raw}


def prepare(store, peer_id, binding_sha256, *, limit=100, max_bytes=MAX_BATCH_BYTES):
    """Register binding and persist one batch, or replay the exact pending bytes."""
    keys = _identity(store, peer_id, binding_sha256)
    if (type(limit) is not int or not 1 <= limit <= MAX_RECORDS
            or type(max_bytes) is not int or not 1024 <= max_bytes <= MAX_BATCH_BYTES):
        _fail("INVALID_LIMIT")
    with store._lock, store._env.begin(write=True) as txn:
        state, pending_raw = _load(store, txn, peer_id, binding_sha256, keys)
        if pending_raw is not None:
            # New caller preferences cannot replace, shrink or skip a pending batch.
            return _result(state, pending_raw)
        total = _total(store, txn)
        if state is None:
            cursor, peers = txn.cursor(), 0
            if cursor.set_range(_PREFIX):
                for key, _ in cursor:
                    if not key.startswith(_PREFIX):
                        break
                    peers += 1
                    if peers >= MAX_PEERS:
                        _fail("PEER_LIMIT")
            state = {"schema": 1, "peer_id": peer_id, "binding_sha256": binding_sha256,
                     "source_organ": store.organ, "source_ns": store.ns, "next_seq": 0,
                     "acknowledged_digest": _GENESIS, "pending": None}
        raws, size, previous = [], 0, state["acknowledged_digest"]
        for seq in range(state["next_seq"], min(total, state["next_seq"] + limit)):
            record_raw, receipt = _record(store, txn, seq)
            if receipt["prev"] != previous:
                _fail("SOURCE_INVALID")
            candidate_size = len(_finite_canon(_header(state, seq + 1))) + size + len(record_raw) + len(raws)
            if candidate_size > max_bytes:
                if not raws:
                    _fail("RECORD_EXCEEDS_BATCH_LIMIT")
                break
            raws.append(record_raw)
            size += len(record_raw)
            previous = receipt["digest"]
        if raws:
            pending_raw = _body(state, raws)
            state["pending"] = {"batch_id": hashlib.sha256(pending_raw).hexdigest(),
                                "first_seq": state["next_seq"], "next_seq": state["next_seq"] + len(raws),
                                "last_digest": previous, "bytes": len(pending_raw)}
            txn.put(keys[1], pending_raw)
        txn.put(keys[0], _finite_canon(state))
        return _result(state, pending_raw)


def acknowledge(store, peer_id, binding_sha256, batch_id):
    """Advance only the exact pending batch, after caller authenticates its ACK."""
    keys = _identity(store, peer_id, binding_sha256)
    if type(batch_id) is not str or not _HEX.fullmatch(batch_id):
        _fail("INVALID_ACK")
    with store._lock, store._env.begin(write=True) as txn:
        state, raw = _load(store, txn, peer_id, binding_sha256, keys)
        if raw is None or state["pending"]["batch_id"] != batch_id:
            _fail("ACK_MISMATCH")
        state["next_seq"] = state["pending"]["next_seq"]
        state["acknowledged_digest"] = state["pending"]["last_digest"]
        state["pending"] = None
        txn.put(keys[0], _finite_canon(state))
        txn.delete(keys[1])
        return state
