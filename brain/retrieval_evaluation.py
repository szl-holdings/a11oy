"""Bounded, fail-closed evaluation for Brain retrieval candidates.

The runner is deliberately offline and adapter-driven.  It does not load a
model, touch the serving Brain, train a GPU, or promote an artifact.  It reads
provenance-admitted held-out cases, evaluates four comparable retrieval runs,
and reports whether the *dataset gate* is eligible for a later promotion
decision.  A fixture adapter is included so recorded BGE and Qwen outputs can
be evaluated without presenting fixture execution as live model inference.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Protocol, Sequence


CASE_SCHEMA = "szl.brain-retrieval-case/v1"
SPLIT_SCHEMA = "szl.brain-source-group-split/v1"
FIXTURE_SCHEMA = "szl.brain-retrieval-fixture/v1"
REPORT_SCHEMA = "szl.brain-retrieval-evaluation/v1"
MIN_PROMOTION_QUERIES = 200
REQUIRED_SYSTEMS = (
    "BGE_BASE",
    "BGE_RERANKED",
    "QWEN_BASE",
    "QWEN_RERANKED",
)
MAX_CASES = 10_000
MAX_LINE_BYTES = 1_048_576
MAX_QUERY_CHARS = 4_096
MAX_CANDIDATES = 2_000
MAX_RELEVANT = 100
MAX_RETURNED = 100
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


class EvaluationRefused(ValueError):
    """Raised before a report can be treated as an evaluation receipt."""


@dataclass(frozen=True)
class RetrievalCase:
    query_id: str
    query: str
    source_group: str
    candidate_node_ids: tuple[str, ...]
    relevant_node_ids: tuple[str, ...]
    exact_node_id: str | None
    should_abstain: bool


@dataclass(frozen=True)
class RetrievalPrediction:
    node_ids: tuple[str, ...]
    abstained: bool = False


class RetrievalAdapter(Protocol):
    """Minimal boundary implemented by a live runner or a recorded fixture."""

    system_id: str
    evidence: Mapping[str, Any]

    def retrieve(self, case: RetrievalCase, *, limit: int) -> RetrievalPrediction:
        """Return at most ``limit`` candidate IDs for exactly one held-out case."""


class FixtureAdapter:
    """Adapter over immutable recorded predictions.

    ``mode=FIXTURE`` is retained in the report so these results cannot be
    confused with a model loaded or served during the evaluation process.
    """

    def __init__(
        self,
        system_id: str,
        predictions: Mapping[str, RetrievalPrediction],
        *,
        fixture_sha256: str,
        corpus_sha256: str,
        model_id: str,
        model_revision: str,
        artifact_sha256: str,
        code_revision: str,
    ) -> None:
        self.system_id = system_id
        self._predictions = dict(predictions)
        self.evidence = {
            "mode": "FIXTURE",
            "fixture_sha256": _require_sha256(
                fixture_sha256, f"{system_id}.fixture_sha256"
            ),
            "corpus_sha256": _require_sha256(
                corpus_sha256, f"{system_id}.corpus_sha256"
            ),
            "model_id": _require_text(model_id, f"{system_id}.model_id"),
            "model_revision": _require_text(
                model_revision, f"{system_id}.model_revision"
            ),
            "artifact_sha256": _require_sha256(
                artifact_sha256, f"{system_id}.artifact_sha256"
            ),
            "code_revision": _require_text(
                code_revision, f"{system_id}.code_revision"
            ),
            "model_execution": "NOT_PERFORMED_BY_EVALUATOR",
        }

    def retrieve(self, case: RetrievalCase, *, limit: int) -> RetrievalPrediction:
        try:
            prediction = self._predictions[case.query_id]
        except KeyError as exc:
            raise EvaluationRefused(
                f"{self.system_id}: missing prediction for {case.query_id}"
            ) from exc
        if len(prediction.node_ids) > limit:
            raise EvaluationRefused(
                f"{self.system_id}/{case.query_id}: returned {len(prediction.node_ids)} "
                f"IDs above the bounded limit {limit}"
            )
        return prediction


def _require_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationRefused(f"{path}: non-empty string required")
    return value.strip()


def _require_sha256(value: Any, path: str) -> str:
    text = _require_text(value, path)
    if not _SHA256.fullmatch(text):
        raise EvaluationRefused(f"{path}: exact sha256 hex required")
    return text.lower()


def _require_string_list(value: Any, path: str, *, maximum: int) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise EvaluationRefused(f"{path}: non-empty list required")
    if len(value) > maximum:
        raise EvaluationRefused(f"{path}: exceeds bounded maximum {maximum}")
    items = tuple(_require_text(item, f"{path}[]") for item in value)
    if len(items) != len(set(items)):
        raise EvaluationRefused(f"{path}: duplicate IDs are not allowed")
    return items


def _validate_rights(raw: Any, query_id: str) -> None:
    if not isinstance(raw, dict):
        raise EvaluationRefused(f"{query_id}.rights: object required")
    if raw.get("status") != "ADMITTED":
        raise EvaluationRefused(f"{query_id}.rights.status: ADMITTED required")
    license_id = _require_text(raw.get("license"), f"{query_id}.rights.license")
    if license_id.upper() in {"UNKNOWN", "UNVERIFIED", "NONE"}:
        raise EvaluationRefused(f"{query_id}.rights.license: unresolved rights")
    scopes = raw.get("permission_scope")
    if not isinstance(scopes, list) or "retrieval_evaluation" not in scopes:
        raise EvaluationRefused(
            f"{query_id}.rights.permission_scope: retrieval_evaluation required"
        )
    _require_text(raw.get("evidence_ref"), f"{query_id}.rights.evidence_ref")
    _require_sha256(raw.get("evidence_sha256"), f"{query_id}.rights.evidence_sha256")


def _validate_provenance(raw: Any, query_id: str) -> None:
    if not isinstance(raw, dict):
        raise EvaluationRefused(f"{query_id}.provenance: object required")
    if raw.get("status") != "ADMITTED":
        raise EvaluationRefused(f"{query_id}.provenance.status: ADMITTED required")
    _require_text(raw.get("source_uri"), f"{query_id}.provenance.source_uri")
    _require_text(raw.get("source_revision"), f"{query_id}.provenance.source_revision")
    _require_sha256(raw.get("content_sha256"), f"{query_id}.provenance.content_sha256")
    _require_text(
        raw.get("admission_receipt_id"),
        f"{query_id}.provenance.admission_receipt_id",
    )


def _validate_authorship(raw: Any, query_id: str) -> None:
    if not isinstance(raw, dict):
        raise EvaluationRefused(f"{query_id}.authorship: object required")
    if raw.get("kind") != "HUMAN":
        raise EvaluationRefused(f"{query_id}.authorship.kind: HUMAN required")
    _require_text(raw.get("author_id"), f"{query_id}.authorship.author_id")
    _require_text(raw.get("attestation_id"), f"{query_id}.authorship.attestation_id")


def _parse_case(raw: Any, line_number: int) -> RetrievalCase:
    if not isinstance(raw, dict):
        raise EvaluationRefused(f"line {line_number}: JSON object required")
    if raw.get("schema") != CASE_SCHEMA:
        raise EvaluationRefused(f"line {line_number}: schema {CASE_SCHEMA} required")
    query_id = _require_text(raw.get("query_id"), f"line {line_number}.query_id")
    query = _require_text(raw.get("query"), f"{query_id}.query")
    if len(query) > MAX_QUERY_CHARS:
        raise EvaluationRefused(f"{query_id}.query: exceeds {MAX_QUERY_CHARS} characters")
    _validate_authorship(raw.get("authorship"), query_id)
    _validate_rights(raw.get("rights"), query_id)
    _validate_provenance(raw.get("provenance"), query_id)

    split = raw.get("split")
    if not isinstance(split, dict):
        raise EvaluationRefused(f"{query_id}.split: object required")
    if split.get("partition") != "HELD_OUT":
        raise EvaluationRefused(f"{query_id}.split.partition: HELD_OUT required")
    source_group = _require_text(split.get("source_group"), f"{query_id}.split.source_group")

    candidates = _require_string_list(
        raw.get("candidate_node_ids"),
        f"{query_id}.candidate_node_ids",
        maximum=MAX_CANDIDATES,
    )
    relevant_raw = raw.get("relevant_node_ids")
    if not isinstance(relevant_raw, list):
        raise EvaluationRefused(f"{query_id}.relevant_node_ids: list required")
    if len(relevant_raw) > MAX_RELEVANT:
        raise EvaluationRefused(f"{query_id}.relevant_node_ids: exceeds {MAX_RELEVANT}")
    relevant = tuple(
        _require_text(item, f"{query_id}.relevant_node_ids[]") for item in relevant_raw
    )
    if len(relevant) != len(set(relevant)):
        raise EvaluationRefused(f"{query_id}.relevant_node_ids: duplicate IDs")
    if not set(relevant).issubset(candidates):
        raise EvaluationRefused(f"{query_id}: relevant IDs must be offered candidates")

    should_abstain = raw.get("should_abstain")
    if not isinstance(should_abstain, bool):
        raise EvaluationRefused(f"{query_id}.should_abstain: boolean required")
    exact_raw = raw.get("exact_node_id")
    exact_node_id = None if exact_raw is None else _require_text(exact_raw, f"{query_id}.exact_node_id")
    if should_abstain:
        if relevant or exact_node_id is not None:
            raise EvaluationRefused(
                f"{query_id}: abstention cases cannot declare relevant or exact IDs"
            )
    else:
        if not relevant:
            raise EvaluationRefused(f"{query_id}: answerable case requires relevant IDs")
        if exact_node_id is None or exact_node_id not in relevant:
            raise EvaluationRefused(
                f"{query_id}: exact_node_id must be one of the relevant IDs"
            )
    return RetrievalCase(
        query_id=query_id,
        query=query,
        source_group=source_group,
        candidate_node_ids=candidates,
        relevant_node_ids=relevant,
        exact_node_id=exact_node_id,
        should_abstain=should_abstain,
    )


def load_cases(path: str | Path) -> tuple[list[RetrievalCase], str]:
    """Read and validate a bounded provenance-admitted JSONL case file."""
    source = Path(path)
    digest = hashlib.sha256()
    cases: list[RetrievalCase] = []
    query_ids: set[str] = set()
    normalized_queries: set[str] = set()
    with source.open("rb") as handle:
        for line_number, line in enumerate(handle, 1):
            digest.update(line)
            if len(line) > MAX_LINE_BYTES:
                raise EvaluationRefused(f"line {line_number}: exceeds bounded byte limit")
            if not line.strip():
                continue
            if len(cases) >= MAX_CASES:
                raise EvaluationRefused(f"case file exceeds bounded maximum {MAX_CASES}")
            try:
                raw = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise EvaluationRefused(f"line {line_number}: invalid JSON") from exc
            case = _parse_case(raw, line_number)
            normalized = " ".join(case.query.casefold().split())
            if case.query_id in query_ids:
                raise EvaluationRefused(f"duplicate query_id: {case.query_id}")
            if normalized in normalized_queries:
                raise EvaluationRefused(
                    f"duplicate normalized query text at {case.query_id}; count inflation refused"
                )
            query_ids.add(case.query_id)
            normalized_queries.add(normalized)
            cases.append(case)
    if not cases:
        raise EvaluationRefused("case file is empty")
    if not any(case.should_abstain for case in cases):
        raise EvaluationRefused("held-out set requires at least one abstention case")
    if not any(not case.should_abstain for case in cases):
        raise EvaluationRefused("held-out set requires at least one answerable case")
    return cases, digest.hexdigest()


def load_split_manifest(path: str | Path) -> tuple[set[str], set[str], str]:
    """Load the independently declared source-group split and verify its receipt."""
    source = Path(path)
    payload = source.read_bytes()
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluationRefused("source-group split manifest is invalid JSON") from exc
    if not isinstance(raw, dict) or raw.get("schema") != SPLIT_SCHEMA:
        raise EvaluationRefused(f"source-group split schema {SPLIT_SCHEMA} required")
    train = set(
        _require_string_list(
            raw.get("training_source_groups"),
            "split.training_source_groups",
            maximum=MAX_CASES,
        )
    )
    held_out = set(
        _require_string_list(
            raw.get("held_out_source_groups"),
            "split.held_out_source_groups",
            maximum=MAX_CASES,
        )
    )
    overlap = sorted(train & held_out)
    if overlap:
        raise EvaluationRefused(
            "source-group leakage between training and held-out: " + ", ".join(overlap)
        )
    provenance = raw.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("status") != "ADMITTED":
        raise EvaluationRefused("split.provenance.status: ADMITTED required")
    _require_text(provenance.get("receipt_id"), "split.provenance.receipt_id")
    _require_sha256(provenance.get("content_sha256"), "split.provenance.content_sha256")
    return train, held_out, hashlib.sha256(payload).hexdigest()


def load_fixture_adapters(path: str | Path) -> dict[str, FixtureAdapter]:
    """Read recorded system outputs through the same adapter boundary as live runs."""
    source = Path(path)
    payload = source.read_bytes()
    fixture_digest = hashlib.sha256(payload).hexdigest()
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluationRefused("retrieval fixture is invalid JSON") from exc
    if not isinstance(raw, dict) or raw.get("schema") != FIXTURE_SCHEMA:
        raise EvaluationRefused(f"retrieval fixture schema {FIXTURE_SCHEMA} required")
    corpus_sha256 = _require_sha256(raw.get("corpus_sha256"), "fixture.corpus_sha256")
    code_revision = _require_text(raw.get("code_revision"), "fixture.code_revision")
    systems = raw.get("systems")
    if not isinstance(systems, dict):
        raise EvaluationRefused("fixture.systems: object required")
    adapters: dict[str, FixtureAdapter] = {}
    for system_id in REQUIRED_SYSTEMS:
        system = systems.get(system_id)
        if not isinstance(system, dict):
            raise EvaluationRefused(f"fixture.systems.{system_id}: object required")
        system_rows = system.get("predictions")
        if not isinstance(system_rows, dict):
            raise EvaluationRefused(
                f"fixture.systems.{system_id}.predictions: object required"
            )
        predictions: dict[str, RetrievalPrediction] = {}
        for query_id, value in system_rows.items():
            if not isinstance(value, dict):
                raise EvaluationRefused(f"{system_id}/{query_id}: prediction object required")
            node_ids_raw = value.get("node_ids")
            if not isinstance(node_ids_raw, list):
                raise EvaluationRefused(f"{system_id}/{query_id}.node_ids: list required")
            if len(node_ids_raw) > MAX_RETURNED:
                raise EvaluationRefused(f"{system_id}/{query_id}: exceeds {MAX_RETURNED} IDs")
            node_ids = tuple(_require_text(node, f"{system_id}/{query_id}.node_ids[]") for node in node_ids_raw)
            if len(node_ids) != len(set(node_ids)):
                raise EvaluationRefused(f"{system_id}/{query_id}: duplicate returned IDs")
            abstained = value.get("abstained", False)
            if not isinstance(abstained, bool):
                raise EvaluationRefused(f"{system_id}/{query_id}.abstained: boolean required")
            predictions[_require_text(query_id, f"{system_id}.query_id")] = RetrievalPrediction(
                node_ids=node_ids,
                abstained=abstained,
            )
        adapters[system_id] = FixtureAdapter(
            system_id,
            predictions,
            fixture_sha256=fixture_digest,
            corpus_sha256=corpus_sha256,
            model_id=_require_text(system.get("model_id"), f"{system_id}.model_id"),
            model_revision=_require_text(
                system.get("model_revision"), f"{system_id}.model_revision"
            ),
            artifact_sha256=_require_sha256(
                system.get("artifact_sha256"), f"{system_id}.artifact_sha256"
            ),
            code_revision=code_revision,
        )
    return adapters


def _validate_comparable_adapters(
    adapters: Mapping[str, RetrievalAdapter],
) -> str:
    """Bind every compared output to one corpus and immutable artifacts."""
    corpus_digests: set[str] = set()
    for system_id in REQUIRED_SYSTEMS:
        evidence = getattr(adapters[system_id], "evidence", None)
        if not isinstance(evidence, Mapping):
            raise EvaluationRefused(f"{system_id}.evidence: object required")
        mode = evidence.get("mode")
        if mode not in {"LIVE", "FIXTURE"}:
            raise EvaluationRefused(f"{system_id}.evidence.mode: LIVE or FIXTURE required")
        corpus_digests.add(
            _require_sha256(evidence.get("corpus_sha256"), f"{system_id}.corpus_sha256")
        )
        _require_text(evidence.get("model_id"), f"{system_id}.model_id")
        _require_text(evidence.get("model_revision"), f"{system_id}.model_revision")
        _require_sha256(
            evidence.get("artifact_sha256"), f"{system_id}.artifact_sha256"
        )
        _require_text(evidence.get("code_revision"), f"{system_id}.code_revision")
        if mode == "FIXTURE":
            _require_sha256(
                evidence.get("fixture_sha256"), f"{system_id}.fixture_sha256"
            )
            if evidence.get("model_execution") != "NOT_PERFORMED_BY_EVALUATOR":
                raise EvaluationRefused(
                    f"{system_id}.model_execution: fixture execution label required"
                )
    if len(corpus_digests) != 1:
        raise EvaluationRefused("all compared systems must bind the same corpus_sha256")
    return next(iter(corpus_digests))


def _safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    return None if denominator == 0 else float(numerator) / float(denominator)


def _ndcg_at_10(returned: Sequence[str], relevant: set[str]) -> float:
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, node_id in enumerate(returned[:10], 1)
        if node_id in relevant
    )
    ideal_count = min(len(relevant), 10)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    return 0.0 if idcg == 0 else dcg / idcg


def _evaluate_system(
    cases: Sequence[RetrievalCase],
    adapter: RetrievalAdapter,
    *,
    k_values: tuple[int, ...],
    limit: int,
) -> dict[str, Any]:
    recall_totals = {k: 0.0 for k in k_values}
    reciprocal_rank_total = 0.0
    ndcg_total = 0.0
    exact_hits = 0
    answerable = 0
    abstain_required = 0
    abstain_predicted = 0
    abstain_true_positive = 0
    abstain_correct = 0

    for case in cases:
        prediction = adapter.retrieve(case, limit=limit)
        if not isinstance(prediction, RetrievalPrediction):
            raise EvaluationRefused(
                f"{adapter.system_id}/{case.query_id}: RetrievalPrediction required"
            )
        returned = prediction.node_ids
        if len(returned) > limit:
            raise EvaluationRefused(f"{adapter.system_id}/{case.query_id}: output exceeds limit")
        if len(returned) != len(set(returned)):
            raise EvaluationRefused(f"{adapter.system_id}/{case.query_id}: duplicate output IDs")
        if prediction.abstained and returned:
            raise EvaluationRefused(
                f"{adapter.system_id}/{case.query_id}: abstention cannot include IDs"
            )
        unknown = sorted(set(returned) - set(case.candidate_node_ids))
        if unknown:
            raise EvaluationRefused(
                f"{adapter.system_id}/{case.query_id}: returned IDs outside offered candidates: "
                + ", ".join(unknown[:5])
            )

        is_required = case.should_abstain
        if is_required:
            abstain_required += 1
        if prediction.abstained:
            abstain_predicted += 1
        if is_required and prediction.abstained:
            abstain_true_positive += 1
        if is_required == prediction.abstained:
            abstain_correct += 1

        if is_required:
            continue
        answerable += 1
        relevant = set(case.relevant_node_ids)
        for k in k_values:
            recall_totals[k] += len(set(returned[:k]) & relevant) / len(relevant)
        first_rank = next(
            (rank for rank, node_id in enumerate(returned[:10], 1) if node_id in relevant),
            None,
        )
        reciprocal_rank_total += 0.0 if first_rank is None else 1.0 / first_rank
        ndcg_total += _ndcg_at_10(returned, relevant)
        if returned and returned[0] == case.exact_node_id:
            exact_hits += 1

    metrics: dict[str, Any] = {
        **{f"recall_at_{k}": recall_totals[k] / answerable for k in k_values},
        "mrr_at_10": reciprocal_rank_total / answerable,
        "ndcg_at_10": ndcg_total / answerable,
        "exact_id_at_1": exact_hits / answerable,
        "abstention_rate": abstain_predicted / len(cases),
        "abstention_accuracy": abstain_correct / len(cases),
        "abstention_precision": _safe_ratio(abstain_true_positive, abstain_predicted),
        "abstention_recall": _safe_ratio(abstain_true_positive, abstain_required),
    }
    return {
        "system_id": adapter.system_id,
        "case_count": len(cases),
        "answerable_count": answerable,
        "abstention_case_count": abstain_required,
        "metrics": metrics,
        "adapter_evidence": dict(getattr(adapter, "evidence", {})),
    }


def _metric_delta(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for key in sorted(set(left) & set(right)):
        left_value, right_value = left[key], right[key]
        if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
            result[key] = float(left_value) - float(right_value)
        else:
            result[key] = None
    return result


def evaluate_retrieval(
    cases_path: str | Path,
    split_manifest_path: str | Path,
    adapters: Mapping[str, RetrievalAdapter],
    *,
    promotion_requested: bool = False,
    k_values: tuple[int, ...] = (1, 5, 10),
) -> dict[str, Any]:
    """Evaluate BGE/Qwen base and reranked outputs after all admission gates pass."""
    if not k_values or any(not isinstance(k, int) or k < 1 or k > MAX_RETURNED for k in k_values):
        raise EvaluationRefused(f"k_values must be integers in [1, {MAX_RETURNED}]")
    k_values = tuple(sorted(set(k_values)))
    missing = [system_id for system_id in REQUIRED_SYSTEMS if system_id not in adapters]
    if missing:
        raise EvaluationRefused("missing required retrieval adapters: " + ", ".join(missing))
    cases, cases_sha256 = load_cases(cases_path)
    training_groups, held_out_groups, split_sha256 = load_split_manifest(split_manifest_path)
    observed_groups = {case.source_group for case in cases}
    if observed_groups != held_out_groups:
        missing_groups = sorted(held_out_groups - observed_groups)
        undeclared_groups = sorted(observed_groups - held_out_groups)
        raise EvaluationRefused(
            "held-out source groups do not exactly match the split manifest; "
            f"missing={missing_groups}, undeclared={undeclared_groups}"
        )
    if observed_groups & training_groups:
        raise EvaluationRefused("observed held-out cases overlap training source groups")
    if promotion_requested and len(cases) < MIN_PROMOTION_QUERIES:
        raise EvaluationRefused(
            f"promotion requires at least {MIN_PROMOTION_QUERIES} unique human-authored "
            f"held-out queries; observed {len(cases)}"
        )
    corpus_sha256 = _validate_comparable_adapters(adapters)

    limit = max(max(k_values), 10)
    systems = {
        system_id: _evaluate_system(cases, adapters[system_id], k_values=k_values, limit=limit)
        for system_id in REQUIRED_SYSTEMS
    }
    metrics = {system_id: systems[system_id]["metrics"] for system_id in REQUIRED_SYSTEMS}
    dataset_eligible = len(cases) >= MIN_PROMOTION_QUERIES
    return {
        "schema": REPORT_SCHEMA,
        "status": "EVALUATED",
        "execution": {
            "bounded_case_limit": MAX_CASES,
            "returned_id_limit": limit,
            "gpu_training": "NOT_PERFORMED",
            "brain_runtime_changed": False,
        },
        "inputs": {
            "cases_sha256": cases_sha256,
            "split_manifest_sha256": split_sha256,
            "corpus_sha256": corpus_sha256,
            "human_authored_held_out_queries": len(cases),
            "answerable_queries": sum(not case.should_abstain for case in cases),
            "abstention_queries": sum(case.should_abstain for case in cases),
            "training_source_groups": sorted(training_groups),
            "held_out_source_groups": sorted(held_out_groups),
        },
        "promotion_dataset_gate": {
            "requested": promotion_requested,
            "minimum_human_held_out_queries": MIN_PROMOTION_QUERIES,
            "eligible": dataset_eligible,
            "status": "ELIGIBLE" if dataset_eligible else "NOT_ELIGIBLE",
            "note": "Dataset eligibility is not a model promotion or performance claim.",
        },
        "systems": systems,
        "comparisons": {
            "BGE_RERANKED_MINUS_BASE": _metric_delta(
                metrics["BGE_RERANKED"], metrics["BGE_BASE"]
            ),
            "QWEN_RERANKED_MINUS_BASE": _metric_delta(
                metrics["QWEN_RERANKED"], metrics["QWEN_BASE"]
            ),
            "QWEN_BASE_MINUS_BGE_BASE": _metric_delta(
                metrics["QWEN_BASE"], metrics["BGE_BASE"]
            ),
            "QWEN_RERANKED_MINUS_BGE_RERANKED": _metric_delta(
                metrics["QWEN_RERANKED"], metrics["BGE_RERANKED"]
            ),
        },
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path, help="provenance-admitted held-out JSONL")
    parser.add_argument("split_manifest", type=Path, help="source-group split JSON")
    parser.add_argument("predictions", type=Path, help="recorded BGE/Qwen fixture JSON")
    parser.add_argument("--promotion", action="store_true", help="enforce the 200-query gate")
    parser.add_argument("--output", type=Path, help="write the JSON report instead of stdout")
    args = parser.parse_args()
    try:
        report = evaluate_retrieval(
            args.cases,
            args.split_manifest,
            load_fixture_adapters(args.predictions),
            promotion_requested=args.promotion,
        )
    except (OSError, EvaluationRefused) as exc:
        print(json.dumps({"schema": REPORT_SCHEMA, "status": "REFUSED", "reason": str(exc)}))
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
