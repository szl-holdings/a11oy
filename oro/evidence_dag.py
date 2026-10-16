"""Read-only evidence DAG projection; not a replacement for canonical Khipu DAG.

Use for Second Brain / Living Anatomy inspection only. No signing or writes.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Iterable

from .brain_anatomy_contract import EvidenceHandle, evidence_projection, projection_digest

MAX_NODES = 64
MAX_EDGES = 128
MAX_ID_LENGTH = 128


@dataclass(frozen=True)
class EvidenceNode:
    node_id: str
    handle: EvidenceHandle
    parents: tuple[str, ...] = ()
    formula: str | None = None
    proof_status: str = 'UNVERIFIED'


def _checked_id(value: object, kind: str) -> str:
    if (not isinstance(value, str) or not value or len(value) > MAX_ID_LENGTH
            or value != value.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError(f'Malformed DAG {kind} identifier')
    return value


def project_dag(nodes: Iterable[EvidenceNode]) -> dict:
    """Validate a bounded, closed DAG and emit handles, never content."""
    by_id: dict[str, EvidenceNode] = {}
    parents_by_id: dict[str, tuple[str, ...]] = {}
    edge_count = 0
    for node in nodes:
        # Reading one extra item detects an unbounded generator without draining it.
        if len(by_id) == MAX_NODES:
            raise ValueError('DAG node limit exceeded')
        if not isinstance(node, EvidenceNode):
            raise ValueError('Malformed DAG node')
        node_id = _checked_id(node.node_id, 'node')
        if node_id in by_id:
            raise ValueError('Duplicate DAG node identifier')
        if not isinstance(node.parents, (tuple, list)):
            raise ValueError('Malformed DAG parents')
        if len(node.parents) > MAX_EDGES - edge_count:
            raise ValueError('DAG edge limit exceeded')
        parents: set[str] = set()
        for parent in node.parents:
            parent_id = _checked_id(parent, 'parent')
            if parent_id in parents:
                raise ValueError('Duplicate DAG parent identifier')
            parents.add(parent_id)
        edge_count += len(parents)
        by_id[node_id] = node
        parents_by_id[node_id] = tuple(sorted(parents))

    children: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    remaining_parents = {node_id: len(parents) for node_id, parents in parents_by_id.items()}
    for node_id, parents in parents_by_id.items():
        for parent in parents:
            if parent not in by_id:
                raise ValueError('Missing DAG dependency')
            children[parent].append(node_id)

    ready = [node_id for node_id, count in remaining_parents.items() if count == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        node_id = heapq.heappop(ready)
        order.append(node_id)
        for child in children[node_id]:
            remaining_parents[child] -= 1
            if remaining_parents[child] == 0:
                heapq.heappush(ready, child)
    if len(order) != len(by_id):
        raise ValueError('DAG cycle detected')

    projections = []
    for node_id in order:
        node = by_id[node_id]
        evidence = evidence_projection(node.handle, formula=node.formula,
                                       proof_status=node.proof_status)
        projections.append({'node_id': node_id, 'parents': list(parents_by_id[node_id]),
                            'evidence': evidence, 'digest': projection_digest(evidence)})
    return {'schema': 'szl.oro.evidence-dag/v1', 'status': 'MODELED_READ_ONLY',
            'execution_authority': False, 'nodes': projections}
