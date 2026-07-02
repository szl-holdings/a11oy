"""Provenance-native agent responses.

Extends the honesty core from benchmarks to LIVE agents. An agent answer is a
piece of text plus the set of Claims that back it. The response refuses to
serialize if any claim overclaims — so an agent cannot silently assert a number
it cannot stand behind. This is the runtime half of "verifiable AI".
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .doctrine import Claim


@dataclass
class ProvenanceResponse:
    text: str
    claims: list[Claim] = field(default_factory=list)

    def violations(self) -> list[str]:
        out: list[str] = []
        for c in self.claims:
            out.extend(c.violations())
        return out

    @property
    def ok(self) -> bool:
        return not self.violations()

    def emit(self) -> dict:
        """Return the provenance-stamped payload, or refuse if it overclaims."""
        v = self.violations()
        if v:
            raise ValueError(
                "refusing to emit a response with unverifiable claims: " + "; ".join(v)
            )
        return {
            "text": self.text,
            "claims": [c.to_provenance() for c in self.claims],
            "verifiable": True,
        }
