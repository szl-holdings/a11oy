"""
overwatch — R0513 read-only sensor (the "eyes" of the Andean anatomy).

Doctrine reference: szl-holdings/ouroboros-thesis ·
  docs/anatomy/hatun-sources.md ("R0513 overwatch panel — 6 innovations")
  docs/anatomy/explainers/linkedin/linkedin_brain.md
    ("OVERWATCH — r0513, df4e9741. 146 SLOC. Read-only. Five invariants.
     Watches every cycle. Halt authority belongs to HUKLLA.")

R0513 watches. It does not write. Halt authority belongs to HUKLLA.
This module never mutates the receipt chain, never publishes to the bus,
never touches kernel state. It only computes invariants over read-only
snapshots and returns a structured panel.

The 6 panel innovations (I1..I6) per thesis:
  I1  KL drift watcher (per axis)
  I2  Joint-margin envelope
  I3  TUKUY mid-exec re-gate signal
  I4  reserved (intentionally — preserves the panel slot)
  I5  Maxwell M=0 rigidity check (21-edge CHAKANA)
  I6  continuum_hash chain integrity

Kernel hash anchor (from hatun-sources.md): 01f6c9b6 (also df4e9741 in
the LinkedIn brain explainer — both are upstream thesis hashes, not of
this module's source).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence


THESIS_KERNEL_HASH = "01f6c9b6"
THESIS_BRAIN_HASH = "df4e9741"
PANEL_VERSION = "r0513.v1"

# CHAKANA Maxwell rigidity: 7 vertices, 3D embedding ⇒ rigid graph requires
# 3·7 − 6 = 15 edges minimum; the doctrine value is 21 (over-constrained by
# 6, which is the Maxwell-rigid signature we check for).
CHAKANA_VERTICES = 7
CHAKANA_EDGES_REQUIRED = 21


@dataclass(frozen=True)
class InvariantResult:
    id: str
    title: str
    status: str  # "pass" | "warn" | "trip" | "reserved"
    value: float | int | None
    threshold: float | int | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "value": self.value,
            "threshold": self.threshold,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class OverwatchSnapshot:
    panel_version: str
    thesis_kernel_hash: str
    thesis_brain_hash: str
    read_only: bool
    invariants: tuple[InvariantResult, ...]
    summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "panel_version": self.panel_version,
            "thesis_kernel_hash": self.thesis_kernel_hash,
            "thesis_brain_hash": self.thesis_brain_hash,
            "read_only": self.read_only,
            "invariants": [i.to_dict() for i in self.invariants],
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# I1 — KL drift watcher (per axis)
# ---------------------------------------------------------------------------

def _normalize(p: Sequence[float]) -> list[float]:
    total = sum(max(0.0, x) for x in p)
    if total <= 0:
        return [1.0 / len(p)] * len(p) if p else []
    return [max(0.0, x) / total for x in p]


def kl_divergence(p: Sequence[float], q: Sequence[float]) -> float:
    """Symmetric-floor KL(p || q). Both inputs are non-negative; zeros in q
    are clamped to a small floor so the value stays finite. The intent is a
    drift indicator, not a measure-theoretic divergence."""
    if not p or not q or len(p) != len(q):
        return float("inf")
    pn = _normalize(p)
    qn = _normalize(q)
    floor = 1e-12
    total = 0.0
    for pi, qi in zip(pn, qn):
        if pi <= 0:
            continue
        total += pi * math.log(pi / max(qi, floor))
    return total


def invariant_i1_kl_drift(
    *,
    baseline: Sequence[float] | None,
    observed: Sequence[float] | None,
    threshold: float = 0.10,
) -> InvariantResult:
    if not baseline or not observed:
        return InvariantResult(
            "I1", "kl_drift_per_axis", "pass",
            value=0.0, threshold=threshold,
            detail="no axis distributions provided — vacuously pass",
        )
    kl = kl_divergence(observed, baseline)
    if not math.isfinite(kl):
        return InvariantResult(
            "I1", "kl_drift_per_axis", "trip",
            value=None, threshold=threshold,
            detail="non-finite KL — shape mismatch or empty axis",
        )
    status = "pass" if kl <= threshold else "warn" if kl <= threshold * 3 else "trip"
    return InvariantResult(
        "I1", "kl_drift_per_axis", status,
        value=round(kl, 6), threshold=threshold,
        detail=f"KL={kl:.6f} vs threshold={threshold}",
    )


# ---------------------------------------------------------------------------
# I2 — Joint-margin envelope
# ---------------------------------------------------------------------------

def invariant_i2_joint_margin(
    margins: Mapping[str, float] | None,
    *,
    min_margin: float = 0.05,
) -> InvariantResult:
    if not margins:
        return InvariantResult(
            "I2", "joint_margin_envelope", "pass",
            value=None, threshold=min_margin,
            detail="no margins reported — vacuously pass",
        )
    lo = min(margins.values())
    name = min(margins, key=lambda k: margins[k])
    status = "pass" if lo >= min_margin else "warn" if lo >= 0 else "trip"
    return InvariantResult(
        "I2", "joint_margin_envelope", status,
        value=round(lo, 6), threshold=min_margin,
        detail=f"min margin {lo:.6f} on '{name}' (envelope of {len(margins)} axes)",
    )


# ---------------------------------------------------------------------------
# I3 — TUKUY mid-exec re-gate signal
# ---------------------------------------------------------------------------

def invariant_i3_tukuy_regate(
    *,
    in_flight: int,
    regated: int,
    max_regate_ratio: float = 0.25,
) -> InvariantResult:
    if in_flight <= 0:
        return InvariantResult(
            "I3", "tukuy_mid_exec_regate", "pass",
            value=0.0, threshold=max_regate_ratio,
            detail="no in-flight evaluations — vacuously pass",
        )
    ratio = regated / in_flight
    status = "pass" if ratio <= max_regate_ratio else "warn" if ratio <= max_regate_ratio * 2 else "trip"
    return InvariantResult(
        "I3", "tukuy_mid_exec_regate", status,
        value=round(ratio, 6), threshold=max_regate_ratio,
        detail=f"{regated}/{in_flight} mid-exec re-gates",
    )


# ---------------------------------------------------------------------------
# I4 — reserved
# ---------------------------------------------------------------------------

def invariant_i4_reserved() -> InvariantResult:
    return InvariantResult(
        "I4", "reserved", "reserved",
        value=None, threshold=None,
        detail="panel slot reserved by doctrine (hatun-sources.md §5)",
    )


# ---------------------------------------------------------------------------
# I5 — Maxwell M=0 rigidity (21-edge CHAKANA)
# ---------------------------------------------------------------------------

def invariant_i5_maxwell_rigidity(
    *,
    vertices: int,
    edges: int,
) -> InvariantResult:
    """Maxwell counting: an over-constrained rigid 3D graph at the doctrinal
    setting has exactly 21 edges across 7 vertices. We report the deviation
    from that signature. M here is "edge deficit vs required"."""
    deficit = CHAKANA_EDGES_REQUIRED - edges
    if vertices == CHAKANA_VERTICES and edges == CHAKANA_EDGES_REQUIRED:
        status = "pass"
        detail = "21/21 edges, 7/7 vertices — Maxwell rigid"
    elif vertices != CHAKANA_VERTICES:
        status = "trip"
        detail = f"vertex count {vertices} ≠ doctrinal {CHAKANA_VERTICES}"
    elif deficit > 0:
        status = "trip"
        detail = f"edge deficit {deficit} — graph under-constrained"
    else:
        status = "warn"
        detail = f"edge surplus {-deficit} — over-rigid"
    return InvariantResult(
        "I5", "maxwell_m_zero_rigidity", status,
        value=deficit, threshold=0,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# I6 — continuum_hash chain integrity
# ---------------------------------------------------------------------------

def invariant_i6_chain_integrity(
    receipts: Iterable[Mapping[str, Any]],
) -> InvariantResult:
    """Walk the receipt chain. Every receipt's prev_hash must equal the
    previous receipt's self_hash; the first receipt must reference the
    genesis prev_hash (64 zeros)."""
    genesis = "0" * 64
    last_self: str | None = None
    breaks: list[int] = []
    count = 0
    for r in receipts:
        count += 1
        prev = r.get("prev_hash") or r.get("prevHash")
        self_h = r.get("self_hash") or r.get("selfHash")
        expected = genesis if last_self is None else last_self
        if prev != expected:
            breaks.append(int(r.get("seq", count)))
        last_self = self_h
    if count == 0:
        return InvariantResult(
            "I6", "continuum_hash_chain_integrity", "pass",
            value=0, threshold=0,
            detail="empty chain — vacuously pass",
        )
    if breaks:
        return InvariantResult(
            "I6", "continuum_hash_chain_integrity", "trip",
            value=len(breaks), threshold=0,
            detail=f"{len(breaks)} broken links at seqs {breaks[:10]}",
        )
    return InvariantResult(
        "I6", "continuum_hash_chain_integrity", "pass",
        value=0, threshold=0,
        detail=f"{count} receipts, chain intact",
    )


# ---------------------------------------------------------------------------
# Top-level snapshot
# ---------------------------------------------------------------------------

def evaluate_panel(
    *,
    receipts: Iterable[Mapping[str, Any]] = (),
    wiring: Mapping[str, Any] | None = None,
    baseline_axes: Sequence[float] | None = None,
    observed_axes: Sequence[float] | None = None,
    margins: Mapping[str, float] | None = None,
    in_flight: int = 0,
    regated: int = 0,
) -> OverwatchSnapshot:
    """Compute the R0513 6-innovation panel against the supplied read-only
    inputs. This function never mutates its inputs and never performs I/O."""
    edges = 0
    vertices = 0
    if wiring is not None:
        edges = len(wiring.get("edges", []))
        vertices = len(wiring.get("chakras", []))

    invariants = (
        invariant_i1_kl_drift(baseline=baseline_axes, observed=observed_axes),
        invariant_i2_joint_margin(margins),
        invariant_i3_tukuy_regate(in_flight=in_flight, regated=regated),
        invariant_i4_reserved(),
        invariant_i5_maxwell_rigidity(vertices=vertices, edges=edges),
        invariant_i6_chain_integrity(receipts),
    )

    summary: dict[str, int] = {"pass": 0, "warn": 0, "trip": 0, "reserved": 0}
    for inv in invariants:
        summary[inv.status] = summary.get(inv.status, 0) + 1

    return OverwatchSnapshot(
        panel_version=PANEL_VERSION,
        thesis_kernel_hash=THESIS_KERNEL_HASH,
        thesis_brain_hash=THESIS_BRAIN_HASH,
        read_only=True,
        invariants=invariants,
        summary=summary,
    )
