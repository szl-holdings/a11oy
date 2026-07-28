#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

"""Immutable contracts for the MODELED Governed Delta Workspace."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping


class CapabilityLabel(str, Enum):
    MODELED = "MODELED"
    EXPERIMENTAL = "EXPERIMENTAL"
    VERIFIED = "VERIFIED"


class Decision(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    QUARANTINE = "QUARANTINE"


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    uri: str
    content_hash: str
    trust: float
    observed_at: str


@dataclass(frozen=True)
class DepthSummary:
    summary_id: str
    depth: int
    vector: tuple[float, ...]
    trust: float
    risk: float
    provenance: tuple[str, ...]


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    parent_state_hash: str
    operation: str
    payload: Mapping[str, Any]
    evidence_ids: tuple[str, ...]
    proposer: str
    created_at: str
    capability_label: CapabilityLabel = CapabilityLabel.MODELED

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _freeze(self.payload))


@dataclass(frozen=True)
class KernelReceipt:
    receipt_id: str
    proposal_id: str
    decision: Decision
    policy_results: Mapping[str, bool]
    invariant_results: Mapping[str, bool]
    state_before: str
    state_after: str | None
    reason: str
    created_at: str
    receipt_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "policy_results", _freeze(self.policy_results)
        )
        object.__setattr__(
            self, "invariant_results", _freeze(self.invariant_results)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "proposal_id": self.proposal_id,
            "decision": self.decision.value,
            "policy_results": _plain(self.policy_results),
            "invariant_results": _plain(self.invariant_results),
            "state_before": self.state_before,
            "state_after": self.state_after,
            "reason": self.reason,
            "created_at": self.created_at,
            "receipt_hash": self.receipt_hash,
        }


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, DepthSummary):
        return {
            "summary_id": value.summary_id,
            "depth": value.depth,
            "vector": list(value.vector),
            "trust": value.trust,
            "risk": value.risk,
            "provenance": list(value.provenance),
        }
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class WorkspaceState:
    """Copy-on-write state. No governed path mutates an instance in place."""

    session_id: str
    step: int
    yuyay: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    unay_refs: tuple[str, ...] = field(default_factory=tuple)
    broadcast: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    delta_memory: tuple[float, ...] = field(default_factory=tuple)
    depth_summaries: tuple[DepthSummary, ...] = field(default_factory=tuple)
    risk_budget: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "yuyay", _freeze(self.yuyay))
        object.__setattr__(self, "unay_refs", tuple(self.unay_refs))
        object.__setattr__(self, "broadcast", _freeze(self.broadcast))
        object.__setattr__(
            self,
            "delta_memory",
            tuple(float(value) for value in self.delta_memory),
        )
        object.__setattr__(
            self, "depth_summaries", tuple(self.depth_summaries)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "step": self.step,
            "yuyay": _plain(self.yuyay),
            "unay_refs": list(self.unay_refs),
            "broadcast": _plain(self.broadcast),
            "delta_memory": list(self.delta_memory),
            "depth_summaries": _plain(self.depth_summaries),
            "risk_budget": self.risk_budget,
        }

    def canonical_hash(self) -> str:
        body = json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(body.encode("utf-8")).hexdigest()
