"""Process-local counters for the MODELED research organ."""

from __future__ import annotations

import threading

from .models import Decision, KernelReceipt


class ModeledTelemetry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters = {
            "accepted": 0,
            "rejected": 0,
            "quarantined": 0,
            "dry_runs": 0,
        }

    def record(
        self, receipt: KernelReceipt | None = None, *, dry_run: bool = False
    ) -> None:
        with self._lock:
            if dry_run:
                self._counters["dry_runs"] += 1
            elif receipt is not None:
                key = {
                    Decision.ACCEPT: "accepted",
                    Decision.REJECT: "rejected",
                    Decision.QUARANTINE: "quarantined",
                }[receipt.decision]
                self._counters[key] += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counters = dict(self._counters)
        return {
            "capability_label": "MODELED",
            "scope": "PROCESS_LOCAL",
            "performance_claim": "UNAVAILABLE",
            "counters": counters,
        }
