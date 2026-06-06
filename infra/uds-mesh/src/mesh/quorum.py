"""Byzantine mesh-health quorum (F1) + FLP/CAP partition guard (F2) for uds-mesh.

Operationalizes the published Byzantine fault-tolerance result: a mesh of ``n``
organs tolerating ``f`` Byzantine faults is healthy iff ``n >= 3f + 1`` AND a
quorum of ``>= 2f + 1`` organs are observed live AND no network partition is
detected. On a healthy decision we stamp a DSSE receipt reusing the SAME PAE
scheme as ``pinn_dsse.py`` (ECDSA-P256 cosign), so a quorum receipt verifies with
the exact same ``cosign verify-blob`` command as every other mesh receipt.

ADR: this file lands in the CANONICAL home ``szl-holdings/uds-mesh`` per
ADR-0001 (Canonical Home for the UDS Mesh, ACCEPTED 2026-06-03).

HONESTY OVER CHECKLIST
----------------------
- The quorum *math* and the *partition guard* are REAL and unit-tested.
- Live cluster polling is OUT OF SCOPE: heartbeats are injected by the caller
  (tests inject lists). No cluster connection is opened by this module.
- If ``SZL_COSIGN_PRIVATE_PEM`` is absent the receipt is an explicit UNSIGNED
  envelope (via ``pinn_dsse.sign_payload``) — no signature is ever fabricated.
- Under partition we choose **CP**: we refuse to claim consensus (sacrifice
  availability) rather than assert liveness we cannot guarantee (FLP). See
  ``docs/FLP_CAP_CAVEAT.md``.

Doctrine v11 — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (never a theorem).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable

try:  # canonical home ships pinn_dsse.py at repo root
    import pinn_dsse  # type: ignore
except Exception:  # pragma: no cover - import-path fallback for src layout
    pinn_dsse = None  # type: ignore

QUORUM_PAYLOAD_TYPE = "application/vnd.szl.mesh-quorum-receipt+json"


def max_byzantine_faults(n: int) -> int:
    """Largest ``f`` such that ``n >= 3f + 1`` holds.

    >>> [max_byzantine_faults(n) for n in (1, 3, 4, 5, 6, 7, 10)]
    [0, 0, 1, 1, 1, 2, 3]
    """
    if n < 1:
        return 0
    return (n - 1) // 3


def quorum_size(f: int) -> int:
    """Read/agreement quorum needed to outvote ``f`` Byzantine organs (2f + 1).

    >>> [quorum_size(f) for f in (0, 1, 2, 3)]
    [1, 3, 5, 7]
    """
    return 2 * f + 1


@dataclass
class QuorumVerdict:
    healthy: bool
    n: int
    f: int
    live: int
    required: int          # quorum threshold (2f+1)
    partition: bool
    reason: str
    receipt: dict[str, Any] | None = field(default=None)

    def as_dict(self) -> dict[str, Any]:
        d = {
            "healthy": self.healthy,
            "n": self.n,
            "f": self.f,
            "live": self.live,
            "required": self.required,
            "partition": self.partition,
            "reason": self.reason,
        }
        if self.receipt is not None:
            d["receipt"] = self.receipt
        return d


class MeshQuorum:
    """Byzantine mesh-health attestor.

    Parameters
    ----------
    n:
        total number of organs in the mesh membership.
    f:
        Byzantine faults to tolerate. If ``None``, the maximum supported by
        ``n`` (``floor((n-1)/3)``) is used. A configuration with ``n < 3f+1`` is
        rejected as structurally unable to provide BFT.
    """

    def __init__(self, n: int, f: int | None = None) -> None:
        if n < 1:
            raise ValueError("n must be >= 1")
        self.n = n
        self.f = max_byzantine_faults(n) if f is None else f
        if self.f < 0:
            raise ValueError("f must be >= 0")
        # structural BFT feasibility: n >= 3f + 1
        self.bft_feasible = self.n >= 3 * self.f + 1
        self.required = quorum_size(self.f)

    # ---- core decision -------------------------------------------------
    def _count_live(self, heartbeats: Iterable[dict[str, Any]]) -> int:
        return sum(1 for h in heartbeats if h.get("alive") is True)

    def partition_guard(
        self,
        view_a: Iterable[str] | None,
        view_b: Iterable[str] | None,
    ) -> bool:
        """Return True if a partition is detected (membership views disagree).

        Two organs that should see the same membership but report different
        member sets indicate a split view. Under a split we will NOT claim
        consensus (CP choice). ``None`` for either view means "not supplied" →
        no partition asserted (we never invent a partition we cannot observe).

        >>> q = MeshQuorum(7)
        >>> q.partition_guard({"a", "b", "c"}, {"a", "b", "c"})
        False
        >>> q.partition_guard({"a", "b", "c"}, {"a", "b"})
        True
        >>> q.partition_guard(None, {"a"})
        False
        """
        if view_a is None or view_b is None:
            return False
        return set(view_a) != set(view_b)

    def healthy(
        self,
        heartbeats: Iterable[dict[str, Any]],
        view_a: Iterable[str] | None = None,
        view_b: Iterable[str] | None = None,
        sign: bool = True,
    ) -> QuorumVerdict:
        """Decide mesh health from organ heartbeats.

        Healthy iff: BFT-feasible (n >= 3f+1) AND no partition AND
        live >= 2f+1.
        """
        heartbeats = list(heartbeats)
        live = self._count_live(heartbeats)
        partition = self.partition_guard(view_a, view_b)

        if not self.bft_feasible:
            healthy, reason = False, f"not BFT-feasible: n={self.n} < 3f+1={3*self.f+1}"
        elif partition:
            healthy, reason = False, "partition detected — refusing consensus (CP / FLP caveat)"
        elif live >= self.required:
            healthy, reason = True, f"quorum met: live={live} >= required={self.required}"
        else:
            healthy, reason = False, f"quorum NOT met: live={live} < required={self.required}"

        verdict = QuorumVerdict(
            healthy=healthy,
            n=self.n,
            f=self.f,
            live=live,
            required=self.required,
            partition=partition,
            reason=reason,
        )
        if sign:
            verdict.receipt = self.decision_receipt(verdict)
        return verdict

    # ---- DSSE receipt (reuses pinn_dsse PAE) ---------------------------
    def decision_receipt(self, verdict: QuorumVerdict) -> dict[str, Any]:
        """Produce a DSSE receipt over the quorum decision.

        Reuses ``pinn_dsse.sign_payload`` so the receipt verifies with the same
        cosign key/command as every other mesh receipt. When the cosign key is
        absent (or ``pinn_dsse`` is unavailable) an explicit UNSIGNED marker is
        returned — never a fabricated signature.
        """
        payload = {
            "kind": "mesh-quorum-decision",
            "n": verdict.n,
            "f": verdict.f,
            "live": verdict.live,
            "required": verdict.required,
            "partition": verdict.partition,
            "healthy": verdict.healthy,
            "reason": verdict.reason,
            "ts": time.time(),
        }
        if pinn_dsse is None:
            return {
                "payloadType": QUORUM_PAYLOAD_TYPE,
                "signed": False,
                "honesty": "UNSIGNED — pinn_dsse module unavailable in this runtime; "
                "no signature fabricated.",
                "_payload": payload,
            }
        env = pinn_dsse.sign_payload(payload, payload_type=QUORUM_PAYLOAD_TYPE)
        return env


if __name__ == "__main__":  # pragma: no cover
    import doctest

    fails, _ = doctest.testmod(verbose=False)
    if fails == 0:
        print("\u2713 quorum doctests passed (Byzantine n>=3f+1 + FLP/CAP partition guard)")
