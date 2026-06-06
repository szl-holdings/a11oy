# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries · 13-axis
# Signed: Yachay.  git trailer: Perplexity Computer Agent
"""
szl_khipu_replicate.py — cross-Space Khipu replication thread (OPTIONAL).

Replication is DISABLED BY DEFAULT. Each Space's handler ACCEPTS inbound
replications (idempotent: a receipt already present is a no-op) but NEVER pushes
outbound until replication is explicitly enabled via enable() / env var.

Wire: HTTP POST to a sibling Space's
    /api/<organ>/v2/khipu/replicate
with body {"receipts": [<receipt>, ...]}. The receiver re-verifies each
receipt's digest before accepting it (no blind trust), and stores accepted
receipts in a local "replicated" sub-store keyed by digest (it does NOT splice
foreign receipts into its own primary append-only chain — replication is a
mirror, not a merge, so each Space's own chain integrity is never disturbed).

Outbound push uses urllib (stdlib) so there is no hard `requests` dependency.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from typing import Any, Callable, Dict, List, Optional

__version__ = "khipu-replicate/1.0.0"


class Replicator:
    """Optional outbound replicator. Disabled until enable() is called."""

    def __init__(
        self,
        local_organ: str,
        peers: Optional[List[str]] = None,
        source_fn: Optional[Callable[[int], List[Dict[str, Any]]]] = None,
        interval_s: float = 30.0,
    ) -> None:
        self.local_organ = local_organ
        # peers are full base URLs e.g. https://szlholdings-amaru.hf.space
        self.peers = list(peers or [])
        # source_fn(since_seq) -> list of receipts to push (caller supplies)
        self.source_fn = source_fn
        self.interval_s = interval_s
        # ENABLED only if explicitly turned on. Env var honoured but defaults off.
        self.enabled = os.environ.get("KHIPU_REPLICATION", "0") == "1"
        self._cursor = 0
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.last_push: Dict[str, Any] = {}

    def enable(self) -> None:
        with self._lock:
            self.enabled = True

    def disable(self) -> None:
        with self._lock:
            self.enabled = False

    def _post(self, base: str, receipts: List[Dict[str, Any]]) -> Dict[str, Any]:
        url = base.rstrip("/") + f"/api/{_organ_of(base)}/v2/khipu/replicate"
        data = json.dumps({"receipts": receipts}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def push_once(self) -> Dict[str, Any]:
        """Push receipts newer than the cursor to every peer. No-op if disabled."""
        if not self.enabled:
            return {"pushed": 0, "enabled": False, "reason": "replication disabled"}
        if not self.source_fn:
            return {"pushed": 0, "enabled": True, "reason": "no source_fn"}
        receipts = self.source_fn(self._cursor)
        if not receipts:
            return {"pushed": 0, "enabled": True, "peers": len(self.peers)}
        results = {}
        for base in self.peers:
            try:
                results[base] = self._post(base, receipts)
            except Exception as e:  # honest: record failure, never crash
                results[base] = {"error": repr(e)}
        self._cursor += len(receipts)
        self.last_push = {"ts": time.time(), "count": len(receipts), "results": results}
        return {"pushed": len(receipts), "enabled": True, "results": results}

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self.enabled:
                    self.push_once()
            except Exception:
                pass
            self._stop.wait(self.interval_s)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def status(self) -> Dict[str, Any]:
        return {
            "version": __version__,
            "enabled": self.enabled,
            "peers": self.peers,
            "cursor": self._cursor,
            "interval_s": self.interval_s,
            "last_push": self.last_push,
        }


def _organ_of(base: str) -> str:
    # szlholdings-amaru.hf.space -> amaru ; falls back to last path-ish token
    host = base.split("//")[-1].split("/")[0]
    if "-" in host:
        return host.split("-", 1)[1].split(".")[0]
    return host.split(".")[0]


def verify_inbound(receipt: Dict[str, Any]) -> bool:
    """Re-verify a foreign receipt's self-digest before accepting it."""
    import hashlib

    required = {"organ", "ns", "seq", "action", "payload_digest", "prev", "digest"}
    if not required.issubset(receipt.keys()):
        return False
    body = {
        "organ": receipt["organ"],
        "ns": receipt["ns"],
        "seq": receipt["seq"],
        "action": receipt["action"],
        "payload_digest": receipt["payload_digest"],
        "prev": receipt["prev"],
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha3_256(raw).hexdigest() == receipt["digest"]
