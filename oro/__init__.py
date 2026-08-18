# SPDX-License-Identifier: Apache-2.0
"""ORO — Obligation-Ranked Orbits.

The package separates deterministic rank/barrier governance, durable evidence,
managed signing, service orchestration, and HTTP delivery. Importing this
package performs no network call, starts no worker, and mutates no state.
"""

from .core import (
    Allocation,
    Arrival,
    BarrierDecision,
    BarrierEngine,
    CodexManifest,
    InvariantBinding,
    OROContractError,
    OROSignerUnavailable,
    OROStateError,
    Rank,
    RoleSpec,
    allocate_rank,
    canonical_json,
    semantic_hash,
)
from .service import OROService
from .store import OROStore

__all__ = [
    "Allocation",
    "Arrival",
    "BarrierDecision",
    "BarrierEngine",
    "CodexManifest",
    "InvariantBinding",
    "OROContractError",
    "OROSignerUnavailable",
    "OROService",
    "OROStateError",
    "OROStore",
    "Rank",
    "RoleSpec",
    "allocate_rank",
    "canonical_json",
    "semantic_hash",
]
