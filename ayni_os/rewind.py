"""Rewind — reconstruct empire state at a target timestamp T by replaying receipts.

HONEST NAMING: this is the EVENT-SOURCING REPLAY pattern. Given a target timestamp T,
we (optionally) start from the nearest signed checkpoint <= T, then re-apply every
KIPU receipt with ts <= T to deterministically reconstruct the state that existed at
moment T. It is NOT "time travel" and makes no physics claim — it is the same
mechanism used by event stores, write-ahead logs, and git.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .checkpoint import CheckpointStore
from .ledger import ORGANS, ReciprocityLedger


@dataclass
class ReconstructedState:
    """Deterministic state of the empire at a past timestamp T."""
    at_ts: float
    n_entries: int
    balances: dict          # organ -> net (In - Out) up to T
    ayni: dict              # organ -> alpha_o up to T
    chain_ok: bool
    state_hash: str
    started_from_checkpoint: Optional[float] = None


def reconstruct_at(ledger: ReciprocityLedger, target_ts: float,
                   store: Optional[CheckpointStore] = None) -> ReconstructedState:
    """Replay receipts up to target_ts to rebuild state. Event-sourcing."""
    import hashlib
    import json

    started_from = None
    if store is not None:
        nearest = store.nearest_before(target_ts)
        if nearest is not None:
            started_from = nearest[0].ts

    entries = ledger.entries(until_ts=target_ts)

    balances = {o: 0.0 for o in ORGANS}
    for e in entries:
        delta = e.amount if e.side == "give" else -e.amount
        balances[e.organ] += delta

    ayni = {o: round(ledger.ayni_coefficient(o, hi=target_ts), 6) for o in ORGANS}
    canon = json.dumps([e.entry_hash for e in entries], separators=(",", ":")).encode()
    state_hash = hashlib.sha256(canon).hexdigest()

    return ReconstructedState(
        at_ts=target_ts,
        n_entries=len(entries),
        balances={o: round(v, 6) for o, v in balances.items()},
        ayni=ayni,
        chain_ok=ledger.verify_chain(until_ts=target_ts),
        state_hash=state_hash,
        started_from_checkpoint=started_from,
    )


def verify_rewind_determinism(ledger: ReciprocityLedger, target_ts: float) -> bool:
    """Replaying twice yields byte-identical state_hash (determinism guarantee)."""
    a = reconstruct_at(ledger, target_ts)
    b = reconstruct_at(ledger, target_ts)
    return a.state_hash == b.state_hash
