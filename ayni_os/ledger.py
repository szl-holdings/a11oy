"""Reciprocity ledger — the AYNI-OS reciprocity organism.

A real, append-only, double-entry give/take ledger over the empire's 14 organs.
Every resource movement is recorded as a KIPU receipt. Reciprocity (Ayni) is the
*pairing* of a take with one or more future gives that return >= the consumed amount
to the drained organ within a finite time-lag tau_max (Trivers 1971 "time-lagged
symbiosis"; Axelrod & Hamilton 1981 direct reciprocity).

This module is pure stdlib (open-source: Python only). No mysticism.
"""
from __future__ import annotations

import hashlib
import json
import time as _time
from dataclasses import dataclass, asdict, field
from typing import Iterable, Optional


# Doctrine v11: 14 organs.
ORGANS = (
    "amaru", "sentra", "rosie", "vessels", "killinchu", "kanchay", "wayra",
    "puriq", "yuyay", "hukla", "khipu", "lambda_spine", "yawar", "tinkuy",
)
assert len(ORGANS) == 14, "Doctrine v11 LOCKED: 14 organs"


def _now() -> float:
    return _time.time()


@dataclass(frozen=True)
class Receipt:
    """A single KIPU ledger entry (event). Append-only, content-addressed.

    side:   'take' (organ consumes resource r, amount>0 leaving the organ)
            'give' (organ receives resource r, amount>0 entering the organ)
    pair_id: links a take to the give(s) that reciprocate it (Ayni pairing).
    prev_hash / entry_hash: KIPU receipt chain (tamper-evident).
    """
    seq: int
    ts: float
    organ: str
    side: str            # 'take' | 'give'
    resource: str
    amount: float
    pair_id: str
    prev_hash: str
    entry_hash: str = ""

    def signed_payload(self) -> str:
        d = {k: v for k, v in asdict(self).items() if k != "entry_hash"}
        return json.dumps(d, sort_keys=True, separators=(",", ":"))

    def compute_hash(self) -> str:
        return hashlib.sha256(self.signed_payload().encode()).hexdigest()


class ReciprocityLedger:
    """Append-only double-entry reciprocity ledger (event store)."""

    def __init__(self) -> None:
        self._entries: list[Receipt] = []

    # ---- write path -----------------------------------------------------
    def _append(self, organ: str, side: str, resource: str, amount: float,
                pair_id: str, ts: Optional[float] = None) -> Receipt:
        if organ not in ORGANS:
            raise ValueError(f"unknown organ {organ!r}")
        if side not in ("take", "give"):
            raise ValueError("side must be 'take' or 'give'")
        if amount < 0:
            raise ValueError("amount must be >= 0")
        seq = len(self._entries)
        prev_hash = self._entries[-1].entry_hash if self._entries else "GENESIS"
        r = Receipt(
            seq=seq, ts=ts if ts is not None else _now(), organ=organ,
            side=side, resource=resource, amount=amount, pair_id=pair_id,
            prev_hash=prev_hash,
        )
        r = Receipt(**{**asdict(r), "entry_hash": r.compute_hash()})
        self._entries.append(r)
        return r

    def record_exchange(self, *, taker: str, giver: str, resource: str,
                        amount: float, pair_id: str,
                        ts: Optional[float] = None) -> tuple[Receipt, Receipt]:
        """Record a balanced internal exchange as a DOUBLE-ENTRY pair:
        `giver` gives `amount` of `resource` to `taker` (taker's take is the
        consumption; giver's give is the reciprocation source). Internal exchanges
        net to zero across the empire (Ayni conservation, double-entry).
        Returns (take_receipt, give_receipt).
        """
        base = ts if ts is not None else _now()
        take = self._append(taker, "take", resource, amount, pair_id, ts=base)
        give = self._append(giver, "give", resource, amount, pair_id, ts=base)
        return take, give

    def reciprocate(self, *, organ: str, resource: str, amount: float,
                    pair_id: str, ts: Optional[float] = None) -> Receipt:
        """Record a future give that returns resource to a previously-drained organ.
        This is the Ayni 'pay-back' leg closing a pair_id (>= original take)."""
        return self._append(organ, "give", resource, amount, pair_id, ts=ts)

    def drain(self, *, organ: str, resource: str, amount: float,
              pair_id: str, ts: Optional[float] = None) -> Receipt:
        """Record an unmatched take (a net drain on `organ`)."""
        return self._append(organ, "take", resource, amount, pair_id, ts=ts)

    # ---- read path ------------------------------------------------------
    def entries(self, until_ts: Optional[float] = None) -> list[Receipt]:
        if until_ts is None:
            return list(self._entries)
        return [e for e in self._entries if e.ts <= until_ts]

    def verify_chain(self, until_ts: Optional[float] = None) -> bool:
        """Verify KIPU receipt chain integrity up to until_ts."""
        prev = "GENESIS"
        for e in self.entries(until_ts):
            if e.prev_hash != prev:
                return False
            if e.compute_hash() != e.entry_hash:
                return False
            prev = e.entry_hash
        return True

    def flows(self, organ: str, lo: float = float("-inf"),
              hi: float = float("inf")) -> tuple[float, float]:
        """Return (In_o, Out_o) over [lo, hi] for `organ`."""
        gin = sum(e.amount for e in self._entries
                  if e.organ == organ and e.side == "give" and lo <= e.ts <= hi)
        out = sum(e.amount for e in self._entries
                  if e.organ == organ and e.side == "take" and lo <= e.ts <= hi)
        return gin, out

    def ayni_coefficient(self, organ: str, lo: float = float("-inf"),
                         hi: float = float("inf")) -> float:
        """alpha_o = In / (In + Out); 0.5 when idle (both zero)."""
        gin, out = self.flows(organ, lo, hi)
        if gin + out == 0:
            return 0.5
        return gin / (gin + out)

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(asdict(e), sort_keys=True) for e in self._entries)

    @classmethod
    def from_jsonl(cls, text: str) -> "ReciprocityLedger":
        led = cls()
        for line in text.splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            led._entries.append(Receipt(**d))
        return led
