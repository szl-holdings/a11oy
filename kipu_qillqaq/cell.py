"""ReceiptCell — a content-addressed receipt (a "knot" in the KIPU).

A ReceiptCell is an immutable record of one act: who wrote it, what organ, what kind of
receipt, the payload, the timestamp, and an optional pointer to parent cells (forming a
content-addressed DAG like git/IPLD). The content address is the SHA-256 of the canonical
JSON of the cell's *content* fields (everything except the address itself).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any


def _canonical(obj: Any) -> bytes:
    """Deterministic JSON encoding for hashing (sorted keys, no whitespace drift)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_address(content: dict) -> str:
    """SHA-256 hex content address of a cell's content dict. Pure function."""
    return hashlib.sha256(_canonical(content)).hexdigest()


@dataclass(frozen=True)
class ReceiptCell:
    """An immutable, content-addressed receipt cell.

    `cid` is derived from the content fields and is the cell's identity in the pool.
    """

    organ: str
    kind: str
    payload: dict
    author: str = "Yachay"
    ts: float = field(default_factory=lambda: time.time())
    parents: tuple = ()  # tuple of parent CIDs -> DAG edges
    cid: str = ""  # filled in __post_init__

    def __post_init__(self):
        if not self.cid:
            object.__setattr__(self, "cid", content_address(self._content()))

    def _content(self) -> dict:
        return {
            "organ": self.organ,
            "kind": self.kind,
            "payload": self.payload,
            "author": self.author,
            "ts": self.ts,
            "parents": list(self.parents),
        }

    def verify(self) -> bool:
        """Chain-verify: recompute the content address and compare. True iff intact."""
        return self.cid == content_address(self._content())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["parents"] = list(self.parents)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ReceiptCell":
        return cls(
            organ=d["organ"],
            kind=d["kind"],
            payload=d["payload"],
            author=d.get("author", "Yachay"),
            ts=d["ts"],
            parents=tuple(d.get("parents", ())),
            cid=d.get("cid", ""),
        )

    def to_bytes(self) -> bytes:
        return _canonical(self.to_dict())

    @classmethod
    def from_bytes(cls, b: bytes) -> "ReceiptCell":
        return cls.from_dict(json.loads(b.decode("utf-8")))
