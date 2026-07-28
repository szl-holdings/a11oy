#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

"""Process-local operational observations for the MODELED GDW surface."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Mapping


_DECISIONS = frozenset({"ACCEPT", "REJECT", "QUARANTINE", "UNAVAILABLE"})
_ERROR_KINDS = frozenset(
    {
        "conflict",
        "integrity",
        "not_found",
        "persistence",
        "unavailable",
        "validation",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperationalTelemetry:
    """Bounded counters only; no hardware, energy, or performance claims."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._started_at = _utc_now()
        self._counters: Counter[str] = Counter()
        self._decisions: Counter[str] = Counter()
        self._errors: Counter[str] = Counter()

    def record_session_created(self) -> None:
        with self._lock:
            self._counters["sessions_created"] += 1

    def record_step(self, decision: str, *, replayed: bool) -> None:
        normalized = str(decision).upper()
        if normalized not in _DECISIONS:
            normalized = "UNAVAILABLE"
        with self._lock:
            self._counters["step_requests"] += 1
            if replayed:
                self._counters["step_replays"] += 1
            else:
                self._counters["step_commits"] += 1
            self._decisions[normalized] += 1

    def record_aggregate(self, *, available: bool) -> None:
        with self._lock:
            self._counters["aggregate_requests"] += 1
            if not available:
                self._counters["aggregate_unavailable"] += 1

    def record_error(self, kind: str) -> None:
        normalized = str(kind).lower()
        if normalized not in _ERROR_KINDS:
            normalized = "unavailable"
        with self._lock:
            self._counters["errors"] += 1
            self._errors[normalized] += 1

    def snapshot(
        self, storage: Mapping[str, Any] | None = None
    ) -> Mapping[str, Any]:
        """Return a copy without incrementing counters or touching storage."""

        with self._lock:
            counters = dict(sorted(self._counters.items()))
            decisions = dict(sorted(self._decisions.items()))
            errors = dict(sorted(self._errors.items()))
            started_at = self._started_at
        return {
            "schema": "szl.gdw.telemetry/v1",
            "label": "MODELED",
            "status": "MODELED",
            "basis": "process-local operational counters",
            "started_at": started_at,
            "counters": counters,
            "decisions": decisions,
            "errors": errors,
            "storage": dict(storage) if storage is not None else None,
            "hardware_observation": "UNAVAILABLE",
            "energy_observation": "UNAVAILABLE",
            "performance_claim": "UNAVAILABLE",
        }


def snapshot(
    telemetry: OperationalTelemetry,
    storage: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Small functional adapter for callers that do not retain class details."""

    return telemetry.snapshot(storage)
