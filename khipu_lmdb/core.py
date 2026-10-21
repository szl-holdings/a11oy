# VENDORED FROM szl-holdings/platform@d16b702ebe63042e05f41eacea4853afc59c7ab3 — packages/khipu-lmdb/khipu_lmdb/core.py
# DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries · 13-axis
# Signed: Yachay.  git trailer: Perplexity Computer Agent
"""
szl_khipu_lmdb.py — Khipu LMDB persistence layer.

The earlier a11oy Khipu DAG (szl_khipu.py) is an IN-MEMORY hash-chained receipt
store: correct discipline, but the chain is lost on Space restart. This module
gives Khipu a DURABLE backend using the real `lmdb` library (Lightning Memory-
Mapped Database, an embedded B+tree key-value store).

What is real here (Zero-Bandaid Law):
  · Storage is a real on-disk LMDB environment (`lmdb.open(path)`). A write that
    completes a transaction is durable; it survives process kill + restart.
  · Receipts are append-only and hash-chained: receipt[n].prev == receipt[n-1]
    digest. The chain is SHA3-256 over the canonical body — tamper-evident by
    re-walk alone (no signature needed for integrity; signatures are a separate,
    honestly-labelled concern handled by the cosign DSSE path elsewhere).
  · `verify()` re-walks the entire on-disk chain and recomputes every digest and
    prev-link; it returns the real depth and the seq of the first break (if any).

Key layout in LMDB (a single unnamed DB, lexicographic order):
  b"seq:%020d"  -> receipt JSON          (the append-only log, ordered by seq)
  b"rcpt:%s"    -> seq (as ascii int)    (receipt-hash -> seq index)
  b"meta:head"  -> head receipt digest
  b"meta:count" -> total receipts
  b"origin:%s" -> first local seq for a foreign receipt digest
  b"meta:origin-indexed-count" -> local prefix indexed by explicit replication writes

Stdlib + lmdb only.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

import lmdb

__version__ = "khipu-lmdb/1.0.0"
_GENESIS = "0" * 64
_MAX_ORIGIN_BYTES = 1024 * 1024
_MAX_ORIGIN_BACKFILL = 1000
_MAX_ORIGIN_BACKFILL_BYTES = 16 * 1024 * 1024

# Process-wide registry of open LMDB environments keyed by absolute path. LMDB
# forbids opening the SAME environment twice in one process (raises "already open
# in this process"). Some servers import the app module more than once (e.g.
# uvicorn.run("serve:app") re-imports `serve`), which would re-run register() and
# re-open the same path. We share one env per path to stay correct + idempotent.
_ENV_REGISTRY: "dict[str, Any]" = {}
_REGISTRY_LOCK = threading.Lock()


def _sha3(b: bytes) -> str:
    return hashlib.sha3_256(b).hexdigest()


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(obj: Any) -> str:
    return _sha3(_canon(obj))


def _seq_key(seq: int) -> bytes:
    return b"seq:%020d" % seq


def _require_json_object_keys(obj: Any) -> None:
    if isinstance(obj, dict):
        if any(type(key) is not str for key in obj):
            raise ValueError("REPLICATION_NON_STRING_JSON_KEY")
        for value in obj.values():
            _require_json_object_keys(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _require_json_object_keys(value)


def _finite_canon(obj: Any) -> bytes:
    try:
        # JSON coercion of numeric keys can reorder a frozen/replayed receipt.
        # Validate this strict write path without changing legacy append bytes.
        _require_json_object_keys(obj)
        return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as error:
        raise ValueError("REPLICATION_INVALID_JSON") from error


def _verified_origin(origin: Any, max_bytes: int = _MAX_ORIGIN_BYTES) -> bytes:
    """Validate integrity and return canonical bytes, without authenticating a sender."""
    fields = ("organ", "ns", "seq", "action", "payload_digest", "prev")
    if type(origin) is not dict or not {*fields, "payload", "digest"} <= origin.keys():
        raise ValueError("REPLICATION_INVALID_RECEIPT")
    canonical = _finite_canon(origin)
    if len(canonical) > max_bytes:
        raise ValueError("REPLICATION_ORIGIN_TOO_LARGE")
    if (_sha3(_finite_canon(origin["payload"])) != origin["payload_digest"]
            or _sha3(_finite_canon({key: origin[key] for key in fields})) != origin["digest"]):
        raise ValueError("REPLICATION_INTEGRITY_FAILED")
    return canonical


class KhipuLMDB:
    """Durable, append-only, hash-chained Khipu receipt store backed by LMDB."""

    def __init__(
        self,
        path: str,
        organ: str = "khipu",
        ns: str = "szl",
        map_size: int = 256 * 1024 * 1024,  # 256 MiB mmap; grows as needed
    ) -> None:
        self.path = path
        self.organ = organ
        self.ns = ns
        self._lock = threading.RLock()
        os.makedirs(path, exist_ok=True)
        abspath = os.path.abspath(path)
        # subdir=True -> path is a directory holding data.mdb + lock.mdb
        with _REGISTRY_LOCK:
            env = _ENV_REGISTRY.get(abspath)
            if env is None:
                env = lmdb.open(
                    path,
                    map_size=map_size,
                    subdir=True,
                    readonly=False,
                    metasync=True,
                    sync=True,  # durability: flush to disk on commit
                    max_dbs=0,
                )
                _ENV_REGISTRY[abspath] = env
            self._env = env
        self._abspath = abspath
        self._init_meta()

    def _init_meta(self) -> None:
        with self._lock, self._env.begin(write=True) as txn:
            if txn.get(b"meta:head") is None:
                txn.put(b"meta:head", _GENESIS.encode())
            if txn.get(b"meta:count") is None:
                txn.put(b"meta:count", b"0")

    # ---- counters ---------------------------------------------------------
    def _count(self, txn: "lmdb.Transaction") -> int:
        raw = txn.get(b"meta:count")
        return int(raw) if raw else 0

    def _head(self, txn: "lmdb.Transaction") -> str:
        raw = txn.get(b"meta:head")
        return raw.decode() if raw else _GENESIS

    # ---- write ------------------------------------------------------------
    def append(self, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Append a hash-chained receipt durably to LMDB; return the receipt."""
        payload = payload or {}
        with self._lock, self._env.begin(write=True) as txn:
            return self._append_txn(txn, action, payload)

    def _append_txn(self, txn: "lmdb.Transaction", action: str, payload: Any) -> Dict[str, Any]:
        # Keep append's existing canonical bytes and receipt shape unchanged.
        seq = self._count(txn)
        prev = self._head(txn)
        ts = time.time()
        body = {
            "organ": self.organ,
            "ns": self.ns,
            "seq": seq,
            "action": action,
            "payload_digest": _digest(payload),
            "prev": prev,
        }
        digest = _digest(body)
        receipt = {
            **body,
            "payload": payload,
            "ts": ts,
            "digest": digest,
            "signature": "DSSE_PLACEHOLDER",  # honest: chain-verified, not signed
            "chain_verified": True,
        }
        txn.put(_seq_key(seq), _canon(receipt))
        txn.put(b"rcpt:" + digest.encode(), str(seq).encode())
        txn.put(b"meta:head", digest.encode())
        txn.put(b"meta:count", str(seq + 1).encode())
        return receipt

    def _replication_record(self, txn: "lmdb.Transaction", seq: int) -> Dict[str, Any]:
        raw = txn.get(_seq_key(seq))
        if raw is None or len(raw) > _MAX_ORIGIN_BYTES * 2:
            raise ValueError("REPLICATION_HISTORY_INVALID")
        try:
            receipt = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError) as error:
            raise ValueError("REPLICATION_HISTORY_INVALID") from error
        _verified_origin(receipt, max_bytes=_MAX_ORIGIN_BYTES * 2)
        if type(receipt["seq"]) is not int or receipt["seq"] != seq:
            raise ValueError("REPLICATION_HISTORY_INVALID")
        return receipt

    def _origin_lookup(self, txn: "lmdb.Transaction", origin: dict,
                       canonical: bytes) -> Optional[Dict[str, Any]]:
        index = txn.get(b"origin:" + origin["digest"].encode("ascii"))
        if index is None:
            return None
        try:
            seq = int(index)
        except ValueError as error:
            raise ValueError("REPLICATION_INDEX_INVALID") from error
        if str(seq).encode() != index or not 0 <= seq < self._count(txn):
            raise ValueError("REPLICATION_INDEX_INVALID")
        receipt = self._replication_record(txn, seq)
        payload = receipt["payload"]
        if receipt["action"] != "replicated" or type(payload) is not dict:
            raise ValueError("REPLICATION_INDEX_INVALID")
        existing = payload.get("origin")
        existing_bytes = _verified_origin(existing)
        if existing["digest"] != origin["digest"]:
            raise ValueError("REPLICATION_INDEX_INVALID")
        if existing_bytes != canonical:
            raise ValueError("REPLICATION_ORIGIN_CONFLICT")
        return receipt

    def _backfill_origins(self, txn: "lmdb.Transaction") -> None:
        total = self._count(txn)
        raw_cursor = txn.get(b"meta:origin-indexed-count", b"0")
        try:
            cursor = int(raw_cursor)
        except ValueError as error:
            raise ValueError("REPLICATION_INDEX_INVALID") from error
        if str(cursor).encode() != raw_cursor or not 0 <= cursor <= total:
            raise ValueError("REPLICATION_INDEX_INVALID")
        if total - cursor > _MAX_ORIGIN_BACKFILL:
            raise ValueError("REPLICATION_HISTORY_RECONCILIATION_REQUIRED")
        previous = (self._replication_record(txn, cursor - 1)["digest"]
                    if cursor else _GENESIS)
        scanned_bytes = 0
        for seq in range(cursor, total):
            raw = txn.get(_seq_key(seq))
            scanned_bytes += len(raw) if raw is not None else 0
            if scanned_bytes > _MAX_ORIGIN_BACKFILL_BYTES:
                raise ValueError("REPLICATION_HISTORY_RECONCILIATION_REQUIRED")
            receipt = self._replication_record(txn, seq)
            if receipt["prev"] != previous:
                raise ValueError("REPLICATION_HISTORY_INVALID")
            previous = receipt["digest"]
            if receipt["action"] != "replicated":
                continue
            payload = receipt["payload"]
            origin = payload.get("origin") if type(payload) is dict else None
            canonical = _verified_origin(origin)
            if self._origin_lookup(txn, origin, canonical) is None:
                txn.put(b"origin:" + origin["digest"].encode("ascii"), str(seq).encode())
        if previous != self._head(txn):
            raise ValueError("REPLICATION_HISTORY_INVALID")
        txn.put(b"meta:origin-indexed-count", str(total).encode())

    def append_replicated(self, origin: Dict[str, Any]) -> Dict[str, Any]:
        """Atomically retain one mirror wrapper per exact foreign receipt.

        All origin fields, including unauthenticated auxiliary metadata, must
        match on replay. A conflicting digest fails closed. Historical duplicate
        wrappers remain intact; bounded backfill runs only on this write path.
        Sender authorization and durable outbound recovery remain separate.
        """
        canonical = _verified_origin(origin)
        # Freeze caller-owned mutable data before the transaction and comparison.
        origin = json.loads(canonical)
        with self._lock, self._env.begin(write=True) as txn:
            self._backfill_origins(txn)
            existing = self._origin_lookup(txn, origin, canonical)
            if existing is not None:
                return {"receipt": existing, "duplicate": True}
            receipt = self._append_txn(txn, "replicated", {"origin": origin})
            txn.put(b"origin:" + origin["digest"].encode("ascii"), str(receipt["seq"]).encode())
            txn.put(b"meta:origin-indexed-count", str(receipt["seq"] + 1).encode())
            return {"receipt": receipt, "duplicate": False}

    def replication_outbound_state(self, peer_id: str, binding_sha256: str):
        """Read local outbound state without creating or repairing metadata."""
        from .outbox import read
        return read(self, peer_id, binding_sha256)

    def prepare_replication_batch(self, peer_id: str, binding_sha256: str, *,
                                  limit: int = 100, max_bytes: int = 4 * 1024 * 1024):
        """Persist/replay a bounded batch; does not transmit or authenticate it."""
        from .outbox import prepare
        return prepare(self, peer_id, binding_sha256, limit=limit, max_bytes=max_bytes)

    def acknowledge_replication_batch(self, peer_id: str, binding_sha256: str, batch_id: str):
        """Commit an exact pending ACK; caller must authenticate the peer first."""
        from .outbox import acknowledge
        return acknowledge(self, peer_id, binding_sha256, batch_id)

    # ---- read -------------------------------------------------------------
    def get_by_seq(self, seq: int) -> Optional[Dict[str, Any]]:
        with self._lock, self._env.begin() as txn:
            raw = txn.get(_seq_key(seq))
            return json.loads(raw) if raw else None

    def get_by_receipt(self, digest: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._env.begin() as txn:
            sraw = txn.get(b"rcpt:" + digest.encode())
            if not sraw:
                return None
            raw = txn.get(_seq_key(int(sraw)))
            return json.loads(raw) if raw else None

    def tail(self, n: int = 10) -> List[Dict[str, Any]]:
        with self._lock, self._env.begin() as txn:
            total = self._count(txn)
            out: List[Dict[str, Any]] = []
            start = max(0, total - n)
            for s in range(start, total):
                raw = txn.get(_seq_key(s))
                if raw:
                    out.append(json.loads(raw))
            return out

    # ---- verify -----------------------------------------------------------
    def verify(self) -> Dict[str, Any]:
        """Re-walk the entire on-disk chain; recompute every digest + prev link."""
        with self._lock, self._env.begin() as txn:
            total = self._count(txn)
            prev = _GENESIS
            broken_at: Optional[int] = None
            for s in range(total):
                raw = txn.get(_seq_key(s))
                if raw is None:
                    broken_at = s
                    break
                r = json.loads(raw)
                body = {
                    "organ": r["organ"],
                    "ns": r["ns"],
                    "seq": r["seq"],
                    "action": r["action"],
                    "payload_digest": r["payload_digest"],
                    "prev": prev,
                }
                recomputed = _digest(body)
                if recomputed != r["digest"] or r["prev"] != prev:
                    broken_at = s
                    break
                # payload integrity too
                if _digest(r.get("payload", {})) != r["payload_digest"]:
                    broken_at = s
                    break
                prev = r["digest"]
            ok = broken_at is None
            head = self._head(txn)
            return {
                "ok": ok,
                "depth": total,
                "broken_at": broken_at,
                "head": head if ok else None,
                "version": __version__,
            }

    def stats(self) -> Dict[str, Any]:
        with self._lock, self._env.begin() as txn:
            total = self._count(txn)
            head = self._head(txn)
        info = self._env.info()
        return {
            "version": __version__,
            "organ": self.organ,
            "ns": self.ns,
            "entries": total,
            "head": head,
            "db_path": os.path.abspath(self.path),
            "map_size": info.get("map_size"),
            "lmdb_version": ".".join(str(x) for x in lmdb.version()),
            "durable": True,
        }

    def close(self) -> None:
        with self._lock:
            self._env.sync(True)
        # Drop from the registry and close the shared env. Safe because callers
        # that re-open will get a fresh env. In tests each path is unique.
        with _REGISTRY_LOCK:
            if _ENV_REGISTRY.get(self._abspath) is self._env:
                _ENV_REGISTRY.pop(self._abspath, None)
        self._env.close()
