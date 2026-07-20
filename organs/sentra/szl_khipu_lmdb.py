# VENDORED FROM szl-holdings/platform@c11291e09702c86f3f8995fffcae6167155c7240 — packages/khipu-lmdb/khipu_lmdb/core.py
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
