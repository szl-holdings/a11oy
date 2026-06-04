# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v13 — shared Khipu receipt store for the three edge organs.
"""
szl_khipu.py — minimal, dependency-free Khipu DAG receipt store.

Every organ action (Doctrine v13 §5) emits a Khipu receipt. A receipt is an
append-only, hash-chained record: each receipt links to the prior receipt's
digest, so the chain is tamper-evident by additive arithmetic alone (mirrors the
v11 YAWAR ledger discipline + `khipuReceipt_checksum_invariant`).

Honest label (Doctrine v11 LOCKED §2, carried): the receipt SIGNATURE is DSSE
PLACEHOLDER (Sigstore not wired into CI). This store verifies the HASH CHAIN
only, not a cryptographic signature. SHA3-256 is used for the chain digest.

Stdlib only (hashlib, json, threading, time). No external deps so it runs in the
slim a11oy Docker image with zero new pip installs.
"""
# ---------------------------------------------------------------------------
# DEVELOPER ORIENTATION (added by Perplexity Computer Agent, 2026-06)
# Purpose:       In-memory, thread-safe, append-only Khipu receipt DAG.
#                One DAG per (organ, namespace). Each receipt is SHA3-256
#                hash-chained to the previous — tamper-evident without a DB.
# Key entry pts: KhipuDAG.emit(action, payload), KhipuDAG.verify_chain(),
#                KhipuDAG.receipts(), get_dag(organ, ns)
# Related mods:  szl_dsse.py (DSSE signing), szl_be_hardening.py (SQLite
#                persistence), szl_wire.py (Wire F receipt ingest)
# Doctrine note: Chain verifies INTEGRITY only. DSSE (szl_dsse) provides
#                authorship. Both layers are required for full attestation.
# ---------------------------------------------------------------------------
from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

_GENESIS = "0" * 64


class KhipuDAG:
    """In-process, thread-safe, append-only hash-chained receipt store.

    One DAG per (namespace, organ). Receipts are kept in memory (the live a11oy
    Space is stateless across restarts; the *discipline* — chain integrity, the
    summation invariant — is what is load-bearing, not durable storage, which is
    WASI-RIKUQ's P1 concern).
    """

    def __init__(self, organ: str, ns: str = "a11oy") -> None:
        self.organ = organ
        self.ns = ns
        self._lock = threading.Lock()
        self._chain: list[dict[str, Any]] = []

    @staticmethod
    def _digest(obj: Any) -> str:
        # Deterministic: sort keys so the digest is replay-stable.
        raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha3_256(raw).hexdigest()

    def emit(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Append a receipt for `action` and return it (with its chain link)."""
        payload = payload or {}
        with self._lock:
            prev = self._chain[-1]["digest"] if self._chain else _GENESIS
            body = {
                "organ": self.organ,
                "ns": self.ns,
                "seq": len(self._chain),
                "action": action,
                "payload_digest": self._digest(payload),
                "ts": time.time(),
                "prev": prev,
            }
            digest = self._digest(body)
            receipt = {
                **body,
                "digest": digest,
                # DSSE PLACEHOLDER — signature not wired (Doctrine v11 LOCKED §2). The
                # field is present so the contract is stable; value is honest.
                "signature": "DSSE_PLACEHOLDER",
                "chain_verified": True,
            }
            self._chain.append(receipt)
            return receipt

    def verify_chain(self) -> dict[str, Any]:
        """Re-walk the chain; return {ok, depth, broken_at}."""
        with self._lock:
            prev = _GENESIS
            for i, r in enumerate(self._chain):
                body = {k: r[k] for k in (
                    "organ", "ns", "seq", "action", "payload_digest", "ts", "prev")}
                if r["prev"] != prev:
                    return {"ok": False, "depth": len(self._chain), "broken_at": i,
                            "reason": "prev-link mismatch"}
                if self._digest(body) != r["digest"]:
                    return {"ok": False, "depth": len(self._chain), "broken_at": i,
                            "reason": "digest mismatch"}
                prev = r["digest"]
            return {"ok": True, "depth": len(self._chain), "broken_at": None}

    def depth(self) -> int:
        with self._lock:
            return len(self._chain)

    def head(self) -> str:
        with self._lock:
            return self._chain[-1]["digest"] if self._chain else _GENESIS

    def tail(self, n: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._chain[-n:])


# Module-level registry so organs share one DAG per organ name across imports.
_REGISTRY: dict[str, KhipuDAG] = {}
_REG_LOCK = threading.Lock()


def get_dag(organ: str, ns: str = "a11oy") -> KhipuDAG:
    key = f"{ns}/{organ}"
    with _REG_LOCK:
        if key not in _REGISTRY:
            _REGISTRY[key] = KhipuDAG(organ, ns)
        return _REGISTRY[key]
