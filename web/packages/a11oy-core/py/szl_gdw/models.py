"""Canonical, immutable data contracts for the MODELED GDW research organ."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from hashlib import sha256
from types import MappingProxyType
from typing import Any


class CapabilityLabel(str, Enum):
    MODELED = "MODELED"
    EXPERIMENTAL = "EXPERIMENTAL"
    VERIFIED = "VERIFIED"


class Decision(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    QUARANTINE = "QUARANTINE"


def freeze_value(value: Any) -> Any:
    """Recursively freeze JSON-like values so frozen dataclasses stay immutable."""
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): freeze_value(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(item) for item in value)
    return value


def to_primitive(value: Any) -> Any:
    """Convert contracts into a deterministic JSON-compatible representation."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            field.name: to_primitive(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): to_primitive(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [to_primitive(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        to_primitive(value),
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_identifier(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_unit_interval(value: float, field_name: str) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be finite and in [0, 1]")


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    uri: str
    content_hash: str
    trust: float
    observed_at: str

    def __post_init__(self) -> None:
        _require_identifier(self.evidence_id, "evidence_id")
        _require_identifier(self.uri, "uri")
        _require_identifier(self.content_hash, "content_hash")
        _require_identifier(self.observed_at, "observed_at")
        _require_unit_interval(self.trust, "trust")


@dataclass(frozen=True)
class DepthSummary:
    summary_id: str
    depth: int
    vector: tuple[float, ...]
    trust: float
    risk: float
    provenance: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_identifier(self.summary_id, "summary_id")
        if self.depth < 0:
            raise ValueError("depth must be non-negative")
        if not self.vector or not all(math.isfinite(value) for value in self.vector):
            raise ValueError("vector must contain finite values")
        _require_unit_interval(self.trust, "trust")
        if not math.isfinite(self.risk) or self.risk < 0.0:
            raise ValueError("risk must be finite and non-negative")
        object.__setattr__(self, "vector", tuple(float(value) for value in self.vector))
        object.__setattr__(
            self, "provenance", tuple(str(value) for value in self.provenance)
        )


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
        for name in (
            "proposal_id",
            "parent_state_hash",
            "operation",
            "proposer",
            "created_at",
        ):
            _require_identifier(getattr(self, name), name)
        object.__setattr__(self, "payload", freeze_value(self.payload))
        object.__setattr__(
            self, "evidence_ids", tuple(str(value) for value in self.evidence_ids)
        )


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
        for name in (
            "receipt_id",
            "proposal_id",
            "state_before",
            "reason",
            "created_at",
            "receipt_hash",
        ):
            _require_identifier(getattr(self, name), name)
        object.__setattr__(self, "policy_results", freeze_value(self.policy_results))
        object.__setattr__(
            self, "invariant_results", freeze_value(self.invariant_results)
        )


@dataclass(frozen=True)
class WorkspaceState:
    session_id: str
    step: int = 0
    yuyay: tuple[Mapping[str, Any], ...] = ()
    unay_refs: tuple[str, ...] = ()
    broadcast: tuple[Mapping[str, Any], ...] = ()
    delta_memory: tuple[float, ...] = ()
    depth_summaries: tuple[DepthSummary, ...] = ()
    risk_budget: float = 1.0

    def __post_init__(self) -> None:
        _require_identifier(self.session_id, "session_id")
        if self.step < 0:
            raise ValueError("step must be non-negative")
        _require_unit_interval(self.risk_budget, "risk_budget")
        if not all(math.isfinite(value) for value in self.delta_memory):
            raise ValueError("delta_memory must contain only finite values")
        object.__setattr__(
            self, "yuyay", tuple(freeze_value(item) for item in self.yuyay)
        )
        object.__setattr__(
            self, "unay_refs", tuple(str(value) for value in self.unay_refs)
        )
        object.__setattr__(
            self, "broadcast", tuple(freeze_value(item) for item in self.broadcast)
        )
        object.__setattr__(
            self, "delta_memory", tuple(float(value) for value in self.delta_memory)
        )
        object.__setattr__(self, "depth_summaries", tuple(self.depth_summaries))

    def canonical_hash(self) -> str:
        return canonical_hash(self)


def evidence_from_mapping(value: Mapping[str, Any]) -> Evidence:
    return Evidence(
        evidence_id=str(value["evidence_id"]),
        uri=str(value["uri"]),
        content_hash=str(value["content_hash"]),
        trust=float(value["trust"]),
        observed_at=str(value["observed_at"]),
    )


def depth_summary_from_mapping(value: Mapping[str, Any]) -> DepthSummary:
    return DepthSummary(
        summary_id=str(value["summary_id"]),
        depth=int(value["depth"]),
        vector=tuple(float(item) for item in value["vector"]),
        trust=float(value["trust"]),
        risk=float(value["risk"]),
        provenance=tuple(str(item) for item in value.get("provenance", ())),
    )


def workspace_state_from_mapping(value: Mapping[str, Any]) -> WorkspaceState:
    return WorkspaceState(
        session_id=str(value["session_id"]),
        step=int(value.get("step", 0)),
        yuyay=tuple(value.get("yuyay", ())),
        unay_refs=tuple(str(item) for item in value.get("unay_refs", ())),
        broadcast=tuple(value.get("broadcast", ())),
        delta_memory=tuple(float(item) for item in value.get("delta_memory", ())),
        depth_summaries=tuple(
            depth_summary_from_mapping(item)
            for item in value.get("depth_summaries", ())
        ),
        risk_budget=float(value.get("risk_budget", 1.0)),
    )


def proposal_from_mapping(value: Mapping[str, Any]) -> Proposal:
    return Proposal(
        proposal_id=str(value["proposal_id"]),
        parent_state_hash=str(value["parent_state_hash"]),
        operation=str(value["operation"]),
        payload=value["payload"],
        evidence_ids=tuple(str(item) for item in value.get("evidence_ids", ())),
        proposer=str(value["proposer"]),
        created_at=str(value["created_at"]),
        capability_label=CapabilityLabel(value.get("capability_label", "MODELED")),
    )


def proposal_identity_hash(proposal: Proposal) -> str:
    """Recompute the content-bound identity that a kernel must verify."""
    return canonical_hash(
        {
            "schema": "szl.gdw.proposal-identity/v1",
            "parent_state_hash": proposal.parent_state_hash,
            "operation": proposal.operation,
            "payload": proposal.payload,
            "evidence_ids": proposal.evidence_ids,
            "proposer": proposal.proposer,
            "created_at": proposal.created_at,
            "capability_label": proposal.capability_label,
        }
    )
