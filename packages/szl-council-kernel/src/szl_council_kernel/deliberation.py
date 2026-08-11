from __future__ import annotations

"""Proof-Carrying Deliberation Graph and append-only Minority Truth Vault."""

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .canonical import digest_object, require_digest, require_identifier
from .errors import IntegrityError, ValidationError

NODE_TYPES = {"CLAIM", "EVIDENCE", "STANCE", "CHALLENGE", "DECISION", "ACTION", "OUTCOME"}
EDGE_TYPES = {"SUPPORTS", "OPPOSES", "CHALLENGES", "DERIVES", "AUTHORIZES", "VERIFIES", "CAUSES", "SETTLES"}
_FORBIDDEN_KEYS = {
    "chain_of_thought",
    "private_reasoning",
    "raw_prompt",
    "system_prompt",
    "credentials",
    "secret",
    "api_key",
    "access_token",
}


def _scan_forbidden(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ValidationError(f"forbidden private field in deliberation graph: {path}.{key}")
            _scan_forbidden(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_forbidden(item, f"{path}[{index}]")


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    node_type: str
    case_id: str
    body: Mapping[str, Any]
    evidence_digests: tuple[str, ...]
    created_at: str
    schema: str = "szl.deliberation-node/v1"

    def __post_init__(self) -> None:
        require_identifier(self.node_id, field="node_id")
        require_identifier(self.case_id, field="case_id")
        if self.node_type not in NODE_TYPES:
            raise ValidationError(f"unsupported graph node type: {self.node_type}")
        _scan_forbidden(self.body)
        object.__setattr__(self, "evidence_digests", tuple(sorted(set(require_digest(item) for item in self.evidence_digests))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "node_id": self.node_id,
            "node_type": self.node_type,
            "case_id": self.case_id,
            "body": dict(self.body),
            "evidence_digests": list(self.evidence_digests),
            "created_at": self.created_at,
        }

    @property
    def digest(self) -> str:
        return digest_object(self.to_dict())


@dataclass(frozen=True, slots=True)
class GraphEdge:
    edge_id: str
    case_id: str
    edge_type: str
    source_digest: str
    target_digest: str
    body: Mapping[str, Any]
    schema: str = "szl.deliberation-edge/v1"

    def __post_init__(self) -> None:
        require_identifier(self.edge_id, field="edge_id")
        require_identifier(self.case_id, field="case_id")
        if self.edge_type not in EDGE_TYPES:
            raise ValidationError(f"unsupported graph edge type: {self.edge_type}")
        require_digest(self.source_digest, field="source_digest")
        require_digest(self.target_digest, field="target_digest")
        _scan_forbidden(self.body)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "edge_id": self.edge_id,
            "case_id": self.case_id,
            "edge_type": self.edge_type,
            "source_digest": self.source_digest,
            "target_digest": self.target_digest,
            "body": dict(self.body),
        }

    @property
    def digest(self) -> str:
        return digest_object(self.to_dict())


class DeliberationGraph:
    def __init__(self, case_id: str) -> None:
        require_identifier(case_id, field="case_id")
        self.case_id = case_id
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}

    def add_node(self, node: GraphNode) -> str:
        if node.case_id != self.case_id:
            raise ValidationError("graph node case mismatch")
        digest = node.digest
        if node.node_id in self._nodes and self._nodes[node.node_id].digest != digest:
            raise IntegrityError("graph node id cannot be rewritten")
        self._nodes[node.node_id] = node
        return digest

    def add_edge(self, edge: GraphEdge) -> str:
        if edge.case_id != self.case_id:
            raise ValidationError("graph edge case mismatch")
        known = {node.digest for node in self._nodes.values()}
        if edge.source_digest not in known or edge.target_digest not in known:
            raise ValidationError("graph edge references an unknown node")
        digest = edge.digest
        if edge.edge_id in self._edges and self._edges[edge.edge_id].digest != digest:
            raise IntegrityError("graph edge id cannot be rewritten")
        self._edges[edge.edge_id] = edge
        return digest

    def to_dict(self) -> dict[str, Any]:
        body = {
            "schema": "szl.proof-carrying-deliberation-graph/v1",
            "case_id": self.case_id,
            "nodes": [self._nodes[key].to_dict() for key in sorted(self._nodes)],
            "edges": [self._edges[key].to_dict() for key in sorted(self._edges)],
        }
        return {**body, "graph_digest": digest_object(body)}

    def verify(self) -> dict[str, Any]:
        errors: list[str] = []
        node_digests = {node.digest for node in self._nodes.values()}
        for edge in self._edges.values():
            if edge.source_digest not in node_digests:
                errors.append(f"MISSING_SOURCE:{edge.edge_id}")
            if edge.target_digest not in node_digests:
                errors.append(f"MISSING_TARGET:{edge.edge_id}")
        decision_count = sum(1 for node in self._nodes.values() if node.node_type == "DECISION")
        if decision_count > 1:
            errors.append("MULTIPLE_TERMINAL_DECISIONS")
        value = self.to_dict()
        observed = value.pop("graph_digest")
        if digest_object(value) != observed:
            errors.append("GRAPH_DIGEST_MISMATCH")
        return {
            "schema": "szl.deliberation-graph-verification/v1",
            "status": "PASS" if not errors else "FAIL",
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
            "decision_count": decision_count,
            "errors": errors,
        }


class MinorityTruthVault:
    """Append-only signed-opposition index; historical entries are never overwritten."""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    def preserve(
        self,
        *,
        case_id: str,
        role: str,
        vote: str,
        assessment_digest: str,
        counterevidence_digests: Iterable[str],
        reason_codes: Iterable[str],
        observed_at: str,
    ) -> str:
        if vote not in {"OPPOSE", "VETO"}:
            raise ValidationError("minority vault accepts only OPPOSE or VETO")
        entry = {
            "schema": "szl.minority-truth-entry/v1",
            "case_id": case_id,
            "role": role,
            "vote": vote,
            "assessment_digest": require_digest(assessment_digest, field="assessment_digest"),
            "counterevidence_digests": sorted(set(require_digest(item) for item in counterevidence_digests)),
            "reason_codes": sorted(set(reason_codes)),
            "observed_at": observed_at,
            "prior_entry_digest": self._entries[-1]["entry_digest"] if self._entries else None,
        }
        entry_digest = digest_object(entry)
        self._entries.append({**entry, "entry_digest": entry_digest})
        return entry_digest

    def entries(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(item) for item in self._entries)

    def verify(self) -> dict[str, Any]:
        previous = None
        errors: list[str] = []
        for index, stored in enumerate(self._entries):
            body = {key: value for key, value in stored.items() if key != "entry_digest"}
            if body["prior_entry_digest"] != previous:
                errors.append(f"CHAIN_MISMATCH:{index}")
            if digest_object(body) != stored["entry_digest"]:
                errors.append(f"DIGEST_MISMATCH:{index}")
            previous = stored["entry_digest"]
        return {
            "schema": "szl.minority-truth-vault-verification/v1",
            "status": "PASS" if not errors else "FAIL",
            "entry_count": len(self._entries),
            "head_digest": previous,
            "errors": errors,
        }
