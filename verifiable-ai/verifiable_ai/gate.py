"""Honesty gate for benchmark / result artifacts.

Scans a results artifact (e.g. a11oy's PINN results.json) and FAILS when it
overclaims:
  - an arm with no doctrine label, or an unrecognized one
  - a MEASURED/MODELED arm that carries no measured value
  - a NOT-RUN/NOT-TESTED/NOT-MEASURED arm that carries a number (fabrication)
  - an overall_label that claims a wider MEASURED sweep than the arms support

This is the same rule a CI step would run to block an overclaiming artifact from
shipping. It is deliberately schema-tolerant so it works across benchmarks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .doctrine import ABSTENTION, Label

# Substrings that mark a field as an actual measured/derived number.
_METRIC_HINTS = ("rel_l2", "abs_err", "_err", "alpha_estimate", "wall_s", "energy_j")
# Descriptive fields that are never treated as measured values.
_NON_METRIC = {"label", "framework", "method", "method_class", "license", "device"}


@dataclass
class GateResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    arms_checked: int = 0

    def __bool__(self) -> bool:
        return self.ok


def _numeric_leaf(x: Any) -> bool:
    if isinstance(x, bool):
        return False
    if isinstance(x, (int, float)):
        return True
    if isinstance(x, dict):
        return any(_numeric_leaf(v) for v in x.values())
    return False


def _arm_has_measured_value(arm: dict) -> bool:
    for k, val in arm.items():
        if k in _NON_METRIC:
            continue
        if any(h in k for h in _METRIC_HINTS) and _numeric_leaf(val):
            return True
    return False


def honesty_gate(artifact: dict) -> GateResult:
    v: list[str] = []
    checked = 0

    if "doctrine" not in str(artifact.get("doctrine", "")).lower():
        v.append("artifact declares no doctrine")
    if not str(artifact.get("honesty", "")).strip():
        v.append("artifact carries no honesty disclosure")

    for pb in artifact.get("problems", []):
        pid = pb.get("id", "<problem>")
        for arm in pb.get("arms", []):
            checked += 1
            tag = f"{pid}/{arm.get('framework', '<arm>')}"
            raw = arm.get("label")
            if raw is None:
                v.append(f"{tag}: arm has no label")
                continue
            try:
                label = Label.parse(raw)
            except ValueError as e:
                v.append(f"{tag}: {e}")
                continue
            has_num = _arm_has_measured_value(arm)
            if label in (Label.MEASURED, Label.MODELED) and not has_num:
                v.append(f"{tag}: {label.value} arm carries no measured value (overclaim)")
            if label in ABSTENTION and has_num:
                v.append(f"{tag}: {label.value} arm carries a measured value (fabrication)")

    # overall_label must not claim a wider MEASURED sweep than the ARM labels
    # support. Arm labels are the doctrine source of truth; frameworks[].status
    # is a role/shipping field and may be absent.
    overall = str(artifact.get("overall_label", ""))
    m = re.search(r"(\d+)-way", overall)
    if m and "MEASURED" in overall.upper():
        n = int(m.group(1))
        fw_arms: dict[str, list[bool]] = {}
        for pb in artifact.get("problems", []):
            for arm in pb.get("arms", []):
                try:
                    lab = Label.parse(arm.get("label"))
                except (ValueError, TypeError):
                    continue
                fw_arms.setdefault(arm.get("framework", "<arm>"), []).append(
                    lab in (Label.MEASURED, Label.MODELED)
                )
        measured = sum(1 for arms in fw_arms.values() if arms and all(arms))
        if measured < n:
            v.append(
                f"overall_label claims MEASURED {n}-way but only {measured}/{n} "
                "frameworks are fully MEASURED/MODELED across all problems (overclaim)"
            )

    return GateResult(ok=not v, violations=v, arms_checked=checked)
