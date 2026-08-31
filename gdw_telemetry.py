"""In-process GDW counters and Prometheus text export."""

import math
import threading
from collections import Counter, deque
from typing import Any, Dict, Iterable, List


class GDWTelemetry:
    def __init__(self):
        self._lock = threading.Lock()
        self._requests = 0
        self._errors = 0
        self._receipts = 0
        self._decisions = Counter()
        self._routes = Counter()
        self._latencies_ms = deque(maxlen=10000)

    def observe(
        self,
        latency_ms: float,
        decision: str,
        route: str,
        receipt_emitted: bool,
        error: bool = False,
    ) -> None:
        with self._lock:
            self._requests += 1
            self._errors += int(error)
            self._receipts += int(receipt_emitted)
            self._decisions[decision] += 1
            self._routes[route] += 1
            self._latencies_ms.append(float(latency_ms))

    @staticmethod
    def _percentile(values: Iterable[float], quantile: float) -> float:
        ordered = sorted(values)
        if not ordered:
            return 0.0
        position = (len(ordered) - 1) * quantile
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            latencies: List[float] = list(self._latencies_ms)
            return {
                "requests": self._requests,
                "errors": self._errors,
                "receipts": self._receipts,
                "decisions": dict(self._decisions),
                "routes": dict(self._routes),
                "p50_ms": round(self._percentile(latencies, 0.50), 6),
                "p95_ms": round(self._percentile(latencies, 0.95), 6),
                "p99_ms": round(self._percentile(latencies, 0.99), 6),
            }

    def render(self) -> str:
        snapshot = self.snapshot()
        lines = [
            "# HELP gdw_requests_total Governed Delta Workspace requests.",
            "# TYPE gdw_requests_total counter",
            f"gdw_requests_total {snapshot['requests']}",
            "# HELP gdw_errors_total Governed Delta Workspace errors.",
            "# TYPE gdw_errors_total counter",
            f"gdw_errors_total {snapshot['errors']}",
            "# HELP gdw_receipts_total Persisted transition receipts.",
            "# TYPE gdw_receipts_total counter",
            f"gdw_receipts_total {snapshot['receipts']}",
        ]
        for decision, value in sorted(snapshot["decisions"].items()):
            lines.append(f'gdw_decisions_total{{decision="{decision}"}} {value}')
        for route, value in sorted(snapshot["routes"].items()):
            lines.append(f'gdw_routes_total{{route="{route}"}} {value}')
        for quantile in ("p50", "p95", "p99"):
            lines.append(
                f'gdw_latency_milliseconds{{quantile="{quantile}"}} '
                f"{snapshot[quantile + '_ms']}"
            )
        return "\n".join(lines) + "\n"
