"""Read-only evidence DAG projection; not a replacement for canonical Khipu DAG.

Use for Second Brain / Living Anatomy inspection only. No signing or writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .brain_anatomy_contract import EvidenceHandle, evidence_projection, projection_digest


@dataclass(frozen=True)
class EvidenceNode:
    node_id: str
    handle: EvidenceHandle
    parents: tuple[str, ...] = ()
    formula: str | None = None
    proof_status: str = 'UNVERIFIED'


def project_dag(nodes: Iterable[EvidenceNode]) -> dict:
    """Validate a closed, acyclic graph and emit handles, never content."""
    rows = list(nodes)
    by_id = {node.node_id: node for node in rows}
    if len(rows) != len(by_id) or any(not n.node_id for n in rows):
        raise ValueError('Duplicate or empty DAG node identifier')
    states: dict[str, int] = {}
    order: list[str] = []

    def visit(node_id: str) -> None:
        state = states.get(node_id, 0)
        if state == 1:
            raise ValueError('DAG cycle detected')
        if state == 2:
            return
        if node_id not in by_id:
            raise ValueError('Missing DAG dependency')
        states[node_id] = 1
        for parent in by_id[node_id].parents:
            visit(parent)
        states[node_id] = 2
        order.append(node_id)

    for node in rows:
        visit(node.node_id)
    projections = []
    for node_id in order:
        node = by_id[node_id]
        evidence = evidence_projection(node.handle, formula=node.formula,
                                       proof_status=node.proof_status)
        projections.append({'node_id': node_id, 'parents': list(node.parents),
                            'evidence': evidence, 'digest': projection_digest(evidence)})
    return {'schema': 'szl.oro.evidence-dag/v1', 'status': 'MODELED_READ_ONLY',
            'execution_authority': False, 'nodes': projections}
