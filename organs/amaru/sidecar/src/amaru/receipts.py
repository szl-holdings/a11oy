"""
Receipt chain — local SHA-256 linked receipts used by every chakra evaluation
and every scheduler tick.

Mirrors the shape of `@szl-holdings/szl-receipts` (LambdaReceipt) so receipts
written here can be reasoned about by the same TypeScript consumers without
re-serialisation drift.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any

# Shared canonicalisation (szl-holdings/szl-evidence-core @ de27568d706c): identical bytes to
# the local implementation below for every valid JSON value, with the profile declared
# explicitly (CANON_UTF8: UTF-8). One deliberate difference: NaN/Infinity
# raise at emit time instead of producing text no conforming JSON reader can parse.
# The local implementation stays as the fallback so nothing here depends on the package.
try:
    from szl_evidence_core.canonical import CANON_UTF8 as _CANON_PROFILE
    from szl_evidence_core.canonical import canonical_json as _shared_canonical_json
    _CANON_SOURCE = "szl_evidence_core"
except Exception:  # pragma: no cover - fallback to the local implementation
    _CANON_PROFILE = 'szl.lambda/v1'
    _shared_canonical_json = None
    _CANON_SOURCE = "local"


def canonical_json(value: Any) -> str:
    if _shared_canonical_json is not None:
        return _shared_canonical_json(value, profile=_CANON_PROFILE, check=False)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_json(value: Any) -> str:
    return sha256_hex(canonical_json(value))


GENESIS_PREV_HASH = "0" * 64


@dataclass
class Receipt:
    seq: int
    ts: str
    endpoint: str
    method: str
    params_hash: str
    result_hash: str | None
    operator_id: str
    prev_hash: str
    self_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "endpoint": self.endpoint,
            "method": self.method,
            "paramsHash": self.params_hash,
            "resultHash": self.result_hash,
            "operatorId": self.operator_id,
            "prevHash": self.prev_hash,
            "selfHash": self.self_hash,
            "metadata": self.metadata,
        }


class ReceiptChain:
    """In-memory append-only receipt chain."""

    def __init__(self, operator_id: str = "amaru-runtime") -> None:
        self._operator_id = operator_id
        self._lock = threading.Lock()
        self._receipts: list[Receipt] = []

    def append(
        self,
        *,
        endpoint: str,
        method: str,
        params: Any,
        result: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Receipt:
        with self._lock:
            seq = len(self._receipts) + 1
            prev_hash = (
                self._receipts[-1].self_hash if self._receipts else GENESIS_PREV_HASH
            )
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            params_hash = hash_json(params)
            result_hash = hash_json(result) if result is not None else None
            partial = {
                "seq": seq,
                "ts": ts,
                "endpoint": endpoint,
                "method": method,
                "paramsHash": params_hash,
                "resultHash": result_hash,
                "operatorId": self._operator_id,
                "prevHash": prev_hash,
                "metadata": metadata or {},
            }
            self_hash = hash_json(partial)
            receipt = Receipt(
                seq=seq,
                ts=ts,
                endpoint=endpoint,
                method=method,
                params_hash=params_hash,
                result_hash=result_hash,
                operator_id=self._operator_id,
                prev_hash=prev_hash,
                self_hash=self_hash,
                metadata=metadata or {},
            )
            self._receipts.append(receipt)
            return receipt

    def head(self) -> Receipt | None:
        with self._lock:
            return self._receipts[-1] if self._receipts else None

    def all(self) -> list[Receipt]:
        with self._lock:
            return list(self._receipts)

    def length(self) -> int:
        with self._lock:
            return len(self._receipts)
