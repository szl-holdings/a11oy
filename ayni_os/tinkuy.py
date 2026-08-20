"""Tinkuy — flow-state synchronization operator (Kuramoto order parameter).

Quechua *tinkuy* = "meeting / convergence". Used here STRICTLY as a label for a
game-theoretic / dynamical synchronization manifold across organs. No mysticism.

Math: each organ runs a control loop with an instantaneous phase theta_o(t). The
empire's global synchrony is the Kuramoto (1975) order parameter

        r * e^{i psi} = (1/N) * sum_o e^{i theta_o}

r in [0,1]: r->0 incoherent, r->1 fully phase-locked. When r > 0.85 the system is in
TINKUY (a coherent flow window). During flow we suppress Reflexion ticks (cf.
Csikszentmihalyi 1975 flow: minimize interruption during deep coherence) and log +
publish the event.

Citations: Kuramoto 1975 (coupled oscillators); Csikszentmihalyi 1975 (flow);
Strogatz, "Sync" (2003). Open-source: stdlib `cmath` only.
"""
from __future__ import annotations

import cmath
import math
import time as _time
from dataclasses import dataclass
from typing import Iterable, Optional

from .ledger import ORGANS

TINKUY_R_THRESHOLD = 0.85


@dataclass
class TinkuyState:
    r: float                 # Kuramoto order parameter magnitude in [0,1]
    psi: float               # mean phase (radians)
    in_tinkuy: bool          # r > threshold
    threshold: float
    n_organs: int
    suppress_reflexion: bool  # True during flow window
    ts: float


def order_parameter(phases: Iterable[float]) -> tuple[float, float]:
    """Return (r, psi) for the Kuramoto order parameter over organ phases."""
    phases = list(phases)
    n = len(phases)
    if n == 0:
        return 0.0, 0.0
    z = sum(cmath.exp(1j * theta) for theta in phases) / n
    return abs(z), cmath.phase(z)


def compute(phases: Iterable[float], threshold: float = TINKUY_R_THRESHOLD,
            now: Optional[float] = None) -> TinkuyState:
    r, psi = order_parameter(phases)
    in_tinkuy = r > threshold
    return TinkuyState(
        r=round(r, 6), psi=round(psi, 6), in_tinkuy=in_tinkuy,
        threshold=threshold, n_organs=len(list(phases)) if not isinstance(phases, list) else len(phases),
        suppress_reflexion=in_tinkuy,
        ts=now if now is not None else _time.time(),
    )


class TinkuyMonitor:
    """Tracks organ-loop phases and exposes the current Kuramoto r.

    suppress_reflexion(): during a flow window (r>threshold), Reflexion ticks are
    suppressed so the coherent state is not interrupted; events are logged/published.
    """

    def __init__(self, threshold: float = TINKUY_R_THRESHOLD) -> None:
        self.threshold = threshold
        self._phases: dict[str, float] = {o: 0.0 for o in ORGANS}
        self._log: list[TinkuyState] = []

    def set_phase(self, organ: str, theta: float) -> None:
        if organ not in self._phases:
            raise ValueError(f"unknown organ {organ!r}")
        # normalize to [0, 2pi)
        self._phases[organ] = theta % (2 * math.pi)

    def update_phases(self, mapping: dict) -> None:
        for o, th in mapping.items():
            self.set_phase(o, th)

    def state(self, now: Optional[float] = None) -> TinkuyState:
        st = compute(list(self._phases.values()), self.threshold, now=now)
        st = TinkuyState(**{**st.__dict__, "n_organs": len(self._phases)})
        if st.in_tinkuy:
            self._log.append(st)          # log + publish on flow
        return st

    def should_suppress_reflexion(self) -> bool:
        return self.state().in_tinkuy

    def flow_log(self) -> list[TinkuyState]:
        return list(self._log)
