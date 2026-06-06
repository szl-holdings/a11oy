"""
huklla-10 — the ten Quechua tripwires that guard the Amaru runtime.

Each tripwire is a pure predicate over runtime snapshot. Tripwires never
mutate state — they only report. The scheduler reads `evaluate_all()` once
per tick and surfaces the result on `GET /tripwires`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from . import CHAKRA_ORDER

# Module-level boot timestamp. Used to implement a cold-start grace period
# so tripwires huklla-5 and huklla-7 don't fire warnings before the operator
# has had time to trigger a first tick or bus publish.
_BOOT_TIME: float = time.monotonic()
_GRACE_PERIOD_SECONDS: float = 60.0


def _in_grace_period() -> bool:
    """Return True if the module has been running for less than 60 seconds."""
    return (time.monotonic() - _BOOT_TIME) < _GRACE_PERIOD_SECONDS

TripwirePredicate = Callable[[dict[str, Any]], "TripwireResult"]


@dataclass(frozen=True)
class TripwireResult:
    id: str
    title: str
    status: str  # "pass" | "warn" | "trip"
    detail: str


@dataclass(frozen=True)
class Tripwire:
    id: str
    title: str
    description: str
    predicate: TripwirePredicate


def _t_all_chakras_registered(snap: dict[str, Any]) -> TripwireResult:
    registered = set(snap.get("registered_chakras", []))
    missing = [c for c in CHAKRA_ORDER if c not in registered]
    if not missing:
        return TripwireResult("huklla-1", "all_chakras_registered", "pass", "7/7")
    return TripwireResult(
        "huklla-1",
        "all_chakras_registered",
        "trip",
        f"missing: {', '.join(missing)}",
    )


def _t_receipt_chain_intact(snap: dict[str, Any]) -> TripwireResult:
    breaks = snap.get("chain_breaks", 0)
    if breaks == 0:
        return TripwireResult("huklla-2", "receipt_chain_intact", "pass", "no breaks")
    return TripwireResult(
        "huklla-2", "receipt_chain_intact", "trip", f"{breaks} broken links"
    )


def _t_proofs_present(snap: dict[str, Any]) -> TripwireResult:
    missing = snap.get("chakras_missing_proof", [])
    if not missing:
        return TripwireResult("huklla-3", "proofs_present", "pass", "all proofs found")
    return TripwireResult(
        "huklla-3", "proofs_present", "warn", f"missing proof: {', '.join(missing)}"
    )


def _t_no_silent_stubs(snap: dict[str, Any]) -> TripwireResult:
    stubs = snap.get("stubbed_chakras", [])
    if not stubs:
        return TripwireResult("huklla-4", "no_silent_stubs", "pass", "0 stubs")
    return TripwireResult(
        "huklla-4",
        "no_silent_stubs",
        "warn",
        f"stubbed (surfaced loudly): {', '.join(stubs)}",
    )


def _t_scheduler_progressing(snap: dict[str, Any]) -> TripwireResult:
    ticks = snap.get("scheduler_ticks", 0)
    if ticks > 0:
        return TripwireResult(
            "huklla-5", "scheduler_progressing", "pass", f"{ticks} ticks"
        )
    # Suppress warn during the first 60 s after boot — a freshly-booted Space
    # has not had time to run a scheduler tick yet (cold-start grace period).
    if _in_grace_period():
        return TripwireResult(
            "huklla-5", "scheduler_progressing", "pass",
            "no ticks yet (cold-start grace period active)"
        )
    return TripwireResult(
        "huklla-5", "scheduler_progressing", "warn", "no ticks yet"
    )


def _t_wiring_acyclic_ex_ouroboros(snap: dict[str, Any]) -> TripwireResult:
    # Ascent edges are linear root→crown; only the explicit ouroboros edge cycles.
    extra = snap.get("unexpected_cycles", 0)
    if extra == 0:
        return TripwireResult(
            "huklla-6", "wiring_acyclic_ex_ouroboros", "pass", "only ouroboros cycle"
        )
    return TripwireResult(
        "huklla-6",
        "wiring_acyclic_ex_ouroboros",
        "trip",
        f"{extra} unexpected cycles",
    )


def _t_bus_publish_succeeded(snap: dict[str, Any]) -> TripwireResult:
    publishes = snap.get("bus_publishes", 0)
    failures = snap.get("bus_publish_failures", 0)
    if publishes == 0:
        # Suppress warn during the first 60 s after boot — no operator action
        # has been taken yet on a freshly-booted Space (cold-start grace period).
        if _in_grace_period():
            return TripwireResult(
                "huklla-7", "bus_publish_succeeded", "pass",
                "no publishes yet (cold-start grace period active)"
            )
        return TripwireResult("huklla-7", "bus_publish_succeeded", "warn", "no publishes yet")
    if failures == 0:
        return TripwireResult(
            "huklla-7", "bus_publish_succeeded", "pass", f"{publishes} ok"
        )
    return TripwireResult(
        "huklla-7",
        "bus_publish_succeeded",
        "warn",
        f"{failures}/{publishes} publishes failed (bus may be down)",
    )


def _t_leader_doctrine_loaded(snap: dict[str, Any]) -> TripwireResult:
    missing = snap.get("chakras_missing_leader", [])
    if not missing:
        return TripwireResult(
            "huklla-8", "leader_doctrine_loaded", "pass", "all LEADER.md present"
        )
    return TripwireResult(
        "huklla-8",
        "leader_doctrine_loaded",
        "trip",
        f"missing LEADER.md: {', '.join(missing)}",
    )


def _t_inputs_bounded(snap: dict[str, Any]) -> TripwireResult:
    oversized = snap.get("oversized_envelopes", 0)
    if oversized == 0:
        return TripwireResult("huklla-9", "inputs_bounded", "pass", "no oversized envelopes")
    return TripwireResult(
        "huklla-9", "inputs_bounded", "warn", f"{oversized} oversized envelopes"
    )


def _t_canonical_order(snap: dict[str, Any]) -> TripwireResult:
    declared = snap.get("declared_order", list(CHAKRA_ORDER))
    if declared == list(CHAKRA_ORDER):
        return TripwireResult("huklla-10", "canonical_order", "pass", "root→crown")
    return TripwireResult(
        "huklla-10", "canonical_order", "trip", f"declared: {declared}"
    )


TRIPWIRES: tuple[Tripwire, ...] = (
    Tripwire("huklla-1", "all_chakras_registered", "All 7 chakra kernels are registered.", _t_all_chakras_registered),
    Tripwire("huklla-2", "receipt_chain_intact", "Receipt chain has no broken prev/self hashes.", _t_receipt_chain_intact),
    Tripwire("huklla-3", "proofs_present", "Every chakra has a proof.json on disk.", _t_proofs_present),
    Tripwire("huklla-4", "no_silent_stubs", "Stubbed kernels are surfaced, never faked.", _t_no_silent_stubs),
    Tripwire("huklla-5", "scheduler_progressing", "Scheduler has run at least one tick.", _t_scheduler_progressing),
    Tripwire("huklla-6", "wiring_acyclic_ex_ouroboros", "Only the declared ouroboros edge cycles.", _t_wiring_acyclic_ex_ouroboros),
    Tripwire("huklla-7", "bus_publish_succeeded", "Yawar-bus publish round-trips succeed.", _t_bus_publish_succeeded),
    Tripwire("huklla-8", "leader_doctrine_loaded", "Every chakra ships LEADER.md.", _t_leader_doctrine_loaded),
    Tripwire("huklla-9", "inputs_bounded", "Envelopes stay under the soft size cap.", _t_inputs_bounded),
    Tripwire("huklla-10", "canonical_order", "Declared chakra order matches the canonical root→crown sequence.", _t_canonical_order),
)


def evaluate_all(snapshot: dict[str, Any]) -> list[TripwireResult]:
    return [t.predicate(snapshot) for t in TRIPWIRES]
