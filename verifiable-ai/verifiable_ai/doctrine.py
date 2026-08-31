"""SZL Verifiable-AI — the honesty doctrine as a reusable primitive.

Doctrine v11: no fabricated numbers. Every claim carries exactly one label:
MEASURED / MODELED / NOT-RUN / NOT-MEASURED / NOT-TESTED.

  - MEASURED / MODELED claims MUST carry a value AND evidence.
  - NOT-RUN / NOT-MEASURED / NOT-TESTED claims MUST NOT carry a value
    (a number on an abstention is fabrication).

This module makes that rule executable so agents and benchmarks cannot silently
overclaim. It is the smallest shared unit of "verifiable AI".
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

DOCTRINE_VERSION = "v11"


class Label(str, Enum):
    MEASURED = "MEASURED"
    MODELED = "MODELED"
    NOT_RUN = "NOT-RUN"
    NOT_MEASURED = "NOT-MEASURED"
    NOT_TESTED = "NOT-TESTED"

    @classmethod
    def parse(cls, raw: Any) -> "Label":
        """Parse a label that may carry a parenthetical caveat.

        e.g. 'MEASURED (fit error vs synthetic ground truth)' -> Label.MEASURED
        """
        base = str(raw).strip().split(" ")[0].upper()
        for lab in cls:
            if lab.value == base:
                return lab
        raise ValueError(f"unrecognized doctrine label: {raw!r}")


# Labels that assert a real result -> must carry evidence.
EVIDENCE_REQUIRED = {Label.MEASURED, Label.MODELED}
# Labels that assert the work was NOT done -> must NOT carry a value.
ABSTENTION = {Label.NOT_RUN, Label.NOT_MEASURED, Label.NOT_TESTED}


@dataclass
class Claim:
    """A single provenance-stamped assertion an agent or benchmark makes."""

    name: str
    label: Label
    value: Any = None
    evidence: Optional[dict] = None
    unit: Optional[str] = None

    def violations(self) -> list[str]:
        v: list[str] = []
        if not isinstance(self.label, Label):
            return [f"{self.name}: label is not a doctrine Label"]
        if self.label in EVIDENCE_REQUIRED:
            if self.value is None:
                v.append(f"{self.name}: {self.label.value} claim has no value")
            if not self.evidence:
                v.append(f"{self.name}: {self.label.value} claim carries no evidence (overclaim)")
        if self.label in ABSTENTION and self.value is not None:
            v.append(f"{self.name}: {self.label.value} claim carries a value (fabrication)")
        return v

    @property
    def ok(self) -> bool:
        return not self.violations()

    def to_provenance(self) -> dict:
        return {
            "name": self.name,
            "label": self.label.value,
            "value": self.value,
            "unit": self.unit,
            "evidence": self.evidence,
            "doctrine": DOCTRINE_VERSION,
        }
