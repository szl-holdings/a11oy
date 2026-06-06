"""rosie.console.spans — Span Explorer fixture data + filtering.

The Span Explorer browses OpenTelemetry-shaped spans across the receipt DAG.
When no live OTLP exporter / `spans_sample.jsonl` is wired in, the console
serves a deterministic synthetic fixture so the surface is never empty. The
data is explicitly labelled synthetic by :func:`provenance`.

Determinism: each span is derived from a SHA-256 pseudo-random seed, so the
fixture is byte-identical across processes and platforms — a property the
tests assert directly.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

# The 5 ecosystem components rosie observes (vessels included so the mesh
# count is 5, matching the documented ecosystem, not 4).
COMPONENTS: tuple[str, ...] = ("amaru", "rosie", "sentra", "a11oy", "vessels")

_OPERATIONS = ("inference", "attest", "gate_check", "receipt_mint")

# Error threshold on the pseudo-random draw; matches the live Space.
_ERROR_THRESHOLD = 0.12

DEFAULT_SPAN_COUNT = 50


@dataclass(frozen=True)
class Span:
    """One OpenTelemetry-shaped span over the receipt DAG."""

    span_id: str
    component: str
    operation: str
    status: str
    duration_ms: float
    timestamp_utc: str
    receipt_hash: str
    actor: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pseudo_rand(seed: int) -> float:
    """Deterministic pseudo-random float in [0, 1) from a SHA-256 seed."""
    h = hashlib.sha256(str(seed).encode()).digest()
    return int.from_bytes(h[:4], "big") / 0xFFFFFFFF


def generate_spans(count: int = DEFAULT_SPAN_COUNT) -> list[Span]:
    """Generate ``count`` deterministic synthetic spans across the components.

    Args:
        count: Number of spans to generate (>= 0).

    Returns:
        A list of :class:`Span`, deterministic for a given ``count``.

    Raises:
        ValueError: If ``count`` is negative.
    """
    if count < 0:
        raise ValueError(f"count must be >= 0, got {count}")
    ncomp = len(COMPONENTS)
    spans: list[Span] = []
    for i in range(count):
        comp = COMPONENTS[i % ncomp]
        r = _pseudo_rand(i * 997 + 1337)
        spans.append(
            Span(
                span_id=f"span-{i:04d}",
                component=comp,
                operation=_OPERATIONS[i % len(_OPERATIONS)],
                status="error" if r < _ERROR_THRESHOLD else "ok",
                duration_ms=round(5 + r * 200, 2),
                timestamp_utc=(
                    f"2026-06-{(i % 28) + 1:02d}T{(i * 7) % 24:02d}:{(i * 13) % 60:02d}:00Z"
                ),
                receipt_hash=hashlib.sha256(f"span-{i}".encode()).hexdigest()[:16],
                actor=f"agent/{comp}-v1",
            )
        )
    return spans


def filter_spans(
    spans: list[Span],
    *,
    component: str = "all",
    status: str = "all",
    limit: int | None = None,
) -> list[Span]:
    """Filter spans by component and/or status, then cap to ``limit``.

    Args:
        spans:     Spans to filter.
        component: Component name, or "all" for no component filter.
        status:    "ok" / "error", or "all" for no status filter.
        limit:     Max rows to return (None = no cap).

    Returns:
        Filtered list of spans.

    Raises:
        ValueError: If ``limit`` is negative.
    """
    if limit is not None and limit < 0:
        raise ValueError(f"limit must be >= 0 or None, got {limit}")
    out = spans
    if component != "all":
        out = [s for s in out if s.component == component]
    if status != "all":
        out = [s for s in out if s.status == status]
    if limit is not None:
        out = out[:limit]
    return out


def provenance() -> dict[str, Any]:
    """Return an explicit provenance descriptor for the span fixture.

    The console surface must disclose that this is synthetic fixture data, not
    a live OTLP feed. This descriptor is the single source of that disclosure.
    """
    return {
        "source": "synthetic-fixture",
        "live": False,
        "note": (
            "Deterministic synthetic spans (no live OTLP exporter wired). "
            "Set ROSIE_SPANS_PATH to a JSONL file to serve real spans."
        ),
        "components": list(COMPONENTS),
    }
