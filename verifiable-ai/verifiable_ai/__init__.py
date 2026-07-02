"""SZL Verifiable-AI: provenance-native honesty primitives.

The smallest reusable core of SZL's "verifiable AI" bet: every claim an agent or
benchmark makes carries a doctrine label and its evidence, and a gate refuses
artifacts that overclaim.
"""
from .doctrine import (
    ABSTENTION,
    DOCTRINE_VERSION,
    EVIDENCE_REQUIRED,
    Claim,
    Label,
)
from .agent import ProvenanceResponse
from .gate import GateResult, honesty_gate

__all__ = [
    "Label",
    "Claim",
    "DOCTRINE_VERSION",
    "EVIDENCE_REQUIRED",
    "ABSTENTION",
    "honesty_gate",
    "GateResult",
    "ProvenanceResponse",
]
