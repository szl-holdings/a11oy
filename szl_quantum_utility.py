# SPDX-License-Identifier: Apache-2.0
"""Bounded, proof-carrying quantum workflow utility proposals.

This clean-room module is deliberately smaller than a quantum SDK.  It accepts
typed QUBO and Hamiltonian descriptions, produces deterministic *proposals*,
and makes unsupported advantage language fail closed.  It performs no network,
filesystem, subprocess, provider, simulator, QPU, credential, or deployment
operation.  ``effectors`` and ``provider_calls`` are always zero.

The finance ``szl_gpu_quant`` engine is a separate system and is not imported.
The repository's ``szl_vqc`` state-vector demonstration remains a small
``MODELED`` / ``SIMULATED`` capability; it is described by the manifest but is
not treated as hardware evidence or an advantage baseline.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "szl.quantum-utility.v1"
RECEIPT_SCHEMA_VERSION = "szl.quantum-utility.receipt.v1"
MODE = "PROPOSAL_ONLY"
EFFECTORS = 0
PROVIDER_CALLS = 0
MAX_QUBO_VARIABLES = 16
MAX_EXACT_STATES = 1 << MAX_QUBO_VARIABLES
MAX_EXACT_RUNTIME_MS = 2_000
MAX_HAMILTONIAN_QUBITS = 128
MAX_HAMILTONIAN_TERMS = 2_048
MIN_SHOTS = 1
MAX_SHOTS = 1_000_000
MIN_REPEATED_MEASUREMENTS = 3
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """Raised when an input cannot be represented by the bounded contract."""


class EvidenceLabel(str, Enum):
    DECLARED = "DECLARED"
    MEASURED = "MEASURED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class QUBOTerm:
    left: str
    right: str
    coefficient: float


@dataclass(frozen=True)
class QUBOProblem:
    problem_id: str
    variables: tuple[str, ...]
    offset: float
    linear: tuple[tuple[str, float], ...]
    quadratic: tuple[QUBOTerm, ...]


@dataclass(frozen=True)
class HamiltonianTerm:
    term_id: str
    pauli: str
    coefficient: float
    declared_priority: float


@dataclass(frozen=True)
class HamiltonianProblem:
    problem_id: str
    qubit_count: int
    terms: tuple[HamiltonianTerm, ...]


UTILITY_FIELDS = (
    "bounded_value_usd",
    "compute_cost_usd",
    "queue_cost_usd",
    "energy_cost_usd",
    "verification_cost_usd",
    "operational_risk_cost_usd",
    "estimated_accuracy",
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be an object")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a non-empty string")
    return value.strip()


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be a finite number")
    out = float(value)
    if not math.isfinite(out):
        raise ContractError(f"{name} must be a finite number")
    return out


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ContractError(f"{name} must be between {minimum} and {maximum}")
    return value


def _digest(value: Any, name: str) -> str:
    text = _text(value, name).lower()
    if not _SHA256_RE.fullmatch(text):
        raise ContractError(f"{name} must be a lowercase SHA-256 digest")
    return text


def _strict_keys(value: Mapping[str, Any], allowed: set[str], name: str) -> None:
    extras = sorted(set(value) - allowed)
    if extras:
        raise ContractError(f"{name} has unsupported fields: {', '.join(extras)}")


def parse_qubo(payload: Mapping[str, Any]) -> QUBOProblem:
    obj = _mapping(payload, "QUBO")
    _strict_keys(obj, {"kind", "problem_id", "variables", "offset", "linear", "quadratic"}, "QUBO")
    if obj.get("kind") != "QUBO":
        raise ContractError("kind must be QUBO")
    raw_variables = obj.get("variables")
    if not isinstance(raw_variables, Sequence) or isinstance(raw_variables, (str, bytes)):
        raise ContractError("variables must be an array")
    variables = tuple(_text(v, "variable") for v in raw_variables)
    if not variables or len(variables) > MAX_QUBO_VARIABLES:
        raise ContractError(f"QUBO must contain 1..{MAX_QUBO_VARIABLES} variables")
    if len(set(variables)) != len(variables):
        raise ContractError("variables must be unique")
    allowed_variables = set(variables)

    raw_linear = obj.get("linear", {})
    if not isinstance(raw_linear, Mapping):
        raise ContractError("linear must be an object")
    unknown_linear = sorted(set(raw_linear) - allowed_variables)
    if unknown_linear:
        raise ContractError(f"linear references unknown variables: {', '.join(unknown_linear)}")
    linear = tuple(sorted((str(k), _number(v, f"linear.{k}")) for k, v in raw_linear.items()))

    raw_quadratic = obj.get("quadratic", [])
    if not isinstance(raw_quadratic, Sequence) or isinstance(raw_quadratic, (str, bytes)):
        raise ContractError("quadratic must be an array")
    terms: list[QUBOTerm] = []
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(raw_quadratic):
        term = _mapping(raw, f"quadratic[{index}]")
        _strict_keys(term, {"left", "right", "coefficient"}, f"quadratic[{index}]")
        left = _text(term.get("left"), f"quadratic[{index}].left")
        right = _text(term.get("right"), f"quadratic[{index}].right")
        if left not in allowed_variables or right not in allowed_variables:
            raise ContractError(f"quadratic[{index}] references an unknown variable")
        if left == right:
            raise ContractError("diagonal QUBO terms belong in linear")
        pair = tuple(sorted((left, right)))
        if pair in seen:
            raise ContractError(f"duplicate quadratic pair: {pair[0]},{pair[1]}")
        seen.add(pair)
        terms.append(QUBOTerm(pair[0], pair[1], _number(term.get("coefficient"), "coefficient")))
    terms.sort(key=lambda row: (row.left, row.right))
    return QUBOProblem(
        problem_id=_text(obj.get("problem_id"), "problem_id"),
        variables=variables,
        offset=_number(obj.get("offset", 0.0), "offset"),
        linear=linear,
        quadratic=tuple(terms),
    )


def solve_qubo_exact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Enumerate a small binary QUBO exactly, with hard state/time ceilings."""

    problem = parse_qubo(payload)
    max_runtime_ms = MAX_EXACT_RUNTIME_MS
    deadline = time.perf_counter() + max_runtime_ms / 1_000.0
    linear = dict(problem.linear)
    best_energy: float | None = None
    best_bits: tuple[int, ...] | None = None
    state_count = 1 << len(problem.variables)
    if state_count > MAX_EXACT_STATES:
        raise ContractError("exact QUBO state ceiling exceeded")

    for state in range(state_count):
        if state % 1_024 == 0 and time.perf_counter() > deadline:
            raise ContractError("exact QUBO time limit exceeded; no partial baseline emitted")
        bits = tuple((state >> index) & 1 for index in range(len(problem.variables)))
        assignment = dict(zip(problem.variables, bits))
        energy = problem.offset
        energy += sum(linear.get(name, 0.0) * assignment[name] for name in problem.variables)
        energy += sum(term.coefficient * assignment[term.left] * assignment[term.right] for term in problem.quadratic)
        if best_energy is None or energy < best_energy or (energy == best_energy and bits < best_bits):
            best_energy = energy
            best_bits = bits

    assert best_energy is not None and best_bits is not None
    return {
        "problem_id": problem.problem_id,
        "problem_digest": sha256_json(asdict(problem)),
        "solver": "EXACT_BINARY_ENUMERATION",
        "evidence_label": EvidenceLabel.MEASURED.value,
        "measurement_scope": "deterministic classical computation",
        "complete": True,
        "variable_count": len(problem.variables),
        "states_evaluated": state_count,
        "objective": best_energy,
        "assignment": dict(zip(problem.variables, best_bits)),
        "max_runtime_ms": max_runtime_ms,
        "quantum_hardware_used": False,
        "quantum_advantage_claimed": False,
        "mode": MODE,
        "effectors": EFFECTORS,
    }


def exact_baseline(request: Mapping[str, Any]) -> dict[str, Any]:
    obj = _mapping(request, "exact baseline request")
    _strict_keys(obj, {"problem", "max_runtime_ms"}, "exact baseline request")
    problem_payload = dict(_mapping(obj.get("problem"), "problem"))
    limit = _integer(obj.get("max_runtime_ms", MAX_EXACT_RUNTIME_MS), "max_runtime_ms", 1, MAX_EXACT_RUNTIME_MS)
    problem = parse_qubo(problem_payload)
    # Avoid widening the typed QUBO schema merely to carry an execution bound.
    deadline = time.perf_counter() + limit / 1_000.0
    linear = dict(problem.linear)
    best: tuple[float, tuple[int, ...]] | None = None
    state_count = 1 << len(problem.variables)
    for state in range(state_count):
        if state % 1_024 == 0 and time.perf_counter() > deadline:
            raise ContractError("exact QUBO time limit exceeded; no partial baseline emitted")
        bits = tuple((state >> index) & 1 for index in range(len(problem.variables)))
        assignment = dict(zip(problem.variables, bits))
        energy = problem.offset
        energy += sum(linear.get(name, 0.0) * assignment[name] for name in problem.variables)
        energy += sum(t.coefficient * assignment[t.left] * assignment[t.right] for t in problem.quadratic)
        candidate = (energy, bits)
        if best is None or candidate < best:
            best = candidate
    assert best is not None
    return {
        "problem_id": problem.problem_id,
        "problem_digest": sha256_json(asdict(problem)),
        "solver": "EXACT_BINARY_ENUMERATION",
        "evidence_label": EvidenceLabel.MEASURED.value,
        "measurement_scope": "deterministic classical computation",
        "complete": True,
        "variable_count": len(problem.variables),
        "states_evaluated": state_count,
        "objective": best[0],
        "assignment": dict(zip(problem.variables, best[1])),
        "max_runtime_ms": limit,
        "quantum_hardware_used": False,
        "quantum_advantage_claimed": False,
        "mode": MODE,
        "effectors": EFFECTORS,
    }


def parse_hamiltonian(payload: Mapping[str, Any]) -> HamiltonianProblem:
    obj = _mapping(payload, "Hamiltonian")
    _strict_keys(obj, {"kind", "problem_id", "qubit_count", "terms"}, "Hamiltonian")
    if obj.get("kind") != "HAMILTONIAN":
        raise ContractError("kind must be HAMILTONIAN")
    qubit_count = _integer(obj.get("qubit_count"), "qubit_count", 1, MAX_HAMILTONIAN_QUBITS)
    raw_terms = obj.get("terms")
    if not isinstance(raw_terms, Sequence) or isinstance(raw_terms, (str, bytes)):
        raise ContractError("terms must be an array")
    if not 1 <= len(raw_terms) <= MAX_HAMILTONIAN_TERMS:
        raise ContractError(f"terms must contain 1..{MAX_HAMILTONIAN_TERMS} rows")
    terms: list[HamiltonianTerm] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_terms):
        row = _mapping(raw, f"terms[{index}]")
        _strict_keys(row, {"term_id", "pauli", "coefficient", "declared_priority"}, f"terms[{index}]")
        term_id = _text(row.get("term_id"), "term_id")
        if term_id in seen:
            raise ContractError(f"duplicate term_id: {term_id}")
        seen.add(term_id)
        pauli = _text(row.get("pauli"), "pauli").upper()
        if len(pauli) != qubit_count or any(symbol not in "IXYZ" for symbol in pauli):
            raise ContractError("pauli must contain exactly qubit_count symbols from I,X,Y,Z")
        priority = _number(row.get("declared_priority", 1.0), "declared_priority")
        if priority < 0:
            raise ContractError("declared_priority must be non-negative")
        terms.append(HamiltonianTerm(term_id, pauli, _number(row.get("coefficient"), "coefficient"), priority))
    terms.sort(key=lambda row: row.term_id)
    return HamiltonianProblem(_text(obj.get("problem_id"), "problem_id"), qubit_count, tuple(terms))


def allocate_hamiltonian_shots(request: Mapping[str, Any]) -> dict[str, Any]:
    obj = _mapping(request, "Hamiltonian shot request")
    _strict_keys(obj, {"hamiltonian", "shot_budget"}, "Hamiltonian shot request")
    problem = parse_hamiltonian(_mapping(obj.get("hamiltonian"), "hamiltonian"))
    budget = _integer(obj.get("shot_budget"), "shot_budget", MIN_SHOTS, MAX_SHOTS)
    if budget < len(problem.terms):
        raise ContractError("shot_budget must allocate at least one shot per term")

    weights = []
    for term in problem.terms:
        locality = sum(symbol != "I" for symbol in term.pauli)
        weights.append(abs(term.coefficient) * max(1, locality) * term.declared_priority)
    total_weight = sum(weights)
    if total_weight <= 0:
        weights = [1.0] * len(problem.terms)
        total_weight = float(len(weights))

    remaining = budget - len(problem.terms)
    exact_extra = [remaining * weight / total_weight for weight in weights]
    floors = [int(math.floor(value)) for value in exact_extra]
    leftover = remaining - sum(floors)
    order = sorted(range(len(problem.terms)), key=lambda i: (-(exact_extra[i] - floors[i]), problem.terms[i].term_id))
    extras = list(floors)
    for index in order[:leftover]:
        extras[index] += 1

    allocations = []
    for index, term in enumerate(problem.terms):
        allocations.append({
            "term_id": term.term_id,
            "pauli": term.pauli,
            "coefficient": term.coefficient,
            "declared_priority": term.declared_priority,
            "importance": weights[index],
            "shots": 1 + extras[index],
        })
    return {
        "problem_id": problem.problem_id,
        "problem_digest": sha256_json(asdict(problem)),
        "shot_budget": budget,
        "shots_allocated": sum(row["shots"] for row in allocations),
        "allocation": allocations,
        "method": "DECLARED_ABS_COEFFICIENT_X_LOCALITY_X_PRIORITY_LARGEST_REMAINDER",
        "method_evidence_label": EvidenceLabel.DECLARED.value,
        "scientific_optimality_claimed": False,
        "execution_performed": False,
        "provider_calls": PROVIDER_CALLS,
        "mode": MODE,
        "effectors": EFFECTORS,
    }


def _evidence_datum(value: Any, name: str, expected_unit: str) -> dict[str, Any]:
    obj = _mapping(value, name)
    _strict_keys(obj, {"value", "label", "unit", "source_ref"}, name)
    try:
        label = EvidenceLabel(_text(obj.get("label"), f"{name}.label"))
    except ValueError as exc:
        raise ContractError(f"{name}.label must be DECLARED, MEASURED, or UNKNOWN") from exc
    unit = _text(obj.get("unit"), f"{name}.unit")
    if unit != expected_unit:
        raise ContractError(f"{name}.unit must be {expected_unit}")
    source_ref = _text(obj.get("source_ref"), f"{name}.source_ref")
    raw = obj.get("value")
    if label is EvidenceLabel.UNKNOWN:
        if raw is not None:
            raise ContractError(f"{name}.value must be null when label is UNKNOWN")
        numeric = None
    else:
        numeric = _number(raw, f"{name}.value")
        if numeric < 0:
            raise ContractError(f"{name}.value must be non-negative")
    return {"value": numeric, "label": label.value, "unit": unit, "source_ref": source_ref}


def score_counterfactuals(request: Mapping[str, Any]) -> dict[str, Any]:
    obj = _mapping(request, "counterfactual request")
    _strict_keys(obj, {"workload_digest", "candidates"}, "counterfactual request")
    workload_digest = _digest(obj.get("workload_digest"), "workload_digest")
    raw_candidates = obj.get("candidates")
    if not isinstance(raw_candidates, Sequence) or isinstance(raw_candidates, (str, bytes)):
        raise ContractError("candidates must be an array")
    if not 1 <= len(raw_candidates) <= 64:
        raise ContractError("candidates must contain 1..64 rows")
    seen: set[str] = set()
    scored: list[dict[str, Any]] = []
    expected_units = {name: ("ratio" if name == "estimated_accuracy" else "USD") for name in UTILITY_FIELDS}
    for index, raw in enumerate(raw_candidates):
        candidate = _mapping(raw, f"candidates[{index}]")
        _strict_keys(candidate, {"candidate_id", "backend_id", "compile_plan_id", "inputs"}, f"candidates[{index}]")
        candidate_id = _text(candidate.get("candidate_id"), "candidate_id")
        if candidate_id in seen:
            raise ContractError(f"duplicate candidate_id: {candidate_id}")
        seen.add(candidate_id)
        inputs = _mapping(candidate.get("inputs"), "inputs")
        if set(inputs) != set(UTILITY_FIELDS):
            raise ContractError("inputs must contain every utility field exactly once")
        evidence = {name: _evidence_datum(inputs[name], name, expected_units[name]) for name in UTILITY_FIELDS}
        accuracy = evidence["estimated_accuracy"]["value"]
        if accuracy is not None and accuracy > 1:
            raise ContractError("estimated_accuracy.value must be between 0 and 1")
        labels = {row["label"] for row in evidence.values()}
        unknown = sorted(name for name, row in evidence.items() if row["label"] == EvidenceLabel.UNKNOWN.value)
        if unknown:
            margin = None
            score_label = EvidenceLabel.UNKNOWN.value
            disposition = "UNKNOWN_INPUTS"
        else:
            margin = evidence["bounded_value_usd"]["value"] - sum(
                evidence[name]["value"] for name in UTILITY_FIELDS
                if name.endswith("_cost_usd") or name == "operational_risk_cost_usd"
            )
            score_label = EvidenceLabel.MEASURED.value if labels == {EvidenceLabel.MEASURED.value} else EvidenceLabel.DECLARED.value
            disposition = "POSITIVE_MARGIN" if margin > 0 else "NON_POSITIVE_MARGIN"
        scored.append({
            "candidate_id": candidate_id,
            "backend_id": _text(candidate.get("backend_id"), "backend_id"),
            "compile_plan_id": _text(candidate.get("compile_plan_id"), "compile_plan_id"),
            "inputs": evidence,
            "unknown_inputs": unknown,
            "utility_margin_usd": margin,
            "score_evidence_label": score_label,
            "disposition": disposition,
        })

    comparable = [row for row in scored if row["utility_margin_usd"] is not None]
    front: list[str] = []
    for row in comparable:
        dominated = False
        for other in comparable:
            if other is row:
                continue
            row_accuracy = row["inputs"]["estimated_accuracy"]["value"]
            other_accuracy = other["inputs"]["estimated_accuracy"]["value"]
            if (
                other["utility_margin_usd"] >= row["utility_margin_usd"]
                and other_accuracy >= row_accuracy
                and (other["utility_margin_usd"] > row["utility_margin_usd"] or other_accuracy > row_accuracy)
            ):
                dominated = True
                break
        if not dominated:
            front.append(row["candidate_id"])
    return {
        "workload_digest": workload_digest,
        "candidates": sorted(scored, key=lambda row: row["candidate_id"]),
        "pareto_front_candidate_ids": sorted(front),
        "score_model": "DECLARED_VALUE_MINUS_TOTAL_DECLARED_OR_MEASURED_COST",
        "universal_provider_ranking_claimed": False,
        "execution_performed": False,
        "provider_calls": PROVIDER_CALLS,
        "mode": MODE,
        "effectors": EFFECTORS,
    }


def _receipt_body(operation: str, request: Mapping[str, Any], output: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "operation": operation,
        "mode": MODE,
        "effectors": EFFECTORS,
        "provider_calls": PROVIDER_CALLS,
        "input": request,
        "input_sha256": sha256_json(request),
        "output": output,
        "output_sha256": sha256_json(output),
        "signature_state": "UNSIGNED_DETERMINISTIC_HASH_ONLY",
    }


def create_receipt(operation: str, request: Mapping[str, Any], output: Mapping[str, Any]) -> dict[str, Any]:
    body = _receipt_body(operation, request, output)
    return {**body, "receipt_sha256": sha256_json(body)}


def evaluate_advantage_claim(request: Mapping[str, Any]) -> dict[str, Any]:
    obj = _mapping(request, "advantage claim")
    allowed = {
        "claim_type", "claim_id", "claim_owner", "classical_baseline_receipt",
        "quantum_observations", "uncertainty", "provenance", "utility_margin",
    }
    _strict_keys(obj, allowed, "advantage claim")
    reasons: list[str] = []
    if obj.get("claim_type") != "QUANTUM_ADVANTAGE":
        reasons.append("QUG-001 claim_type must be QUANTUM_ADVANTAGE")
    try:
        _text(obj.get("claim_id"), "claim_id")
        _text(obj.get("claim_owner"), "claim_owner")
    except ContractError:
        reasons.append("QUG-002 claim_id and accountable claim_owner are required")

    baseline = obj.get("classical_baseline_receipt")
    baseline_input_digest: str | None = None
    try:
        baseline_obj = _mapping(baseline, "classical_baseline_receipt")
        if baseline_obj.get("operation") != "QUBO_EXACT_BASELINE":
            raise ContractError("baseline receipt must be QUBO_EXACT_BASELINE")
        baseline_check = replay_receipt(baseline_obj)
        baseline_output = _mapping(baseline_obj.get("output"), "baseline output")
        if (
            not baseline_check["valid"]
            or not baseline_output.get("complete")
            or baseline_output.get("evidence_label") != EvidenceLabel.MEASURED.value
        ):
            reasons.append("QUG-003 exact replayable classical baseline is required")
        else:
            baseline_input_digest = str(baseline_obj.get("input_sha256"))
    except (ContractError, TypeError, KeyError):
        reasons.append("QUG-003 exact replayable classical baseline is required")

    observations = obj.get("quantum_observations")
    observation_rows = observations if isinstance(observations, Sequence) and not isinstance(observations, (str, bytes)) else []
    if len(observation_rows) < MIN_REPEATED_MEASUREMENTS:
        reasons.append(f"QUG-004 at least {MIN_REPEATED_MEASUREMENTS} repeated measurements are required")
    else:
        run_ids: set[str] = set()
        for index, raw in enumerate(observation_rows):
            try:
                row = _mapping(raw, f"quantum_observations[{index}]")
                _strict_keys(row, {"run_id", "task_digest", "backend_id", "shots", "raw_result_sha256", "label"}, f"quantum_observations[{index}]")
                run_id = _text(row.get("run_id"), "run_id")
                if run_id in run_ids:
                    raise ContractError("run_id must be unique")
                run_ids.add(run_id)
                if row.get("label") != EvidenceLabel.MEASURED.value:
                    raise ContractError("observation label must be MEASURED")
                if baseline_input_digest is None or _digest(row.get("task_digest"), "task_digest") != baseline_input_digest:
                    raise ContractError("task digest must match the classical baseline")
                _text(row.get("backend_id"), "backend_id")
                _integer(row.get("shots"), "shots", 1, MAX_SHOTS)
                _digest(row.get("raw_result_sha256"), "raw_result_sha256")
            except ContractError:
                reasons.append(f"QUG-005 observation {index} is incomplete, incomparable, or not MEASURED")
                break

    margin_value: float | None = None
    try:
        margin = _evidence_datum(obj.get("utility_margin"), "utility_margin", "USD")
        margin_value = margin["value"]
        if margin["label"] != EvidenceLabel.MEASURED.value or margin_value is None or margin_value <= 0:
            reasons.append("QUG-006 a positive MEASURED utility margin is required")
    except ContractError:
        reasons.append("QUG-006 a positive MEASURED utility margin is required")

    try:
        uncertainty = _mapping(obj.get("uncertainty"), "uncertainty")
        _strict_keys(uncertainty, {"label", "method", "source_ref", "lower_margin_usd", "upper_margin_usd", "confidence"}, "uncertainty")
        lower = _number(uncertainty.get("lower_margin_usd"), "lower_margin_usd")
        upper = _number(uncertainty.get("upper_margin_usd"), "upper_margin_usd")
        confidence = _number(uncertainty.get("confidence"), "confidence")
        if (
            uncertainty.get("label") != EvidenceLabel.MEASURED.value
            or lower <= 0
            or upper < lower
            or not 0.5 <= confidence <= 1.0
            or margin_value is None
            or not lower <= margin_value <= upper
        ):
            raise ContractError("uncertainty interval does not support a positive margin")
        _text(uncertainty.get("method"), "uncertainty.method")
        _text(uncertainty.get("source_ref"), "uncertainty.source_ref")
    except ContractError:
        reasons.append("QUG-007 measured uncertainty with a positive lower margin bound is required")

    provenance = obj.get("provenance")
    provenance_rows = provenance if isinstance(provenance, Sequence) and not isinstance(provenance, (str, bytes)) else []
    if not provenance_rows:
        reasons.append("QUG-008 provenance is required")
    else:
        try:
            for index, raw in enumerate(provenance_rows):
                row = _mapping(raw, f"provenance[{index}]")
                _strict_keys(row, {"source_uri", "content_sha256", "observed_at"}, f"provenance[{index}]")
                _text(row.get("source_uri"), "source_uri")
                _digest(row.get("content_sha256"), "content_sha256")
                _text(row.get("observed_at"), "observed_at")
        except ContractError:
            reasons.append("QUG-008 complete provenance is required")

    unique_reasons = sorted(set(reasons))
    if any(reason.startswith("QUG-006") for reason in unique_reasons) and margin_value is not None and margin_value <= 0:
        evidence_state = "REFUTED"
    elif unique_reasons:
        evidence_state = "UNKNOWN"
    else:
        evidence_state = "SUPPORTED"
    passed = not unique_reasons
    return {
        "claim_id": obj.get("claim_id"),
        "claim_type": obj.get("claim_type"),
        "gate_passed": passed,
        "evidence_state": evidence_state,
        "reasons": unique_reasons,
        "eligible_for_human_review": passed,
        "quantum_advantage_verified": False,
        "claim_authorized": False,
        "publication_authorized": False,
        "execution_authorized": False,
        "note": "Passing this gate means evidence completeness for human review, not verified quantum advantage.",
        "mode": MODE,
        "effectors": EFFECTORS,
        "provider_calls": PROVIDER_CALLS,
    }


OPERATIONS = {
    "QUBO_EXACT_BASELINE": exact_baseline,
    "HAMILTONIAN_SHOT_PLAN": allocate_hamiltonian_shots,
    "COUNTERFACTUAL_SCORE": score_counterfactuals,
    "QUANTUM_ADVANTAGE_GATE": evaluate_advantage_claim,
}


def run_with_receipt(operation: str, request: Mapping[str, Any]) -> dict[str, Any]:
    if operation not in OPERATIONS:
        raise ContractError(f"unsupported operation: {operation}")
    normalized_request = dict(_mapping(request, "request"))
    output = OPERATIONS[operation](normalized_request)
    return {"result": output, "receipt": create_receipt(operation, normalized_request, output)}


def replay_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    obj = _mapping(receipt, "receipt")
    required = set(_receipt_body("x", {}, {})) | {"receipt_sha256"}
    if set(obj) != required:
        raise ContractError("receipt fields do not match the receipt schema")
    if obj.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise ContractError("unsupported receipt schema_version")
    if (
        obj.get("mode") != MODE
        or obj.get("effectors") != EFFECTORS
        or obj.get("provider_calls") != PROVIDER_CALLS
        or obj.get("signature_state") != "UNSIGNED_DETERMINISTIC_HASH_ONLY"
    ):
        raise ContractError("receipt violates the proposal-only boundary")
    operation = _text(obj.get("operation"), "operation")
    request = dict(_mapping(obj.get("input"), "receipt.input"))
    output = dict(_mapping(obj.get("output"), "receipt.output"))
    stored = _digest(obj.get("receipt_sha256"), "receipt_sha256")
    body = {key: obj[key] for key in obj if key != "receipt_sha256"}
    hash_valid = sha256_json(body) == stored
    input_valid = sha256_json(request) == obj.get("input_sha256")
    output_valid = sha256_json(output) == obj.get("output_sha256")
    if operation not in OPERATIONS:
        replay_output: Mapping[str, Any] = {}
        replay_equal = False
    elif operation == "QUANTUM_ADVANTAGE_GATE":
        # Advantage requests embed a baseline receipt. Replaying remains pure,
        # bounded, and recursive only by one validated baseline level.
        replay_output = OPERATIONS[operation](request)
        replay_equal = replay_output == output
    else:
        replay_output = OPERATIONS[operation](request)
        replay_equal = replay_output == output
    valid = bool(hash_valid and input_valid and output_valid and replay_equal)
    return {
        "valid": valid,
        "receipt_sha256": stored,
        "hash_valid": hash_valid,
        "input_digest_valid": input_valid,
        "output_digest_valid": output_valid,
        "replay_equal": replay_equal,
        "mode": MODE,
        "effectors": EFFECTORS,
        "provider_calls": PROVIDER_CALLS,
    }


def info() -> dict[str, Any]:
    return {
        "service": "szl-quantum-utility-gate",
        "schema_version": SCHEMA_VERSION,
        "ready": True,
        "label": "STRUCTURAL-ONLY",
        "label_detail": "Classical exact baselines may be MEASURED within their stated computation scope; no QPU measurement is made here.",
        "mode": MODE,
        "effectors": EFFECTORS,
        "provider_calls": PROVIDER_CALLS,
        "qpu_calls": 0,
        "finance_quant_engine_imported": False,
        "capabilities": {
            "qubo_exact_classical_baseline": {"label": "MEASURED", "max_variables": MAX_QUBO_VARIABLES},
            "hamiltonian_shot_allocation": {"label": "DECLARED", "max_terms": MAX_HAMILTONIAN_TERMS},
            "counterfactual_backend_compile_scoring": {"labels_required": [label.value for label in EvidenceLabel]},
            "quantum_advantage_rupture_gate": {"auto_verifies_advantage": False},
            "deterministic_receipt_replay": True,
        },
        "existing_simulator_boundary": {
            "module": "szl_vqc.py",
            "label": "MODELED",
            "sim_kind": "SIMULATED",
            "used_as_hardware_evidence": False,
            "used_as_advantage_evidence": False,
        },
        "non_goals": [
            "QPU or provider execution",
            "universal provider rankings",
            "quantum advantage verification",
            "finance portfolio analysis",
        ],
        "operations": sorted(OPERATIONS),
    }
