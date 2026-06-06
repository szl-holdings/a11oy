"""rosie.console.mesh — mesh health aggregation (operator mesh query).

Aggregates per-component statistics over a set of spans: span count, error
count, error rate, average duration, and a green/yellow health flag. This is
the compute behind the operator console's Mesh Health tab and the mesh query
endpoint.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .spans import COMPONENTS, Span

# Below this per-component error rate (percent) a component is green.
GREEN_THRESHOLD_PCT = 15.0
# Above this overall error rate (percent) the mesh flags for alert review.
ALERT_THRESHOLD_PCT = 20.0


@dataclass(frozen=True)
class ComponentHealth:
    """Aggregated health for one mesh component."""

    component: str
    total_spans: int
    error_count: int
    error_rate_pct: float
    avg_duration_ms: float
    healthy: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MeshHealth:
    """Whole-mesh health rollup."""

    components: list[ComponentHealth]
    total_spans: int
    total_errors: int
    overall_error_rate_pct: float
    alert: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "components": [c.as_dict() for c in self.components],
            "total_spans": self.total_spans,
            "total_errors": self.total_errors,
            "overall_error_rate_pct": self.overall_error_rate_pct,
            "alert": self.alert,
        }


def component_health(component: str, spans: list[Span]) -> ComponentHealth:
    """Aggregate health for a single component from its spans.

    Args:
        component: Component name (reported back verbatim).
        spans:     Spans belonging to ``component``.

    Returns:
        :class:`ComponentHealth`. A component with zero spans is reported as
        healthy with a 0% error rate (no evidence of failure).
    """
    total = len(spans)
    errors = sum(1 for s in spans if s.status == "error")
    total_dur = sum(s.duration_ms for s in spans)
    error_rate = round(100 * errors / total, 1) if total else 0.0
    avg_dur = round(total_dur / total, 2) if total else 0.0
    return ComponentHealth(
        component=component,
        total_spans=total,
        error_count=errors,
        error_rate_pct=error_rate,
        avg_duration_ms=avg_dur,
        healthy=error_rate < GREEN_THRESHOLD_PCT,
    )


def mesh_health(spans: list[Span], components: tuple[str, ...] = COMPONENTS) -> MeshHealth:
    """Compute the whole-mesh health rollup over all components.

    Args:
        spans:      All spans to aggregate.
        components: The component names to report (defaults to the 5-component
                    ecosystem so every component appears even with no spans).

    Returns:
        :class:`MeshHealth`.
    """
    by_component = [
        component_health(comp, [s for s in spans if s.component == comp])
        for comp in components
    ]
    total_spans = len(spans)
    total_errors = sum(c.error_count for c in by_component)
    overall = round(100 * total_errors / total_spans, 1) if total_spans else 0.0
    return MeshHealth(
        components=by_component,
        total_spans=total_spans,
        total_errors=total_errors,
        overall_error_rate_pct=overall,
        alert=overall > ALERT_THRESHOLD_PCT,
    )
