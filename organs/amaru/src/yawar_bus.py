"""YAWAR — blood / receipt bus. Append-only, immutable receipts.

Doctrine D-YAWAR-FLOW: agents READ never WRITE. Writes only at RUWAY.
Doctrine: ≤10 SLOC for append + snapshot.
SENTRA hooks inspect every appended packet (immune system).
"""
import hashlib
import json
from typing import Any


class Yawar:
    def __init__(self): self.receipts = []; self.snapshots = {}
    def append(self, packet: dict, sentra_inspect: Any = None) -> str:
        if sentra_inspect and not sentra_inspect(packet):
            raise PermissionError("SENTRA rejected packet")
        h = hashlib.sha256(json.dumps(packet, sort_keys=True, default=str).encode()).hexdigest()
        self.receipts.append({"hash": h, "packet": packet})   # immutable append
        return h
    def snapshot(self, layer: str, data: dict) -> None:
        self.snapshots[layer] = json.loads(json.dumps(data, default=str))  # frozen copy
    def read(self, layer: str) -> dict: return self.snapshots.get(layer, {})
