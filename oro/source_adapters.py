"""Bounded, read-only adapters for existing evidence owners.

This module observes an already-created Wire F Khipu DAG. It does not create a
DAG, checkpoint, receipt, signature, proof, or ORO execution decision. The
other inputs are explicit snapshots from their respective read-only adapters.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any

from .brain_anatomy_contract import EvidenceHandle
from .evidence_dag import EvidenceNode, project_dag

_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SECOND_BRAIN_FIELDS = frozenset({
    "nodeId", "nodeKind", "label", "note", "source", "sha256", "sourceId",
})
_HATUN_HANDLES = frozenset({
    "khipu.handle.alpha", "khipu.handle.beta", "nav.waypoint.17",
    "receipt.bind.owner-pubkey",
})
_ANATOMY_FIELDS = frozenset({"id", "label", "role", "depends_on", "control_after"})
MAX_KHIPU_NODES = 32
MAX_SECOND_BRAIN_HANDLES = 12
MAX_ANATOMY_TOPOLOGY_NODES = 64


def _hex(value: Any, size: int, field: str) -> str:
    pattern = _HEX40 if size == 40 else _HEX64
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"{field} must be lowercase {size}-hex")
    return value


def _pointer(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64 or not _HEX64.fullmatch(value.lower()):
        raise ValueError("Second Brain pointer must be 64-hex")
    return value.lower()


def _commit(value: Any, field: str) -> str:
    return "commit:" + _hex(value, 40, field)


def _canonical_khipu(dag: Any) -> tuple[list[EvidenceNode], dict[str, Any]]:
    if dag is None:
        return [], {"state": "UNKNOWN", "count": 0}
    recent = getattr(dag, "recent", None)
    if not callable(recent):
        raise ValueError("existing canonical Khipu DAG reader required")
    # Wire F's recent() is a lock-protected read. Never call get_dag(),
    # verify(), checkpoint(), tick(), append_signed(), or an ORO writer.
    raw = recent(MAX_KHIPU_NODES + 1)
    if not isinstance(raw, (list, tuple)) or len(raw) > MAX_KHIPU_NODES + 1:
        raise ValueError("canonical Khipu snapshot exceeds read bound")
    window = raw[-MAX_KHIPU_NODES:]
    entries: list[tuple[str, tuple[str, ...], int]] = []
    seen: set[str] = set()
    for item in window:
        if not isinstance(item, Mapping) or item.get("space") != "a11oy" or item.get("wire") != "F":
            raise ValueError("unexpected canonical Khipu node")
        digest = _hex(item.get("digest"), 64, "Khipu node digest")
        index = item.get("index")
        parents = item.get("parents")
        if type(index) is not int or index < 0 or not isinstance(parents, list) or len(parents) > 1:
            raise ValueError("invalid canonical Khipu position or parent count")
        if digest in seen:
            raise ValueError("duplicate canonical Khipu digest")
        seen.add(digest)
        entries.append((digest, tuple(_hex(p, 64, "Khipu parent") for p in parents), index))
    nodes: list[EvidenceNode] = []
    omitted_parents: list[str] = []
    for offset, (digest, parents, index) in enumerate(entries):
        if offset and index != entries[offset - 1][2] + 1:
            raise ValueError("noncontiguous canonical Khipu window")
        if (index == 0 and parents) or (index > 0 and not parents):
            raise ValueError("invalid canonical Khipu chain position")
        visible: list[str] = []
        for parent in parents:
            if offset and parent == entries[offset - 1][0]:
                visible.append("khipu:" + parent)
            elif offset == 0:
                omitted_parents.append(parent)
            else:
                raise ValueError("canonical Khipu parent does not link to immediate predecessor")
        nodes.append(EvidenceNode(
            "khipu:" + digest,
            EvidenceHandle("szl-holdings/a11oy/wire-f", "sha256:" + digest, digest),
            tuple(visible),
        ))
    # A bounded tail can omit prior nodes. Report the boundary rather than
    # inventing an anchor node or claiming a complete chain.
    partial = len(raw) > MAX_KHIPU_NODES or bool(omitted_parents)
    return nodes, {
        "state": "DECLARED" if nodes else "UNKNOWN",
        "count": len(nodes),
        "last_observed_digest": entries[-1][0] if entries else None,
        "window_complete": not partial,
        "omitted_parent_digests": omitted_parents,
        "signature_verification": "UNKNOWN",
    }


def _second_brain(snapshot: Mapping[str, Any] | None, revision: str | None) -> tuple[list[EvidenceNode], dict[str, Any]]:
    if snapshot is None:
        return [], {"state": "UNKNOWN", "count": 0}
    if not isinstance(snapshot, Mapping):
        raise ValueError("Second Brain snapshot must be an object")
    if snapshot.get("status") == "UNAVAILABLE":
        if snapshot.get("handles"):
            raise ValueError("unavailable Second Brain snapshot has handles")
        return [], {"state": "UNAVAILABLE", "count": 0}
    if (snapshot.get("status") != "LIVE"
            or snapshot.get("schema") != "szl.second-brain.retrieve/v1"
            or snapshot.get("ready") is not True
            or snapshot.get("content_access") != "HANDLES_ONLY"
            or snapshot.get("index_is_model_weights") is not False
            or type(snapshot.get("raw_graph_nodes_admitted_to_gradients")) is not int
            or snapshot.get("raw_graph_nodes_admitted_to_gradients") != 0):
        raise ValueError("Second Brain handle-only contract mismatch")
    source_revision = _commit(revision, "Second Brain source revision")
    handles = snapshot.get("handles")
    if not isinstance(handles, list) or not 1 <= len(handles) <= MAX_SECOND_BRAIN_HANDLES:
        raise ValueError("Second Brain handle count outside bound")
    if type(snapshot.get("k")) is not int or snapshot["k"] != len(handles):
        raise ValueError("Second Brain count does not bind the handles")
    nodes: list[EvidenceNode] = []
    for handle in handles:
        if (not isinstance(handle, Mapping)
                or not 6 <= len(handle) <= len(_SECOND_BRAIN_FIELDS)
                or not {"nodeId", "nodeKind", "label", "note", "source", "sha256"} <= set(handle)
                or not set(handle) <= _SECOND_BRAIN_FIELDS):
            raise ValueError("invalid Second Brain handle")
        node_id = handle.get("nodeId")
        if not isinstance(node_id, str) or not node_id or len(node_id) > 256:
            raise ValueError("invalid Second Brain node identifier")
        try:
            node_id_bytes = node_id.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("invalid Second Brain node identifier") from exc
        if len(node_id_bytes) > 256:
            raise ValueError("invalid Second Brain node identifier")
        pointer = _pointer(handle.get("sha256"))
        # Hash the upstream ID so a label, note, query, or path cannot escape.
        opaque_id = hashlib.sha256(node_id_bytes).hexdigest()
        nodes.append(EvidenceNode(
            "second-brain:" + opaque_id,
            EvidenceHandle("szl-holdings/szl-second-brain", source_revision, pointer),
        ))
    return nodes, {
        "state": "DECLARED", "count": len(nodes),
        "source_revision_binding": "DECLARED",
        "content_hash_verification": "UNKNOWN",
    }


def _anatomy(snapshot: Mapping[str, Any] | None) -> tuple[list[EvidenceNode], dict[str, Any]]:
    if snapshot is None:
        return [], {"state": "UNKNOWN", "count": 0}
    if not isinstance(snapshot, Mapping):
        raise ValueError("Anatomy snapshot must be an object")
    if snapshot.get("ready") is False:
        return [], {"state": "UNAVAILABLE", "count": 0}
    observation_state = snapshot.get("state")
    if (snapshot.get("ready") is not True or not isinstance(observation_state, str)
            or observation_state not in {"OBSERVED", "STALE", "PENDING", "FAILED", "UNAVAILABLE", "REJECTED"}):
        raise ValueError("Anatomy observation state mismatch")
    if observation_state in {"PENDING", "FAILED", "UNAVAILABLE", "REJECTED"}:
        state = ("UNAVAILABLE" if observation_state == "UNAVAILABLE" else
                 "UNKNOWN" if observation_state == "PENDING" else "BLOCKED")
        return [], {"state": state, "observation_state": observation_state, "count": 0}
    source = snapshot.get("source")
    dag = snapshot.get("dag")
    if (not isinstance(source, Mapping) or not isinstance(dag, Mapping)
            or source.get("repository") != "szl-holdings/a11oy"
            or source.get("path") != "console/assets/brain-frontier-v7.json"
            or dag.get("state") != "MODELED_PLAN_ONLY"
            or not isinstance(dag.get("decision"), str)
            or dag.get("decision") not in {"READY_TO_ORCHESTRATE", "REVISE"}
            or dag.get("execution_authorized") is not False):
        raise ValueError("Anatomy modeled source contract mismatch")
    topology = dag.get("nodes")
    if (not isinstance(topology, list) or not 1 <= len(topology) <= MAX_ANATOMY_TOPOLOGY_NODES
            or type(dag.get("node_count")) is not int or dag["node_count"] != len(topology)):
        raise ValueError("Anatomy topology outside bound")
    _hex(dag.get("contract_digest"), 64, "Anatomy contract digest")
    ids: set[str] = set()
    edges: dict[str, list[str]] = {}
    for node in topology:
        if (not isinstance(node, Mapping) or len(node) != len(_ANATOMY_FIELDS)
                or set(node) != _ANATOMY_FIELDS):
            raise ValueError("invalid Anatomy topology node")
        node_id = node.get("id")
        depends_on = node.get("depends_on")
        control_after = node.get("control_after")
        if (not isinstance(node_id, str) or not node_id or len(node_id) > 128
                or node_id in ids
                or any(not isinstance(node.get(field), str) or not node[field]
                       or len(node[field]) > 256 for field in ("label", "role"))
                or not isinstance(depends_on, list) or not isinstance(control_after, list)
                or len(depends_on) > MAX_ANATOMY_TOPOLOGY_NODES
                or len(control_after) > MAX_ANATOMY_TOPOLOGY_NODES):
            raise ValueError("invalid Anatomy topology node")
        parents = depends_on + control_after
        if (not all(isinstance(p, str) and p and len(p) <= 128 for p in parents)
                or len(depends_on) != len(set(depends_on))
                or len(control_after) != len(set(control_after))):
            raise ValueError("invalid Anatomy topology node")
        ids.add(node_id)
        edges[node_id] = parents
    if any(parent not in ids for parents in edges.values() for parent in parents):
        raise ValueError("Anatomy topology dependency missing")
    remaining = {node_id: set(parents) for node_id, parents in edges.items()}
    ready = {node_id for node_id, parents in remaining.items() if not parents}
    visited = 0
    expected_layers: list[list[str]] = []
    while ready:
        layer = sorted(ready)
        expected_layers.append(layer)
        visited += len(layer)
        ready = set()
        for node_id in layer:
            for child, parents in remaining.items():
                if node_id in parents:
                    parents.remove(node_id)
                    if not parents:
                        ready.add(child)
    if visited != len(topology):
        raise ValueError("Anatomy topology cycle")
    layers = dag.get("layers")
    if not isinstance(layers, list) or not 1 <= len(layers) <= len(topology):
        raise ValueError("Anatomy topology layers mismatch")
    layer_members = 0
    for layer in layers:
        if not isinstance(layer, list) or not layer or len(layer) > len(topology):
            raise ValueError("Anatomy topology layers mismatch")
        layer_members += len(layer)
        if layer_members > len(topology) or any(not isinstance(item, str) for item in layer):
            raise ValueError("Anatomy topology layers mismatch")
    if sorted(item for layer in layers for item in layer) != sorted(ids):
        raise ValueError("Anatomy topology layers mismatch")
    if layers != expected_layers:
        raise ValueError("Anatomy topology layers violate dependency order")
    _hex(snapshot.get("snapshot_sha256"), 64, "Anatomy snapshot digest")
    digest = _hex(source.get("sha256"), 64, "Anatomy source digest")
    revision = _commit(source.get("revision"), "Anatomy source revision")
    # Anatomy topology has no per-node content hashes; bind its source once.
    return [EvidenceNode(
        "anatomy:" + digest,
        EvidenceHandle("szl-holdings/a11oy/console/assets/brain-frontier-v7.json", revision, digest),
    )], {
        "state": "MODELED", "observation_state": observation_state,
        "count": 1, "topology_node_count": len(topology),
        "source_revision_binding": "DECLARED", "execution_authority": False,
    }


def _hatun(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    if snapshot is None:
        return {"state": "UNKNOWN", "count": 0}
    if (not isinstance(snapshot, Mapping)
            or not isinstance(snapshot.get("action"), str)
            or snapshot.get("action") not in {"NAVIGATE", "ABSTAIN", "REFUSE"}
            or not isinstance(snapshot.get("handles"), list)
            or len(snapshot["handles"]) > 4
            or any(not isinstance(handle, str) or handle not in _HATUN_HANDLES
                   for handle in snapshot["handles"])
            or len(snapshot["handles"]) != len(set(snapshot["handles"]))):
        raise ValueError("Hatun local adapter is not an unhydrated bounded declaration")
    if snapshot["action"] == "REFUSE":
        if (snapshot["handles"] or snapshot.get("reason") != "INVENTED_IDENTIFIER"
                or snapshot.get("hydrated") not in (None, False)):
            raise ValueError("Hatun refusal contract mismatch")
    elif snapshot.get("hydrated") is not False:
        raise ValueError("Hatun local adapter is not an unhydrated bounded declaration")
    # Hatun's four literal identifiers have no digest or immutable revision.
    return {"state": "DECLARED", "count": 0, "evidence_handles": "UNAVAILABLE"}


def project_source_snapshots(*, canonical_khipu_dag: Any = None,
                             second_brain: Mapping[str, Any] | None = None,
                             second_brain_revision: str | None = None,
                             anatomy: Mapping[str, Any] | None = None,
                             hatun: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Join existing owner snapshots as disconnected inspection components.

    No cross-source causal edge is inferred. All evidence status stays
    UNVERIFIED; hashes are pointers, not verified content or signatures.
    """
    khipu_nodes, khipu_state = _canonical_khipu(canonical_khipu_dag)
    brain_nodes, brain_state = _second_brain(second_brain, second_brain_revision)
    anatomy_nodes, anatomy_state = _anatomy(anatomy)
    hatun_state = _hatun(hatun)
    result = project_dag([*khipu_nodes, *brain_nodes, *anatomy_nodes])
    result["sources"] = {
        "canonical_khipu": khipu_state,
        "second_brain": brain_state,
        "anatomy": anatomy_state,
        "hatun": hatun_state,
    }
    result["promotion_authority"] = False
    result["signing_authority"] = False
    return result
