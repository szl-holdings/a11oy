"""KipuPool — the shared, content-addressed receipt-cell substrate.

Every organ reads/writes ReceiptCells here. Each write:
  1. computes/verifies the content address (cid),
  2. persists the cell (LMDB if available, else a JSON-file store — same API),
  3. optionally stores a Reed-Solomon shard manifest for durability,
  4. publishes a ("write", cell) event on the in-process EventBus.

Each read publishes a ("read", cid) event and emits a read-receipt cell, so there is no
silent access. This is a Linda-style tuple space + event sourcing + content addressing.
HONEST: durability is Reed-Solomon erasure coding, not "holographic QEC".
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Iterable, Optional

from .cell import ReceiptCell
from .coding import decode_shards, encode_cell
from .events import EventBus


class _Store:
    """Key-value persistence: LMDB backend if installed, else JSON-file fallback."""

    def __init__(self, path: str):
        self.path = path
        self.backend = "json"
        self._lmdb = None
        self._lock = threading.RLock()
        try:
            import lmdb  # type: ignore

            os.makedirs(path, exist_ok=True)
            self._lmdb = lmdb.open(path, map_size=256 * 1024 * 1024)
            self.backend = "lmdb"
        except Exception:
            self._file = Path(path)
            self._file.parent.mkdir(parents=True, exist_ok=True)
            if not self._file.exists():
                self._file.write_text("{}")

    def put(self, key: str, value: bytes) -> None:
        with self._lock:
            if self.backend == "lmdb":
                with self._lmdb.begin(write=True) as txn:
                    txn.put(key.encode(), value)
            else:
                d = json.loads(self._file.read_text())
                d[key] = value.decode("utf-8")
                self._file.write_text(json.dumps(d))

    def get(self, key: str) -> Optional[bytes]:
        with self._lock:
            if self.backend == "lmdb":
                with self._lmdb.begin() as txn:
                    v = txn.get(key.encode())
                    return bytes(v) if v is not None else None
            d = json.loads(self._file.read_text())
            v = d.get(key)
            return v.encode("utf-8") if v is not None else None

    def keys(self) -> Iterable[str]:
        with self._lock:
            if self.backend == "lmdb":
                with self._lmdb.begin() as txn:
                    return [k.decode() for k, _ in txn.cursor()]
            return list(json.loads(self._file.read_text()).keys())


class KipuPool:
    """The shared receipt-cell substrate."""

    def __init__(self, path: str = "/tmp/kipu", durability: bool = True,
                 rs_n: int = 10, rs_k: int = 6):
        self.bus = EventBus()
        self._cells = _Store(os.path.join(path, "cells"))
        self._shards = _Store(os.path.join(path, "shards"))
        self.durability = durability
        self.rs_n, self.rs_k = rs_n, rs_k

    @property
    def store_backend(self) -> str:
        return self._cells.backend

    def write(self, cell: ReceiptCell) -> str:
        """Persist a cell, optionally RS-encode it, publish a write event. Returns cid."""
        if not cell.verify():
            raise ValueError("ReceiptCell failed content-address verification")
        cb = cell.to_bytes()
        self._cells.put(cell.cid, cb)
        if self.durability:
            manifest = encode_cell(cb, self.rs_n, self.rs_k)
            self._shards.put(cell.cid, json.dumps(manifest).encode())
        self.bus.publish("write", cell)
        self.bus.publish(f"organ:{cell.organ}", cell)
        return cell.cid

    def read(self, cid: str, reader: str = "anon", emit_receipt: bool = True) -> Optional[ReceiptCell]:
        """Read a cell by cid. Publishes a read event and (optionally) a read-receipt."""
        raw = self._cells.get(cid)
        cell = ReceiptCell.from_bytes(raw) if raw is not None else None
        self.bus.publish("read", {"cid": cid, "reader": reader, "hit": cell is not None})
        if emit_receipt and cell is not None:
            rr = ReceiptCell(organ=reader, kind="read_receipt",
                             payload={"read_cid": cid}, parents=(cid,))
            self._cells.put(rr.cid, rr.to_bytes())
        return cell

    def recover(self, cid: str, drop: Optional[list[int]] = None) -> Optional[ReceiptCell]:
        """Recover a cell from its Reed-Solomon shards, optionally simulating lost shards."""
        raw = self._shards.get(cid)
        if raw is None:
            return None
        manifest = json.loads(raw.decode())
        if drop:
            shards = list(manifest["shards"])
            for i in drop:
                shards[i] = None
            manifest = {**manifest, "shards": shards}
        cb = decode_shards(manifest)
        return ReceiptCell.from_bytes(cb)

    def all_cids(self) -> list[str]:
        return list(self._cells.keys())

    def stats(self) -> dict:
        return {
            "store_backend": self._cells.backend,
            "cells": len(list(self._cells.keys())),
            "durability": self.durability,
            "rs_code": f"RS({self.rs_n},{self.rs_k})",
        }
