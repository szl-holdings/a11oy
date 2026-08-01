# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Lutar, Stephen P. - SZL Holdings
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""Governed Graph Operations: deterministic topology analysis for A11oy.

Taxonomy home: governance/services.  This module turns a proposed graph of
bounded jobs and local loops into an auditable execution *plan*.  It never runs
agents, calls providers, mutates repositories, or emits a receipt: the API is a
pure, deterministic analysis surface.  A later executor must re-check the
returned contract against policy and obtain the required receipts/human gates.

The design deliberately distinguishes:

* data dependencies from control/resource dependencies;
* bounded local loops from illegal top-level graph cycles;
* declared parallel work from hidden shared-resource conflicts;
* expected fan-in from structurally received inputs;
* maker context from an independent verifier context; and
* graph agreement from external truth anchors.

Doctrine v11: analysis is MODELED, side effects are zero, and GET signs nothing.
"""

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "szl.governed-graph/v1"
IMPLEMENTATION_STATUS = "REAL"
EVIDENCE_LABEL = "MODELED"
EXECUTION_MODE = "PLAN_ONLY"
MAX_BODY_BYTES = 96 * 1024
MAX_NODES = 64
MAX_LIST_ITEMS = 64
MAX_TEXT = 512

_ROLES = {
    "scope",
    "planner",
    "worker",
    "reducer",
    "verifier",
    "governance",
    "human_gate",
    "synthesizer",
    "loop",
    "publisher",
}
_AUTHORITIES = {"READ_ONLY", "PROPOSE", "WRITE_GOVERNED", "HUMAN"}
_ANCHOR_TYPES = {"test", "source", "human", "receipt", "runtime"}
_TOP_LEVEL_KEYS = {
    "schema",
    "graph_id",
    "goal",
    "external_inputs",
    "nodes",
    "anchors",
    "budget",
}
_NODE_KEYS = {
    "id",
    "label",
    "role",
    "depends_on",
    "control_after",
    "consumes",
    "produces",
    "reads",
    "writes",
    "resources",
    "fresh_context",
    "verifier_for",
    "side_effecting",
    "authority",
    "max_iterations",
    "exit_conditions",
}
_ANCHOR_KEYS = {"id", "type", "nodes", "required", "description"}
_BUDGET_KEYS = {
    "max_nodes",
    "max_parallel",
    "max_depth",
    "max_total_iterations",
}


class GraphContractError(ValueError):
    """Raised when a graph request does not satisfy the bounded input contract."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _plain_object(value: Any, field: str) -> dict:
    if not isinstance(value, dict):
        raise GraphContractError(f"{field} must be an object")
    return value


def _bounded_text(value: Any, field: str, *, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise GraphContractError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum:
        raise GraphContractError(f"{field} must contain 1-{maximum} characters")
    return cleaned


def _string_list(value: Any, field: str, *, maximum: int = MAX_LIST_ITEMS) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum:
        raise GraphContractError(f"{field} must be a list with at most {maximum} items")
    result = []
    for index, item in enumerate(value):
        result.append(_bounded_text(item, f"{field}[{index}]", maximum=128))
    if len(result) != len(set(result)):
        raise GraphContractError(f"{field} contains duplicate values")
    return result


def _bounded_int(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GraphContractError(f"{field} must be an integer")
    if value < minimum or value > maximum:
        raise GraphContractError(f"{field} must be between {minimum} and {maximum}")
    return value


def validate_graph_contract(payload: Any) -> dict:
    """Validate and normalize the public graph contract; reject unknown fields."""

    raw = _plain_object(payload, "request")
    unknown = sorted(set(raw) - _TOP_LEVEL_KEYS)
    if unknown:
        raise GraphContractError(f"unknown top-level fields: {', '.join(unknown)}")
    if raw.get("schema") != SCHEMA:
        raise GraphContractError(f"schema must equal {SCHEMA}")

    graph_id = _bounded_text(raw.get("graph_id"), "graph_id", maximum=128)
    goal = _bounded_text(raw.get("goal"), "goal", maximum=2048)
    external_inputs = _string_list(raw.get("external_inputs", []), "external_inputs")

    raw_nodes = raw.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise GraphContractError("nodes must be a non-empty list")
    if len(raw_nodes) > MAX_NODES:
        raise GraphContractError(f"nodes exceeds the hard cap of {MAX_NODES}")

    nodes = []
    seen_ids = set()
    for index, item in enumerate(raw_nodes):
        node = _plain_object(item, f"nodes[{index}]")
        extra = sorted(set(node) - _NODE_KEYS)
        if extra:
            raise GraphContractError(
                f"nodes[{index}] has unknown fields: {', '.join(extra)}"
            )
        node_id = _bounded_text(node.get("id"), f"nodes[{index}].id", maximum=64)
        if node_id in seen_ids:
            raise GraphContractError(f"duplicate node id: {node_id}")
        seen_ids.add(node_id)
        role = _bounded_text(node.get("role"), f"nodes[{index}].role", maximum=32)
        if role not in _ROLES:
            raise GraphContractError(f"unsupported role for {node_id}: {role}")
        authority = node.get("authority", "READ_ONLY")
        if authority not in _AUTHORITIES:
            raise GraphContractError(f"unsupported authority for {node_id}: {authority}")
        side_effecting = node.get("side_effecting", False)
        fresh_context = node.get("fresh_context", False)
        if not isinstance(side_effecting, bool) or not isinstance(fresh_context, bool):
            raise GraphContractError(
                f"side_effecting and fresh_context must be booleans for {node_id}"
            )
        max_iterations = node.get("max_iterations")
        if max_iterations is not None:
            max_iterations = _bounded_int(
                max_iterations,
                f"nodes[{index}].max_iterations",
                minimum=1,
                maximum=32,
            )
        normalized = {
            "id": node_id,
            "label": _bounded_text(
                node.get("label", node_id), f"nodes[{index}].label", maximum=128
            ),
            "role": role,
            "depends_on": _string_list(
                node.get("depends_on", []), f"nodes[{index}].depends_on"
            ),
            "control_after": _string_list(
                node.get("control_after", []), f"nodes[{index}].control_after"
            ),
            "consumes": _string_list(
                node.get("consumes", []), f"nodes[{index}].consumes"
            ),
            "produces": _string_list(
                node.get("produces", []), f"nodes[{index}].produces"
            ),
            "reads": _string_list(node.get("reads", []), f"nodes[{index}].reads"),
            "writes": _string_list(node.get("writes", []), f"nodes[{index}].writes"),
            "resources": _string_list(
                node.get("resources", []), f"nodes[{index}].resources"
            ),
            "fresh_context": fresh_context,
            "verifier_for": _string_list(
                node.get("verifier_for", []), f"nodes[{index}].verifier_for"
            ),
            "side_effecting": side_effecting,
            "authority": authority,
            "max_iterations": max_iterations,
            "exit_conditions": _string_list(
                node.get("exit_conditions", []), f"nodes[{index}].exit_conditions"
            ),
        }
        nodes.append(normalized)

    raw_anchors = raw.get("anchors", [])
    if not isinstance(raw_anchors, list) or len(raw_anchors) > MAX_LIST_ITEMS:
        raise GraphContractError(
            f"anchors must be a list with at most {MAX_LIST_ITEMS} items"
        )
    anchors = []
    anchor_ids = set()
    for index, item in enumerate(raw_anchors):
        anchor = _plain_object(item, f"anchors[{index}]")
        extra = sorted(set(anchor) - _ANCHOR_KEYS)
        if extra:
            raise GraphContractError(
                f"anchors[{index}] has unknown fields: {', '.join(extra)}"
            )
        anchor_id = _bounded_text(anchor.get("id"), f"anchors[{index}].id", maximum=64)
        if anchor_id in anchor_ids:
            raise GraphContractError(f"duplicate anchor id: {anchor_id}")
        anchor_ids.add(anchor_id)
        anchor_type = _bounded_text(
            anchor.get("type"), f"anchors[{index}].type", maximum=32
        )
        if anchor_type not in _ANCHOR_TYPES:
            raise GraphContractError(f"unsupported anchor type: {anchor_type}")
        required = anchor.get("required", True)
        if not isinstance(required, bool):
            raise GraphContractError(f"anchors[{index}].required must be boolean")
        anchors.append(
            {
                "id": anchor_id,
                "type": anchor_type,
                "nodes": _string_list(
                    anchor.get("nodes", []), f"anchors[{index}].nodes"
                ),
                "required": required,
                "description": _bounded_text(
                    anchor.get("description", anchor_id),
                    f"anchors[{index}].description",
                    maximum=256,
                ),
            }
        )

    raw_budget = _plain_object(raw.get("budget", {}), "budget")
    extra_budget = sorted(set(raw_budget) - _BUDGET_KEYS)
    if extra_budget:
        raise GraphContractError(f"budget has unknown fields: {', '.join(extra_budget)}")
    budget = {
        "max_nodes": _bounded_int(
            raw_budget.get("max_nodes", 32), "budget.max_nodes", minimum=1, maximum=64
        ),
        "max_parallel": _bounded_int(
            raw_budget.get("max_parallel", 6),
            "budget.max_parallel",
            minimum=1,
            maximum=16,
        ),
        "max_depth": _bounded_int(
            raw_budget.get("max_depth", 12), "budget.max_depth", minimum=1, maximum=32
        ),
        "max_total_iterations": _bounded_int(
            raw_budget.get("max_total_iterations", 48),
            "budget.max_total_iterations",
            minimum=1,
            maximum=256,
        ),
    }
    return {
        "schema": SCHEMA,
        "graph_id": graph_id,
        "goal": goal,
        "external_inputs": external_inputs,
        "nodes": nodes,
        "anchors": anchors,
        "budget": budget,
    }


def _issue(code: str, message: str, *, nodes: list[str], severity: str) -> dict:
    return {
        "code": code,
        "severity": severity,
        "nodes": sorted(set(nodes)),
        "message": message,
    }


def analyse_graph(payload: Any) -> dict:
    """Return a deterministic, non-effecting topology and governance analysis."""

    graph = validate_graph_contract(payload)
    nodes = graph["nodes"]
    by_id = {node["id"]: node for node in nodes}
    blockers = []
    advisories = []

    dependencies = {}
    children = {node_id: [] for node_id in by_id}
    data_edges = []
    control_edges = []
    for node in nodes:
        node_id = node["id"]
        overlap = set(node["depends_on"]) & set(node["control_after"])
        if overlap:
            raise GraphContractError(
                f"{node_id} repeats dependencies as both data and control edges: "
                + ", ".join(sorted(overlap))
            )
        deps = list(node["depends_on"]) + list(node["control_after"])
        for dep in deps:
            if dep == node_id:
                raise GraphContractError(f"{node_id} cannot depend on itself")
            if dep not in by_id:
                raise GraphContractError(f"{node_id} references unknown dependency: {dep}")
            children[dep].append(node_id)
        dependencies[node_id] = deps
        data_edges.extend(
            {"source": dep, "target": node_id, "kind": "data"}
            for dep in node["depends_on"]
        )
        control_edges.extend(
            {"source": dep, "target": node_id, "kind": "control"}
            for dep in node["control_after"]
        )

    indegree = {node_id: len(dependencies[node_id]) for node_id in by_id}
    ready = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
    layers = []
    order = []
    while ready:
        layer = ready
        layers.append(layer)
        order.extend(layer)
        next_ready = []
        for node_id in layer:
            for child in sorted(children[node_id]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    next_ready.append(child)
        ready = sorted(next_ready)
    if len(order) != len(nodes):
        cycle_nodes = sorted(node_id for node_id, degree in indegree.items() if degree > 0)
        raise GraphContractError(
            "top-level graph contains a cycle; model retries as bounded loop nodes: "
            + ", ".join(cycle_nodes)
        )

    if len(nodes) > graph["budget"]["max_nodes"]:
        blockers.append(
            _issue(
                "NODE_BUDGET_EXCEEDED",
                "Declared node count exceeds the graph budget.",
                nodes=list(by_id),
                severity="BLOCKER",
            )
        )
    if len(layers) > graph["budget"]["max_depth"]:
        blockers.append(
            _issue(
                "DEPTH_BUDGET_EXCEEDED",
                "Critical-path depth exceeds the graph budget.",
                nodes=order,
                severity="BLOCKER",
            )
        )

    loop_iterations = 0
    for node in nodes:
        if node["role"] == "loop":
            if node["max_iterations"] is None or not node["exit_conditions"]:
                blockers.append(
                    _issue(
                        "UNBOUNDED_LOOP",
                        "Loop nodes require max_iterations and at least one exit condition.",
                        nodes=[node["id"]],
                        severity="BLOCKER",
                    )
                )
            else:
                loop_iterations += node["max_iterations"]
        elif node["max_iterations"] is not None or node["exit_conditions"]:
            advisories.append(
                _issue(
                    "LOOP_FIELDS_ON_NON_LOOP",
                    "Loop bounds are ignored unless the node role is loop.",
                    nodes=[node["id"]],
                    severity="ADVISORY",
                )
            )
    if loop_iterations > graph["budget"]["max_total_iterations"]:
        blockers.append(
            _issue(
                "ITERATION_BUDGET_EXCEEDED",
                "Sum of local loop caps exceeds the total iteration budget.",
                nodes=[node["id"] for node in nodes if node["role"] == "loop"],
                severity="BLOCKER",
            )
        )

    external_inputs = set(graph["external_inputs"])
    fake_edges = []
    input_gaps = []
    fan_in = []
    for node in nodes:
        supplied = set(external_inputs)
        for dep in node["depends_on"]:
            produced = set(by_id[dep]["produces"])
            overlap = sorted(produced & set(node["consumes"]))
            if not overlap:
                fake_edges.append(
                    {
                        "source": dep,
                        "target": node["id"],
                        "reason": "consumer declares no use of predecessor output",
                    }
                )
            supplied.update(produced)
        missing = sorted(set(node["consumes"]) - supplied)
        if missing:
            input_gaps.append({"node": node["id"], "missing": missing})
            blockers.append(
                _issue(
                    "INPUT_CONTRACT_GAP",
                    f"Node consumes unavailable inputs: {', '.join(missing)}.",
                    nodes=[node["id"]],
                    severity="BLOCKER",
                )
            )
        if node["role"] in {"reducer", "synthesizer"} and len(node["depends_on"]) > 1:
            received = sum(
                1
                for dep in node["depends_on"]
                if set(by_id[dep]["produces"]) & set(node["consumes"])
            )
            fan_in.append(
                {
                    "node": node["id"],
                    "expected": len(node["depends_on"]),
                    "contractually_received": received,
                    "complete": received == len(node["depends_on"]),
                }
            )
            if received != len(node["depends_on"]):
                blockers.append(
                    _issue(
                        "FAN_IN_INCOMPLETE",
                        "Reducer/synthesizer does not consume a declared output from every worker.",
                        nodes=[node["id"]] + node["depends_on"],
                        severity="BLOCKER",
                    )
                )
    for edge in fake_edges:
        advisories.append(
            _issue(
                "FAKE_DATA_EDGE",
                "No declared artifact crosses this data edge; remove it or make it a control edge.",
                nodes=[edge["source"], edge["target"]],
                severity="ADVISORY",
            )
        )

    hidden_resource_edges = []
    for layer_index, layer in enumerate(layers):
        for left_index, left_id in enumerate(layer):
            left = by_id[left_id]
            for right_id in layer[left_index + 1 :]:
                right = by_id[right_id]
                write_conflicts = sorted(
                    set(left["writes"]) & (set(right["writes"]) | set(right["reads"]))
                    | set(right["writes"]) & set(left["reads"])
                )
                resource_conflicts = sorted(set(left["resources"]) & set(right["resources"]))
                if write_conflicts or resource_conflicts:
                    conflict = {
                        "nodes": [left_id, right_id],
                        "layer": layer_index,
                        "writes": write_conflicts,
                        "resources": resource_conflicts,
                    }
                    hidden_resource_edges.append(conflict)
                    blockers.append(
                        _issue(
                            "HIDDEN_RESOURCE_EDGE",
                            "Nodes scheduled in parallel share mutable state or an exclusive resource.",
                            nodes=[left_id, right_id],
                            severity="BLOCKER",
                        )
                    )

    for node in nodes:
        if node["role"] == "verifier":
            if not node["fresh_context"]:
                blockers.append(
                    _issue(
                        "VERIFIER_CONTEXT_NOT_FRESH",
                        "Verifier must declare fresh_context=true.",
                        nodes=[node["id"]],
                        severity="BLOCKER",
                    )
                )
            if not node["verifier_for"]:
                blockers.append(
                    _issue(
                        "VERIFIER_TARGET_MISSING",
                        "Verifier must name at least one artifact-producing target.",
                        nodes=[node["id"]],
                        severity="BLOCKER",
                    )
                )
            for target in node["verifier_for"]:
                if target not in by_id:
                    raise GraphContractError(
                        f"{node['id']} verifies unknown node: {target}"
                    )
                target_artifacts = set(by_id[target]["produces"])
                consumed_artifacts = set(node["consumes"])
                if (
                    target not in node["depends_on"]
                    or not target_artifacts & consumed_artifacts
                ):
                    blockers.append(
                        _issue(
                            "VERIFIER_ARTIFACT_NOT_BOUND",
                            "Verifier target must be a data dependency with a consumed artifact.",
                            nodes=[node["id"], target],
                            severity="BLOCKER",
                        )
                    )

    anchor_nodes = set()
    required_anchor_types = set()
    for anchor in graph["anchors"]:
        for node_id in anchor["nodes"]:
            if node_id not in by_id:
                raise GraphContractError(
                    f"anchor {anchor['id']} references unknown node: {node_id}"
                )
        if anchor["required"]:
            required_anchor_types.add(anchor["type"])
            anchor_nodes.update(anchor["nodes"])
    terminals = sorted(node_id for node_id, outgoing in children.items() if not outgoing)
    if not required_anchor_types & {"test", "source", "human", "runtime"}:
        blockers.append(
            _issue(
                "EXTERNAL_TRUTH_ANCHOR_MISSING",
                "At least one required test, source, runtime, or human anchor is required.",
                nodes=terminals,
                severity="BLOCKER",
            )
        )
    unanchored_terminals = sorted(set(terminals) - anchor_nodes)
    if unanchored_terminals:
        blockers.append(
            _issue(
                "TERMINAL_NOT_ANCHORED",
                "Every terminal outcome must be covered by a declared anchor.",
                nodes=unanchored_terminals,
                severity="BLOCKER",
            )
        )

    for node in nodes:
        if not node["side_effecting"]:
            continue
        if node["authority"] not in {"WRITE_GOVERNED", "HUMAN"}:
            blockers.append(
                _issue(
                    "WRITE_AUTHORITY_MISSING",
                    "Side-effecting nodes require WRITE_GOVERNED or HUMAN authority.",
                    nodes=[node["id"]],
                    severity="BLOCKER",
                )
            )
        receipt_bound = any(
            anchor["type"] == "receipt"
            and anchor["required"]
            and node["id"] in anchor["nodes"]
            for anchor in graph["anchors"]
        )
        if not receipt_bound:
            blockers.append(
                _issue(
                    "WRITE_RECEIPT_ANCHOR_MISSING",
                    "Side-effecting nodes require a mandatory receipt anchor.",
                    nodes=[node["id"]],
                    severity="BLOCKER",
                )
            )

    distance = {}
    predecessor = {}
    for node_id in order:
        deps = dependencies[node_id]
        if not deps:
            distance[node_id] = 1
            predecessor[node_id] = None
            continue
        best = max(deps, key=lambda dep: (distance[dep], dep))
        distance[node_id] = distance[best] + 1
        predecessor[node_id] = best
    critical_end = max(order, key=lambda node_id: (distance[node_id], node_id))
    critical_path = []
    cursor = critical_end
    while cursor is not None:
        critical_path.append(cursor)
        cursor = predecessor[cursor]
    critical_path.reverse()

    max_parallel = graph["budget"]["max_parallel"]
    schedule = []
    batch_index = 0
    for layer_index, layer in enumerate(layers):
        for start in range(0, len(layer), max_parallel):
            batch = layer[start : start + max_parallel]
            schedule.append(
                {"batch": batch_index, "topology_layer": layer_index, "nodes": batch}
            )
            batch_index += 1

    blockers = sorted(
        blockers,
        key=lambda issue: (issue["code"], issue["nodes"], issue["message"]),
    )
    advisories = sorted(
        advisories,
        key=lambda issue: (issue["code"], issue["nodes"], issue["message"]),
    )
    contract_digest = _sha256(graph)
    return {
        "ok": True,
        "schema": "szl.governed-graph.analysis/v1",
        "graph_id": graph["graph_id"],
        "contract_digest": contract_digest,
        "plan_id": f"ggp-{contract_digest[:20]}",
        "implementation_status": IMPLEMENTATION_STATUS,
        "evidence_label": EVIDENCE_LABEL,
        "decision": "READY_TO_ORCHESTRATE" if not blockers else "REVISE",
        "execution": {
            "mode": EXECUTION_MODE,
            "authorized": False,
            "effectors": 0,
            "provider_calls": 0,
            "writes": 0,
            "note": (
                "This endpoint computes a plan only. An executor must re-validate "
                "the exact digest, pass policy, obtain human approval where declared, "
                "and emit receipts for every write."
            ),
        },
        "topology": {
            "node_count": len(nodes),
            "data_edge_count": len(data_edges),
            "control_edge_count": len(control_edges),
            "layer_count": len(layers),
            "max_declared_parallel": max((len(layer) for layer in layers), default=0),
            "scheduled_parallel_cap": max_parallel,
            "layers": layers,
            "schedule": schedule,
            "critical_path": critical_path,
            "critical_path_nodes": len(critical_path),
            "terminals": terminals,
            "edges": data_edges + control_edges,
        },
        "contracts": {
            "fake_edges": fake_edges,
            "input_gaps": input_gaps,
            "hidden_resource_edges": hidden_resource_edges,
            "fan_in": fan_in,
            "anchor_types": sorted(required_anchor_types),
            "anchored_nodes": sorted(anchor_nodes),
            "bounded_loop_iterations": loop_iterations,
        },
        "gates": {
            "pass": not blockers,
            "blocker_count": len(blockers),
            "advisory_count": len(advisories),
            "blockers": blockers,
            "advisories": advisories,
        },
        "normalized_contract": graph,
    }


def _node(
    node_id: str,
    label: str,
    role: str,
    *,
    depends_on: list[str] | None = None,
    control_after: list[str] | None = None,
    consumes: list[str] | None = None,
    produces: list[str] | None = None,
    writes: list[str] | None = None,
    resources: list[str] | None = None,
    fresh_context: bool = False,
    verifier_for: list[str] | None = None,
    side_effecting: bool = False,
    authority: str = "READ_ONLY",
    max_iterations: int | None = None,
    exit_conditions: list[str] | None = None,
) -> dict:
    return {
        "id": node_id,
        "label": label,
        "role": role,
        "depends_on": depends_on or [],
        "control_after": control_after or [],
        "consumes": consumes or [],
        "produces": produces or [],
        "reads": [],
        "writes": writes or [],
        "resources": resources or [],
        "fresh_context": fresh_context,
        "verifier_for": verifier_for or [],
        "side_effecting": side_effecting,
        "authority": authority,
        "max_iterations": max_iterations,
        "exit_conditions": exit_conditions or [],
    }


def sample_contract(sample_id: str = "protected-release") -> dict:
    """Return one of the audited, deterministic demonstration contracts."""

    common_budget = {
        "max_nodes": 24,
        "max_parallel": 4,
        "max_depth": 10,
        "max_total_iterations": 24,
    }
    if sample_id == "research-diamond":
        return {
            "schema": SCHEMA,
            "graph_id": "research-diamond",
            "goal": "Triangulate a claim from independent primary sources.",
            "external_inputs": ["research.question"],
            "nodes": [
                _node("scope", "Freeze question and source rules", "scope", consumes=["research.question"], produces=["scope.contract"]),
                _node("papers", "Primary paper review", "worker", depends_on=["scope"], consumes=["scope.contract"], produces=["finding.papers"]),
                _node("repos", "Licensed repository review", "worker", depends_on=["scope"], consumes=["scope.contract"], produces=["finding.repos"]),
                _node("operators", "Production operator evidence", "worker", depends_on=["scope"], consumes=["scope.contract"], produces=["finding.operators"]),
                _node("reduce", "Deterministic evidence reduce", "reducer", depends_on=["papers", "repos", "operators"], consumes=["finding.papers", "finding.repos", "finding.operators"], produces=["evidence.bundle"]),
                _node("verify", "Fresh-context source verification", "verifier", depends_on=["reduce"], consumes=["evidence.bundle"], produces=["verification.result"], fresh_context=True, verifier_for=["reduce"]),
                _node("synthesize", "Cited answer or abstention", "synthesizer", depends_on=["verify"], consumes=["verification.result"], produces=["research.answer"]),
            ],
            "anchors": [
                {"id": "source-resolution", "type": "source", "nodes": ["verify", "synthesize"], "required": True, "description": "Every material claim resolves to a primary source."},
            ],
            "budget": common_budget,
        }
    if sample_id == "bounded-repair":
        return {
            "schema": SCHEMA,
            "graph_id": "bounded-repair",
            "goal": "Repair a failing change without an unbounded retry cycle.",
            "external_inputs": ["failure.evidence"],
            "nodes": [
                _node("scope", "Freeze failure evidence", "scope", consumes=["failure.evidence"], produces=["failure.contract"]),
                _node("repair", "Bounded diagnose-test-repair loop", "loop", depends_on=["scope"], consumes=["failure.contract"], produces=["repair.artifact"], max_iterations=3, exit_conditions=["tests_pass", "same_failure_twice", "budget_exhausted"]),
                _node("verify", "Independent regression verification", "verifier", depends_on=["repair"], consumes=["repair.artifact"], produces=["verification.result"], fresh_context=True, verifier_for=["repair"]),
                _node("human", "Human disposition", "human_gate", depends_on=["verify"], consumes=["verification.result"], produces=["human.decision"], authority="HUMAN"),
            ],
            "anchors": [
                {"id": "executed-tests", "type": "test", "nodes": ["verify"], "required": True, "description": "Regression tests run against the repaired artifact."},
                {"id": "human-disposition", "type": "human", "nodes": ["human"], "required": True, "description": "A human owns the final disposition."},
            ],
            "budget": common_budget,
        }
    if sample_id != "protected-release":
        raise GraphContractError(f"unknown sample: {sample_id}")
    return {
        "schema": SCHEMA,
        "graph_id": "protected-release",
        "goal": "Produce an exact-head, independently verified protected release.",
        "external_inputs": ["release.scope"],
        "nodes": [
            _node("scope", "Freeze authority and exact base", "scope", consumes=["release.scope"], produces=["scope.lock"]),
            _node("architecture", "Architecture review", "worker", depends_on=["scope"], consumes=["scope.lock"], produces=["finding.architecture"], writes=["worktree:architecture"]),
            _node("security", "Security review", "worker", depends_on=["scope"], consumes=["scope.lock"], produces=["finding.security"], writes=["worktree:security"]),
            _node("tests", "Test and failure audit", "worker", depends_on=["scope"], consumes=["scope.lock"], produces=["finding.tests"], writes=["worktree:tests"]),
            _node("licensing", "License and provenance review", "worker", depends_on=["scope"], consumes=["scope.lock"], produces=["finding.licensing"], writes=["worktree:licensing"]),
            _node("reduce", "Deterministic finding reduce", "reducer", depends_on=["architecture", "security", "tests", "licensing"], consumes=["finding.architecture", "finding.security", "finding.tests", "finding.licensing"], produces=["review.bundle"]),
            _node("verify", "Fresh-context exact-head verification", "verifier", depends_on=["reduce"], consumes=["review.bundle"], produces=["verification.result"], fresh_context=True, verifier_for=["reduce"]),
            _node("governance", "Policy and protection gate", "governance", depends_on=["verify"], consumes=["verification.result"], produces=["governance.decision"]),
            _node("publish", "Human-approved protected publish", "publisher", depends_on=["governance"], consumes=["governance.decision"], produces=["release.receipt"], writes=["github:protected-main", "huggingface:space"], resources=["release-lane"], side_effecting=True, authority="HUMAN"),
        ],
        "anchors": [
            {"id": "source-head", "type": "source", "nodes": ["scope"], "required": True, "description": "Exact reviewed Git commit and immutable source identity."},
            {"id": "checks", "type": "test", "nodes": ["verify"], "required": True, "description": "Required checks observed on the exact reviewed head."},
            {"id": "human-review", "type": "human", "nodes": ["publish"], "required": True, "description": "Independent authorized approval before publish."},
            {"id": "write-receipt", "type": "receipt", "nodes": ["publish"], "required": True, "description": "Every release write emits a source-bound receipt."},
        ],
        "budget": common_budget,
    }


def status_payload(ns: str = "a11oy") -> dict:
    return {
        "ok": True,
        "service": "a11oy.governed-graph-operations",
        "implementation_status": IMPLEMENTATION_STATUS,
        "evidence_label": EVIDENCE_LABEL,
        "execution_mode": EXECUTION_MODE,
        "schema": SCHEMA,
        "routes": {
            "page": "/graph-operations",
            "status": f"/api/{ns}/v1/graph-operations/status",
            "sample": f"/api/{ns}/v1/graph-operations/sample/{{sample_id}}",
            "analyse": f"/api/{ns}/v1/graph-operations/analyse",
        },
        "samples": ["protected-release", "research-diamond", "bounded-repair"],
        "limits": {"body_bytes": MAX_BODY_BYTES, "nodes": MAX_NODES},
        "truth_boundary": {
            "effectors": 0,
            "writes": 0,
            "provider_calls": 0,
            "receipts_emitted": 0,
            "note": "Real deterministic analyzer; proposed execution remains MODELED.",
        },
        "doctrine": {
            "version": "v11",
            "lambda": "Conjecture 1",
            "khipu_bft": "Conjecture 2",
            "locked_count": 8,
        },
    }


def register(app, ns: str = "a11oy") -> dict:
    """Attach the page and pure-analysis API before the SPA catch-all."""

    from fastapi import Request
    from fastapi.responses import FileResponse, JSONResponse

    page_path = Path(__file__).resolve().parent.parent / "pages" / "graph-operations.html"
    prefix = f"/api/{ns}/v1/graph-operations"

    @app.get("/graph-operations", include_in_schema=False)
    async def graph_operations_page():
        if not page_path.is_file():
            return JSONResponse(
                {
                    "ok": False,
                    "state": "UNAVAILABLE",
                    "reason": "graph operations page is absent from this image",
                },
                status_code=503,
            )
        return FileResponse(
            str(page_path),
            media_type="text/html",
            headers={"cache-control": "no-store"},
        )

    @app.get(prefix + "/status")
    async def graph_operations_status():
        return JSONResponse(status_payload(ns), headers={"cache-control": "no-store"})

    @app.get(prefix + "/sample/{sample_id}")
    async def graph_operations_sample(sample_id: str):
        try:
            contract = sample_contract(sample_id)
        except GraphContractError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=404)
        return JSONResponse(
            {"ok": True, "contract": contract, "analysis": analyse_graph(contract)},
            headers={"cache-control": "no-store"},
        )

    @app.post(prefix + "/analyse")
    async def graph_operations_analyse(request: Request):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                declared_length = int(content_length)
            except ValueError:
                return JSONResponse(
                    {"ok": False, "error": "invalid Content-Length header"},
                    status_code=400,
                )
            if declared_length > MAX_BODY_BYTES:
                return JSONResponse(
                    {"ok": False, "error": "request body exceeds the 96 KiB limit"},
                    status_code=413,
                )
        chunks = []
        body_bytes = 0
        async for chunk in request.stream():
            body_bytes += len(chunk)
            if body_bytes > MAX_BODY_BYTES:
                return JSONResponse(
                    {"ok": False, "error": "request body exceeds the 96 KiB limit"},
                    status_code=413,
                )
            chunks.append(chunk)
        body = b"".join(chunks)
        try:
            payload = json.loads(body.decode("utf-8"))
            result = analyse_graph(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JSONResponse({"ok": False, "error": "invalid JSON body"}, status_code=400)
        except GraphContractError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=422)
        return JSONResponse(result, headers={"cache-control": "no-store"})

    return {
        "ok": True,
        "state": IMPLEMENTATION_STATUS,
        "evidence_label": EVIDENCE_LABEL,
        "routes": [
            "/graph-operations",
            prefix + "/status",
            prefix + "/sample/{sample_id}",
            prefix + "/analyse",
        ],
    }
