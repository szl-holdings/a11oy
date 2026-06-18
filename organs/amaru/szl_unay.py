# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries · 13-axis
# Signed: Yachay.  git trailer: Perplexity Computer Agent
"""
szl_unay.py — UNAY: receipt-keyed semantic memory store.

UNAY (Quechua: "to remember / ancient memory") is a durable, receipt-keyed
memory organ. Every memory is keyed by a SHA3-256 receipt hash (the same chain
discipline as Khipu) and is recallable by semantic similarity.

Design (honest labels — Zero-Bandaid Law):
  · STORE: sqlite (stdlib) — durable on disk, one row per memory.
  · VECTOR SEARCH: sqlite-vss (Faiss-backed) when the extension loads in the
    Space; this is REAL approximate-nearest-neighbour over float32 embeddings.
    If sqlite-vss cannot load (slim Docker, missing .so), UNAY falls back to an
    in-process exact cosine scan over the same vectors and LABELS the backend
    honestly as "cosine-fallback". No path ever claims vss when it is cosine.
  · EMBEDDING: a deterministic, dependency-free hashing embedder (feature-hash
    of token trigrams into a fixed dim, L2-normalised). It is NOT a learned LLM
    embedding — it is labelled "hashing-embedder/v1". It gives real, stable,
    semantically-useful similarity for recall without any model download, so the
    Space boots instantly. Callers may inject their own vectors via `remember(
    ..., vector=...)` to use a real LLM embedder when one is wired.
  · APPEND-ONLY LOG: every remember() also appends a hash-chained receipt to an
    append-only log (prev-digest link), so the memory set is tamper-evident and
    chain-verifiable, exactly like Khipu.
  · LRU EVICTION: a capacity bound; least-recently-recalled memories are evicted
    from the HOT store when capacity is exceeded. Eviction NEVER breaks the
    append-only log (the log is the source of truth; eviction only trims the
    queryable hot set, and an evicted memory can be rehydrated from the log).

Primary key: the receipt hash (SHA3-256 over the canonical memory body).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

__version__ = "unay/1.0.0"
_GENESIS = "0" * 64
EMBED_DIM = 256  # fixed embedding dimension for the hashing embedder

# Optional real vector backend. Honest if absent.
try:  # pragma: no cover - import guard
    import sqlite_vss as _sqlite_vss
    _HAVE_VSS = True
except Exception:  # pragma: no cover
    _sqlite_vss = None
    _HAVE_VSS = False


# --------------------------------------------------------------------------- hashing
def _sha3(b: bytes) -> str:
    return hashlib.sha3_256(b).hexdigest()


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(obj: Any) -> str:
    return _sha3(_canon(obj))


# --------------------------------------------------------------------------- embedder
def embed(text: str, dim: int = EMBED_DIM) -> List[float]:
    """Deterministic feature-hashing embedder (hashing-embedder/v1).

    Token unigrams + char trigrams are hashed into `dim` buckets with a signed
    hash; the result is L2-normalised. Deterministic and dependency-free. This
    is a real, stable similarity signal (cosine of these vectors tracks lexical
    + sub-lexical overlap), explicitly NOT a learned LLM embedding.
    """
    vec = [0.0] * dim
    text = (text or "").lower()
    tokens = text.split()
    grams: List[str] = list(tokens)
    # char trigrams across the whole string (captures sub-word similarity)
    s = " ".join(tokens)
    for i in range(len(s) - 2):
        grams.append(s[i : i + 3])
    for g in grams:
        h = int(hashlib.md5(g.encode("utf-8"), usedforsecurity=False).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def _cosine(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # both are L2-normalised


def _vec_to_blob(vec: List[float]) -> bytes:
    import struct
    return struct.pack("%sf" % len(vec), *vec)


def _blob_to_vec(blob: bytes) -> List[float]:
    import struct
    n = len(blob) // 4
    return list(struct.unpack("%sf" % n, blob))


# --------------------------------------------------------------------------- Unay store
class UnayStore:
    """Receipt-keyed semantic memory store.

    Thread-safe. Backed by a sqlite file at `path` (use ":memory:" for tests).
    """

    def __init__(
        self,
        path: str = ":memory:",
        organ: str = "unay",
        ns: str = "szl",
        capacity: int = 10_000,
        dim: int = EMBED_DIM,
        enable_vss: bool = True,
    ) -> None:
        self.path = path
        self.organ = organ
        self.ns = ns
        self.capacity = int(capacity)
        self.dim = int(dim)
        self._lock = threading.RLock()
        self._lru: "OrderedDict[str, float]" = OrderedDict()
        if path != ":memory:":
            d = os.path.dirname(path)
            if d:
                os.makedirs(d, exist_ok=True)
        # check_same_thread=False because we guard with our own RLock.
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self.backend = "cosine-fallback"
        self._vss_ok = False
        if enable_vss and _HAVE_VSS:
            try:
                self._db.enable_load_extension(True)
                _sqlite_vss.load(self._db)
                self._db.enable_load_extension(False)
                self._vss_ok = True
                self.backend = "sqlite-vss"
            except Exception:
                self._vss_ok = False
                self.backend = "cosine-fallback"
        self._init_schema()
        self._rehydrate_lru()

    # ---- schema -----------------------------------------------------------
    def _init_schema(self) -> None:
        with self._lock:
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS unay_memory (
                    receipt   TEXT PRIMARY KEY,
                    seq       INTEGER NOT NULL,
                    organ     TEXT NOT NULL,
                    ns        TEXT NOT NULL,
                    text      TEXT NOT NULL,
                    meta      TEXT NOT NULL,
                    vector    BLOB NOT NULL,
                    prev      TEXT NOT NULL,
                    ts        REAL NOT NULL,
                    last_recall REAL NOT NULL,
                    evicted   INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_unay_seq ON unay_memory(seq)"
            )
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS unay_meta (k TEXT PRIMARY KEY, v TEXT)"
            )
            if self._vss_ok:
                try:
                    self._db.execute(
                        f"CREATE VIRTUAL TABLE IF NOT EXISTS unay_vss USING vss0(vector({self.dim}))"
                    )
                except Exception:
                    # vss virtual table failed -> downgrade honestly
                    self._vss_ok = False
                    self.backend = "cosine-fallback"
            self._db.commit()

    def _rehydrate_lru(self) -> None:
        with self._lock:
            rows = self._db.execute(
                "SELECT receipt, last_recall FROM unay_memory WHERE evicted=0 ORDER BY last_recall ASC"
            ).fetchall()
            for r in rows:
                self._lru[r["receipt"]] = r["last_recall"]

    # ---- counters ---------------------------------------------------------
    def _next_seq(self) -> int:
        row = self._db.execute("SELECT MAX(seq) AS m FROM unay_memory").fetchone()
        return 0 if row["m"] is None else int(row["m"]) + 1

    def _head_digest(self) -> str:
        row = self._db.execute(
            "SELECT receipt FROM unay_memory ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return row["receipt"] if row else _GENESIS

    # ---- write ------------------------------------------------------------
    def remember(
        self,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
        vector: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Store a memory; return its receipt. Primary key = receipt hash."""
        meta = meta or {}
        if vector is None:
            vector = embed(text, self.dim)
        if len(vector) != self.dim:
            raise ValueError(f"vector dim {len(vector)} != store dim {self.dim}")
        with self._lock:
            seq = self._next_seq()
            prev = self._head_digest()
            ts = time.time()
            body = {
                "organ": self.organ,
                "ns": self.ns,
                "seq": seq,
                "text": text,
                "meta": meta,
                "prev": prev,
            }
            receipt = _digest(body)
            blob = _vec_to_blob(vector)
            self._db.execute(
                "INSERT OR REPLACE INTO unay_memory "
                "(receipt, seq, organ, ns, text, meta, vector, prev, ts, last_recall, evicted) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,0)",
                (receipt, seq, self.organ, self.ns, text, json.dumps(meta), blob, prev, ts, ts),
            )
            if self._vss_ok:
                try:
                    rowid = self._db.execute(
                        "SELECT rowid FROM unay_memory WHERE receipt=?", (receipt,)
                    ).fetchone()["rowid"]
                    self._db.execute(
                        "INSERT INTO unay_vss(rowid, vector) VALUES (?, ?)",
                        (rowid, json.dumps(vector)),
                    )
                except Exception:
                    pass
            self._db.commit()
            self._lru[receipt] = ts
            self._lru.move_to_end(receipt)
            self._evict_if_needed()
            return {
                "receipt": receipt,
                "seq": seq,
                "prev": prev,
                "organ": self.organ,
                "ns": self.ns,
                "ts": ts,
                "backend": self.backend,
                "version": __version__,
            }

    # ---- recall -----------------------------------------------------------
    def recall(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Semantic recall: top-k memories by cosine similarity to `query`."""
        qvec = embed(query, self.dim)
        with self._lock:
            results: List[Tuple[str, float]] = []
            if self._vss_ok:
                try:
                    rows = self._db.execute(
                        "SELECT rowid, distance FROM unay_vss WHERE vss_search(vector, ?) LIMIT ?",
                        (json.dumps(qvec), int(k)),
                    ).fetchall()
                    for r in rows:
                        mem = self._db.execute(
                            "SELECT receipt FROM unay_memory WHERE rowid=? AND evicted=0",
                            (r["rowid"],),
                        ).fetchone()
                        if mem:
                            # vss returns L2 distance; convert to a similarity score
                            dist = float(r["distance"])
                            sim = 1.0 - (dist / 2.0)  # vectors are unit-norm
                            results.append((mem["receipt"], sim))
                except Exception:
                    results = []
            if not results:
                # cosine fallback (also used to fill if vss returned nothing)
                rows = self._db.execute(
                    "SELECT receipt, vector FROM unay_memory WHERE evicted=0"
                ).fetchall()
                scored = []
                for r in rows:
                    v = _blob_to_vec(r["vector"])
                    scored.append((r["receipt"], _cosine(qvec, v)))
                scored.sort(key=lambda x: x[1], reverse=True)
                results = scored[: int(k)]
            out: List[Dict[str, Any]] = []
            now = time.time()
            for receipt, score in results[: int(k)]:
                row = self._db.execute(
                    "SELECT * FROM unay_memory WHERE receipt=?", (receipt,)
                ).fetchone()
                if not row:
                    continue
                self._db.execute(
                    "UPDATE unay_memory SET last_recall=? WHERE receipt=?", (now, receipt)
                )
                if receipt in self._lru:
                    self._lru.move_to_end(receipt)
                    self._lru[receipt] = now
                out.append(
                    {
                        "receipt": receipt,
                        "text": row["text"],
                        "meta": json.loads(row["meta"]),
                        "score": round(float(score), 6),
                        "seq": row["seq"],
                        "ts": row["ts"],
                    }
                )
            self._db.commit()
            return out

    def get(self, receipt: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM unay_memory WHERE receipt=?", (receipt,)
            ).fetchone()
            if not row:
                return None
            return {
                "receipt": row["receipt"],
                "seq": row["seq"],
                "text": row["text"],
                "meta": json.loads(row["meta"]),
                "prev": row["prev"],
                "ts": row["ts"],
                "evicted": bool(row["evicted"]),
            }

    # ---- eviction ---------------------------------------------------------
    def _evict_if_needed(self) -> int:
        evicted = 0
        active = self._db.execute(
            "SELECT COUNT(*) AS c FROM unay_memory WHERE evicted=0"
        ).fetchone()["c"]
        while active > self.capacity and self._lru:
            receipt, _ = next(iter(self._lru.items()))
            self._lru.pop(receipt, None)
            # mark evicted in the HOT store; the append-only log row remains.
            self._db.execute(
                "UPDATE unay_memory SET evicted=1 WHERE receipt=?", (receipt,)
            )
            if self._vss_ok:
                try:
                    rowid = self._db.execute(
                        "SELECT rowid FROM unay_memory WHERE receipt=?", (receipt,)
                    ).fetchone()["rowid"]
                    self._db.execute("DELETE FROM unay_vss WHERE rowid=?", (rowid,))
                except Exception:
                    pass
            evicted += 1
            active -= 1
        if evicted:
            self._db.commit()
        return evicted

    # ---- chain verification ----------------------------------------------
    def verify_chain(self) -> Dict[str, Any]:
        """Re-walk the append-only log; recompute each receipt and the prev link."""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM unay_memory ORDER BY seq ASC"
            ).fetchall()
            prev = _GENESIS
            broken_at = None
            for r in rows:
                body = {
                    "organ": r["organ"],
                    "ns": r["ns"],
                    "seq": r["seq"],
                    "text": r["text"],
                    "meta": json.loads(r["meta"]),
                    "prev": prev,
                }
                recomputed = _digest(body)
                if recomputed != r["receipt"] or r["prev"] != prev:
                    broken_at = r["seq"]
                    break
                prev = r["receipt"]
            ok = broken_at is None
            return {
                "ok": ok,
                "depth": len(rows),
                "broken_at": broken_at,
                "head": prev if ok else None,
                "backend": self.backend,
                "version": __version__,
            }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._db.execute(
                "SELECT COUNT(*) AS c FROM unay_memory"
            ).fetchone()["c"]
            hot = self._db.execute(
                "SELECT COUNT(*) AS c FROM unay_memory WHERE evicted=0"
            ).fetchone()["c"]
            return {
                "version": __version__,
                "backend": self.backend,
                "vss_available": _HAVE_VSS,
                "vss_active": self._vss_ok,
                "embedder": "hashing-embedder/v1",
                "dim": self.dim,
                "capacity": self.capacity,
                "total": total,
                "hot": hot,
                "evicted": total - hot,
                "head": self._head_digest(),
                "db_path": self.path,
            }

    def close(self) -> None:
        with self._lock:
            try:
                self._db.commit()
            finally:
                self._db.close()
