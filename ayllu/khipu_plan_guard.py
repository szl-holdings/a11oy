# SPDX-License-Identifier: Apache-2.0
"""Fail-closed Khipu proposal invariants; no inference, resolution or promotion.

Inspired by independently checked retrieval constraints, not external code.
The model sees HANDLE metadata only. Identity binding does NOT prove relevance,
truth, serving weights, independent evaluation, or execution authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_PLAN_KEYS = frozenset({
    "planId", "capabilityProfile", "provenance", "query", "contentAccess",
    "candidates", "decision", "steps", "citedNodeIds", "groundedOnly",
    "brainBinding", "controllerBoundary", "abstainReason",
})
_CANDIDATE_KEYS = frozenset({"nodeId", "nodeKind", "label", "note"})
_STEP_KEYS = frozenset({"action", "nodeId", "rationale"})
_KINDS = frozenset({"ARTIFACT", "CLAIM", "EDGE", "INDEX", "SUMMARY"})
_LABELS = frozenset({"MEASURED", "REPORTED", "DECLARED", "SIMULATED", "UNKNOWN", "UNAVAILABLE"})
_ACTIONS = frozenset({"RETRIEVE", "EXPAND", "CITE"})


@dataclass(frozen=True)
class PlanCheck:
    admitted_structure: bool
    code: str
    cited_node_ids: tuple[str, ...] = ()
    semantic_relevance_verified: bool = False
    execution_authorized: bool = False
    signer_verified: bool = False


def _refuse(code: str) -> PlanCheck:
    return PlanCheck(False, code)


def _nonempty(value: Any, *, limit: int = 8192) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit


def validate_khipu_plan(
    plan: Any, handles: Any, evidence: Any, *, requested_query: str,
) -> PlanCheck:
    """Require deterministic invariants for a NAVIGATE or ABSTAIN proposal.

    Exactly matching offer/evidence digests and handle IDs establish a scoped
    structural binding; they do not establish that a node answers the question.
    No raw document text, semantic LLM judge, I/O, signing, or retries.
    """
    if type(plan) is not dict or set(plan) != _PLAN_KEYS:
        return _refuse("PLAN_SHAPE")
    if (
        not _nonempty(plan["planId"], limit=128)
        or plan["capabilityProfile"] != "SZL-Khipu-1.5B-BrainNavigator"
        or plan["provenance"] != "MODEL_PROPOSED"
        or plan["contentAccess"] != "HANDLES_ONLY"
        or plan["groundedOnly"] is not True
        or not _nonempty(requested_query)
        or plan["query"] != requested_query
        or not _nonempty(plan["controllerBoundary"])
    ):
        return _refuse("PLAN_AUTHORITY_OR_QUERY")
    binding = plan["brainBinding"]
    if (
        type(binding) is not dict
        or set(binding) != {"protocol", "status", "note"}
        or binding["protocol"] != "khipu-retrieval"
        or binding["status"] != "NOT_RESOLVED"
        or not _nonempty(binding["note"])
    ):
        return _refuse("MODEL_CANNOT_RESOLVE_CONTENT")
    if (
        type(handles) is not list or not 0 < len(handles) <= 64
        or type(evidence) is not list or len(evidence) > 64
    ):
        return _refuse("CONTROLLER_OFFER_INVALID")
    offered: dict[str, tuple[str, str]] = {}
    for row in handles:
        if type(row) is not dict:
            return _refuse("CONTROLLER_OFFER_INVALID")
        ident, chunk, digest = row.get("nodeId"), row.get("chunkId"), row.get("sha256")
        if (
            not _nonempty(ident, limit=256) or ident in offered
            or not _nonempty(chunk, limit=256)
            or type(digest) is not str or not _HEX64.fullmatch(digest)
        ):
            return _refuse("CONTROLLER_OFFER_INVALID")
        offered[ident] = (chunk, digest)
    candidates = plan["candidates"]
    if type(candidates) is not list or not 0 < len(candidates) <= len(offered):
        return _refuse("CANDIDATE_SET_INVALID")
    chosen: set[str] = set()
    for row in candidates:
        if type(row) is not dict or set(row) != _CANDIDATE_KEYS:
            return _refuse("CANDIDATE_SHAPE")
        ident = row["nodeId"]
        if (
            type(ident) is not str or ident not in offered or ident in chosen
            or type(row["nodeKind"]) is not str or row["nodeKind"] not in _KINDS
            or type(row["label"]) is not str or row["label"] not in _LABELS
            or not isinstance(row["note"], str)
        ):
            return _refuse("CANDIDATE_NOT_OFFERED")
        chosen.add(ident)
    cites, steps = plan["citedNodeIds"], plan["steps"]
    if type(cites) is not list or type(steps) is not list:
        return _refuse("CITES_OR_STEPS_INVALID")
    if (
        len(cites) != len(set(x for x in cites if isinstance(x, str)))
        or any(type(x) is not str or x not in chosen for x in cites)
        or len(steps) > 96
    ):
        return _refuse("CITED_HANDLE_OUTSIDE_OFFER")
    cite_actions: set[str] = set()
    for row in steps:
        if type(row) is not dict or set(row) != _STEP_KEYS:
            return _refuse("STEP_SHAPE")
        if (
            type(row["action"]) is not str or row["action"] not in _ACTIONS
            or type(row["nodeId"]) is not str or row["nodeId"] not in chosen
            or not _nonempty(row["rationale"])
        ):
            return _refuse("STEP_NOT_OFFERED")
        if row["action"] == "CITE":
            if row["nodeId"] in cite_actions:
                return _refuse("DUPLICATE_CITE_ACTION")
            cite_actions.add(row["nodeId"])
    if cite_actions != set(cites):
        return _refuse("CITE_STEPS_INCONSISTENT")
    decision = plan["decision"]
    if decision == "ABSTAIN":
        if cites or steps or not _nonempty(plan["abstainReason"]):
            return _refuse("ABSTAIN_MUST_HAVE_NO_ACTIONS")
        return PlanCheck(True, "ABSTAIN_STRUCTURE_ONLY_SEMANTICS_UNVERIFIED")
    if decision != "NAVIGATE":
        return _refuse("UNKNOWN_DECISION")
    if not cites or plan["abstainReason"] is not None:
        return _refuse("NAVIGATE_NEEDS_CITATION_AND_NULL_ABSTENTION")
    # Reconcile immutable source-bound identities from the controller, never
    # from model-supplied text. This is structural evidence, not relevance.
    indexed: set[tuple[str, str, str]] = set()
    for row in evidence:
        if type(row) is not dict:
            return _refuse("CONTROLLER_EVIDENCE_INVALID")
        ident, chunk, digest = row.get("node_id"), row.get("chunk_id"), row.get("sha256")
        if (
            not _nonempty(ident, limit=256) or not _nonempty(chunk, limit=256)
            or type(digest) is not str or not _HEX64.fullmatch(digest)
        ):
            return _refuse("CONTROLLER_EVIDENCE_INVALID")
        indexed.add((ident, chunk, digest))
    for ident in cites:
        chunk, digest = offered[ident]
        if (ident, chunk, digest) not in indexed:
            return _refuse("CITED_EVIDENCE_BINDING_MISSING")
    return PlanCheck(True, "NAVIGATE_STRUCTURE_ONLY_RELEVANCE_UNVERIFIED", tuple(cites))
