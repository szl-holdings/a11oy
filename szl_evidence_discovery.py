# SPDX-License-Identifier: Apache-2.0
"""Read-only proof-to-discovery projections over the existing Canonical Evidence Graph.

This module owns no evidence, execution, training, approval or publication state.
An edge hash is not a signature; an observer's VERIFIED label is not an
independent attestation. Numeric experiment assumptions remain MODELED.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from szl_evidence_graph import openlineage_job_event, sha256_hex

SCHEMA = "szl.evidence-discovery/v1"
VALUE_SCHEMA = "szl.evidence-discovery-binary-evsi/v1"
GATES = ("TRAINING", "ARTIFACT_VERIFIED", "EVALUATED", "DEPLOYED", "QUALIFIED")
SUBJECT_KINDS = frozenset({"training", "evaluation", "model"})
MAX_TARGETS = 32
MAX_EXPERIMENTS = 32
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")


def _seal(body: dict[str, Any]) -> dict[str, Any]:
    return {**body, "digest_sha256": sha256_hex(body)}


def _hold(graph: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return _seal({
        "schema": SCHEMA,
        "state": "UNAVAILABLE",
        "reason": reason,
        "graph_digest_sha256": graph["digest_sha256"],
        "observed_at": graph["observed_at"],
        "candidates": [],
        "candidate_count": 0,
        "coverage_complete": False,
        "authority": {"execute": False, "promote": False, "publish": False},
        "source_claims_authenticated": False,
    })


def discovery_gaps(graph: Mapping[str, Any], *, max_targets: int = MAX_TARGETS) -> dict[str, Any]:
    """Find unqualified subjects in one validated, complete CEG *view*.

    Completeness here covers only the supplied snapshot, never an entire
    provider or estate. No existing CEG verdict independently proves quality.
    No candidate is an executable instruction.
    """
    if type(max_targets) is not int or not 1 <= max_targets <= MAX_TARGETS:
        raise ValueError("invalid discovery target limit")
    # Reuse the canonical graph's strict edge-ID, ordering, digest and schema
    # verification. JobEvent construction neither emits nor writes an event.
    openlineage_job_event(graph)
    rows = graph["edges"]
    ids = {row["receipt_id"] for row in rows}
    unresolved = {p for row in rows for p in row["parents"] if p not in ids}
    if (graph.get("dangling_parent_count") != len(unresolved)
            or graph.get("bounded") or unresolved):
        return _hold(graph, "GRAPH_COVERAGE_OR_PARENT_UNAVAILABLE")

    targets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in rows:
        subject = edge["subject"]
        kind, name = subject["kind"], subject["id"]
        if kind not in SUBJECT_KINDS:
            continue
        # Never echo unconstrained private identity or user-provided content.
        if not _SAFE_ID.fullmatch(name) or "private" in name.lower():
            return _hold(graph, "UNSAFE_SUBJECT_IDENTIFIER")
        targets.setdefault((kind, name), []).append(edge)

    if len(targets) > max_targets:
        return _hold(graph, "DISCOVERY_CANDIDATE_CAP")
    if not targets:
        return _hold(graph, "NO_TRAINING_OR_EVALUATION_EVIDENCE")

    candidates = []
    for (kind, name), evidence in sorted(targets.items()):
        sources = sorted({e["source_revision"] for e in evidence
                          if e["source_revision"] is not None})
        declared_pinned_source = len(sources) == 1 and _REVISION.fullmatch(sources[0]) is not None
        # A declaration is not an independently checked source/base/data binding.
        candidates.append({
            "subject": {"kind": kind, "id": name},
            "evidence_edge_ids": sorted(e["receipt_id"] for e in evidence),
            "declared_source_revision": sources[0] if declared_pinned_source else None,
            "conflicting_source_declarations": len(sources) > 1,
            "declared_artifact_digests": sorted({
                e["artifact_sha256"] for e in evidence if e["artifact_sha256"]
            }),
            "qualification": "UNQUALIFIED",
            "gate_status": {gate: "UNVERIFIED" for gate in GATES},
            "next_evidence_requirement": "INDEPENDENT_SOURCE_MODEL_DATASET_CONFIG_BINDING",
            "subsequent_requirements": [
                "TERMINAL_ARTIFACT_BYTES_AND_INDEPENDENT_BACKUP",
                "VERSION_BOUND_HELDOUT_EVALUATION_AND_CONTAMINATION",
                "AUTH_ISOLATION_SLO_AND_ROLLBACK",
                "SIGNED_WITNESS_AND_OWNER_APPROVAL",
            ],
            "experiment_authorized": False,
            "freshness_verified": False,
            "independent_signature_verified": False,
        })

    return _seal({
        "schema": SCHEMA,
        "state": "GAPS_OBSERVED",
        "reason": "UNAUTHENTICATED_OBSERVER_EDGES_CANNOT_QUALIFY_MODELS",
        "graph_digest_sha256": graph["digest_sha256"],
        "observed_at": graph["observed_at"],
        "scope": "SUPPLIED_COMPLETE_SNAPSHOT_ONLY",
        "coverage_complete": True,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "authority": {"execute": False, "promote": False, "publish": False},
        "source_claims_authenticated": False,
    })


def _keys(value: Any, expected: set[str], code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError(code)
    return value


def _number(value: Any, code: str, *, minimum: float = -1_000_000,
            maximum: float = 1_000_000) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(code)
    return float(value)


def _identifier(value: Any, code: str) -> str:
    if type(value) is not str or not _SAFE_ID.fullmatch(value):
        raise ValueError(code)
    return value


def binary_evsi(decision: Mapping[str, Any],
                experiments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compute finite binary-decision EVSI from *explicit modeled assumptions*.

    All monetary utilities, experiment cost and expected risk loss are USD.
    A positive forecast is never approval to run an experiment or release a
    model. Missing probabilities and identifiers must be supplied by a reviewed
    planning process, never guessed from an inference response.
    """
    spec = _keys(decision, {
        "decision_id", "binding", "prior_pass", "utility_usd",
    }, "INVALID_DECISION_SPEC")
    decision_id = _identifier(spec["decision_id"], "INVALID_DECISION_ID")
    binding = _keys(spec["binding"], {
        "model_sha256", "dataset_sha256", "harness_sha256",
    }, "MISSING_IMMUTABLE_BINDING")
    for key, value in binding.items():
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            raise ValueError("MISSING_IMMUTABLE_BINDING")
    prior = _number(spec["prior_pass"], "INVALID_PRIOR", minimum=0, maximum=1)
    utility = _keys(spec["utility_usd"], {"release", "hold"}, "INVALID_UTILITY")
    u = {}
    for action in ("release", "hold"):
        pair = _keys(utility[action], {"pass", "fail"}, "INVALID_UTILITY")
        u[action] = {key: _number(pair[key], "INVALID_UTILITY") for key in ("pass", "fail")}
    if not isinstance(experiments, (list, tuple)) or not 1 <= len(experiments) <= MAX_EXPERIMENTS:
        raise ValueError("EXPERIMENT_COUNT_OUT_OF_BOUNDS")

    def preferred(joint_pass: float, joint_fail: float) -> float:
        return max(joint_pass * u[action]["pass"] + joint_fail * u[action]["fail"]
                   for action in ("release", "hold"))

    before = preferred(prior, 1 - prior)
    seen: set[str] = set()
    ranked = []
    for item in experiments:
        e = _keys(item, {
            "experiment_id", "sensitivity", "specificity", "cost_usd",
            "risk_expected_loss_usd",
        }, "INVALID_EXPERIMENT")
        experiment_id = _identifier(e["experiment_id"], "INVALID_EXPERIMENT_ID")
        if experiment_id in seen:
            raise ValueError("DUPLICATE_EXPERIMENT_ID")
        seen.add(experiment_id)
        sens = _number(e["sensitivity"], "INVALID_LIKELIHOOD", minimum=0, maximum=1)
        spec = _number(e["specificity"], "INVALID_LIKELIHOOD", minimum=0, maximum=1)
        cost = _number(e["cost_usd"], "INVALID_COST", minimum=0)
        risk = _number(e["risk_expected_loss_usd"], "INVALID_RISK", minimum=0)
        # Unnormalized joint probabilities avoid division by a zero-probability
        # test outcome and correctly value both positive and negative results.
        after = (
            preferred(prior * sens, (1 - prior) * (1 - spec))
            + preferred(prior * (1 - sens), (1 - prior) * spec)
        )
        gain = after - before
        if gain < -1e-8:
            raise ValueError("NEGATIVE_VALUE_OF_INFORMATION")
        gain = max(0.0, gain)
        ranked.append({
            "experiment_id": experiment_id,
            "evsi_usd": gain,
            "cost_usd": cost,
            "risk_expected_loss_usd": risk,
            "modeled_net_value_usd": gain - cost - risk,
            "measurement_class": "MODELED",
            "execution_authorized": False,
        })
    ranked.sort(key=lambda item: (-item["modeled_net_value_usd"], item["experiment_id"]))
    top = ranked[0]
    return _seal({
        "schema": VALUE_SCHEMA,
        "decision_id": decision_id,
        "binding": dict(binding),
        "state": "MODELED",
        "assumptions_independently_verified": False,
        "best_without_test_usd": before,
        "ranked": ranked,
        "candidate_count": len(ranked),
        "analytical_priority_only": top["experiment_id"] if top["modeled_net_value_usd"] > 0 else None,
        "reason": "MODELED_POSITIVE_NET_VALUE" if top["modeled_net_value_usd"] > 0
                  else "NO_POSITIVE_MODELED_NET_VALUE",
        "authority": {"execute": False, "promote": False, "publish": False},
    })
