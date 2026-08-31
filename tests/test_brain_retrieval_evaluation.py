"""Focused tests for the offline Brain retrieval evaluation gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from brain.retrieval_evaluation import (
    CASE_SCHEMA,
    MIN_PROMOTION_QUERIES,
    REQUIRED_SYSTEMS,
    SPLIT_SCHEMA,
    EvaluationRefused,
    FixtureAdapter,
    RetrievalPrediction,
    evaluate_retrieval,
    load_fixture_adapters,
)


HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64


def _case(index: int, *, abstain: bool = False, group: str = "held:alpha") -> dict:
    candidate_ids = [f"node:{index}:exact", f"node:{index}:near", f"node:{index}:noise"]
    return {
        "schema": CASE_SCHEMA,
        "query_id": f"q-{index:04d}",
        "query": f"Human held-out retrieval question number {index}?",
        "authorship": {
            "kind": "HUMAN",
            "author_id": "reviewer:human-1",
            "attestation_id": f"authorship:{index:04d}",
        },
        "rights": {
            "status": "ADMITTED",
            "license": "Apache-2.0",
            "permission_scope": ["retrieval_evaluation"],
            "evidence_ref": f"rights:{index:04d}",
            "evidence_sha256": HEX_A,
        },
        "provenance": {
            "status": "ADMITTED",
            "source_uri": f"https://example.invalid/source/{index}",
            "source_revision": "fixture-revision-1",
            "content_sha256": HEX_B,
            "admission_receipt_id": f"admission:{index:04d}",
        },
        "split": {"partition": "HELD_OUT", "source_group": group},
        "candidate_node_ids": candidate_ids,
        "relevant_node_ids": [] if abstain else candidate_ids[:2],
        "exact_node_id": None if abstain else candidate_ids[0],
        "should_abstain": abstain,
    }


def _write_inputs(tmp_path: Path, cases: list[dict], *, train_groups=None, held_groups=None):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        "".join(json.dumps(case, sort_keys=True) + "\n" for case in cases),
        encoding="utf-8",
    )
    split_path = tmp_path / "split.json"
    split_path.write_text(
        json.dumps(
            {
                "schema": SPLIT_SCHEMA,
                "training_source_groups": train_groups or ["train:one"],
                "held_out_source_groups": held_groups or sorted({case["split"]["source_group"] for case in cases}),
                "provenance": {
                    "status": "ADMITTED",
                    "receipt_id": "split-receipt-1",
                    "content_sha256": HEX_A,
                },
            }
        ),
        encoding="utf-8",
    )
    return cases_path, split_path


def _adapters(cases: list[dict], *, improved: bool = True):
    systems = {}
    for system_id in REQUIRED_SYSTEMS:
        rows = {}
        for case in cases:
            query_id = case["query_id"]
            if case["should_abstain"]:
                abstain = system_id in {"BGE_RERANKED", "QWEN_RERANKED"}
                rows[query_id] = RetrievalPrediction((), abstained=abstain)
            elif system_id in {"BGE_BASE", "QWEN_BASE"}:
                rows[query_id] = RetrievalPrediction(
                    (case["candidate_node_ids"][2], case["candidate_node_ids"][0])
                )
            else:
                rows[query_id] = RetrievalPrediction(
                    (case["candidate_node_ids"][0], case["candidate_node_ids"][1])
                    if improved
                    else (case["candidate_node_ids"][2],)
                )
        systems[system_id] = FixtureAdapter(
            system_id,
            rows,
            fixture_sha256=hashlib.sha256(system_id.encode()).hexdigest(),
            corpus_sha256=HEX_C,
            model_id=f"test/{system_id.lower()}",
            model_revision="revision-1",
            artifact_sha256=hashlib.sha256(f"artifact:{system_id}".encode()).hexdigest(),
            code_revision="test-code-revision",
        )
    return systems


def test_computes_retrieval_abstention_and_rerank_deltas(tmp_path: Path):
    cases = [_case(1), _case(2), _case(3, abstain=True)]
    cases_path, split_path = _write_inputs(tmp_path, cases)
    report = evaluate_retrieval(cases_path, split_path, _adapters(cases))

    base = report["systems"]["BGE_BASE"]["metrics"]
    reranked = report["systems"]["BGE_RERANKED"]["metrics"]
    assert base["recall_at_1"] == 0.0
    assert base["recall_at_5"] == 0.5
    assert base["mrr_at_10"] == 0.5
    assert base["exact_id_at_1"] == 0.0
    assert reranked["recall_at_1"] == 0.5
    assert reranked["recall_at_5"] == 1.0
    assert reranked["mrr_at_10"] == 1.0
    assert reranked["exact_id_at_1"] == 1.0
    assert reranked["abstention_precision"] == 1.0
    assert reranked["abstention_recall"] == 1.0
    assert report["comparisons"]["BGE_RERANKED_MINUS_BASE"]["mrr_at_10"] == 0.5
    assert report["promotion_dataset_gate"]["status"] == "NOT_ELIGIBLE"
    assert report["execution"]["gpu_training"] == "NOT_PERFORMED"


def test_promotion_refuses_fewer_than_200_human_held_out_queries(tmp_path: Path):
    cases = [_case(1), _case(2, abstain=True)]
    cases_path, split_path = _write_inputs(tmp_path, cases)
    with pytest.raises(EvaluationRefused, match="at least 200"):
        evaluate_retrieval(
            cases_path,
            split_path,
            _adapters(cases),
            promotion_requested=True,
        )


def test_promotion_dataset_gate_accepts_exactly_200_unique_human_queries(tmp_path: Path):
    cases = [_case(i, abstain=(i % 20 == 0)) for i in range(MIN_PROMOTION_QUERIES)]
    cases_path, split_path = _write_inputs(tmp_path, cases)
    report = evaluate_retrieval(
        cases_path,
        split_path,
        _adapters(cases),
        promotion_requested=True,
    )
    assert report["inputs"]["human_authored_held_out_queries"] == 200
    assert report["promotion_dataset_gate"]["eligible"] is True
    assert report["promotion_dataset_gate"]["note"].startswith("Dataset eligibility")


@pytest.mark.parametrize(
    ("field", "nested", "expected"),
    [
        ("rights", "status", "rights.status"),
        ("provenance", "admission_receipt_id", "admission_receipt_id"),
        ("authorship", "kind", "authorship.kind"),
    ],
)
def test_refuses_missing_admission_evidence_before_adapter_execution(
    tmp_path: Path, field: str, nested: str, expected: str
):
    cases = [_case(1), _case(2, abstain=True)]
    cases[0][field].pop(nested)
    cases_path, split_path = _write_inputs(tmp_path, cases)

    class MustNotRun:
        system_id = "BGE_BASE"
        evidence = {}

        def retrieve(self, case, *, limit):
            raise AssertionError("adapter ran before admission completed")

    adapters = _adapters(cases)
    adapters["BGE_BASE"] = MustNotRun()
    with pytest.raises(EvaluationRefused, match=expected):
        evaluate_retrieval(cases_path, split_path, adapters)


def test_refuses_source_group_leakage_and_manifest_mismatch(tmp_path: Path):
    cases = [_case(1), _case(2, abstain=True)]
    cases_path, split_path = _write_inputs(
        tmp_path,
        cases,
        train_groups=["train:one", "held:alpha"],
        held_groups=["held:alpha"],
    )
    with pytest.raises(EvaluationRefused, match="leakage"):
        evaluate_retrieval(cases_path, split_path, _adapters(cases))

    cases_path, split_path = _write_inputs(
        tmp_path,
        cases,
        held_groups=["held:alpha", "held:missing"],
    )
    with pytest.raises(EvaluationRefused, match="do not exactly match"):
        evaluate_retrieval(cases_path, split_path, _adapters(cases))


def test_refuses_nonhuman_duplicate_and_out_of_candidate_predictions(tmp_path: Path):
    cases = [_case(1), _case(2, abstain=True)]
    cases[0]["authorship"]["kind"] = "SYNTHETIC"
    cases_path, split_path = _write_inputs(tmp_path, cases)
    with pytest.raises(EvaluationRefused, match="HUMAN required"):
        evaluate_retrieval(cases_path, split_path, _adapters(cases))

    cases = [_case(1), _case(2, abstain=True)]
    cases[1]["query"] = cases[0]["query"].upper()
    cases_path, split_path = _write_inputs(tmp_path, cases)
    with pytest.raises(EvaluationRefused, match="count inflation refused"):
        evaluate_retrieval(cases_path, split_path, _adapters(cases))

    cases = [_case(1), _case(2, abstain=True)]
    cases_path, split_path = _write_inputs(tmp_path, cases)
    adapters = _adapters(cases)
    bad = dict(adapters["QWEN_BASE"]._predictions)
    bad[cases[0]["query_id"]] = RetrievalPrediction(("node:not-offered",))
    adapters["QWEN_BASE"] = FixtureAdapter(
        "QWEN_BASE",
        bad,
        fixture_sha256=HEX_A,
        corpus_sha256=HEX_C,
        model_id="test/qwen-base",
        model_revision="revision-1",
        artifact_sha256=HEX_B,
        code_revision="test-code-revision",
    )
    with pytest.raises(EvaluationRefused, match="outside offered candidates"):
        evaluate_retrieval(cases_path, split_path, adapters)


def test_refuses_incomplete_bge_qwen_comparison_matrix(tmp_path: Path):
    cases = [_case(1), _case(2, abstain=True)]
    cases_path, split_path = _write_inputs(tmp_path, cases)
    adapters = _adapters(cases)
    del adapters["QWEN_RERANKED"]
    with pytest.raises(EvaluationRefused, match="QWEN_RERANKED"):
        evaluate_retrieval(cases_path, split_path, adapters)


def test_recorded_fixture_file_uses_the_same_four_adapter_contract(tmp_path: Path):
    cases = [_case(1), _case(2, abstain=True)]
    cases_path, split_path = _write_inputs(tmp_path, cases)
    systems = {}
    for system_id in REQUIRED_SYSTEMS:
        systems[system_id] = {
            "model_id": f"test/{system_id.lower()}",
            "model_revision": "revision-1",
            "artifact_sha256": hashlib.sha256(
                f"artifact:{system_id}".encode()
            ).hexdigest(),
            "predictions": {
                cases[0]["query_id"]: {
                    "node_ids": [cases[0]["exact_node_id"]],
                    "abstained": False,
                },
                cases[1]["query_id"]: {"node_ids": [], "abstained": True},
            },
        }
    fixture_path = tmp_path / "predictions.json"
    fixture_path.write_text(
        json.dumps(
            {
                "schema": "szl.brain-retrieval-fixture/v1",
                "corpus_sha256": HEX_C,
                "code_revision": "test-code-revision",
                "systems": systems,
            }
        ),
        encoding="utf-8",
    )

    adapters = load_fixture_adapters(fixture_path)
    report = evaluate_retrieval(cases_path, split_path, adapters)
    assert set(report["systems"]) == set(REQUIRED_SYSTEMS)
    for system_id in REQUIRED_SYSTEMS:
        assert report["systems"][system_id]["metrics"]["exact_id_at_1"] == 1.0
        assert report["systems"][system_id]["adapter_evidence"]["mode"] == "FIXTURE"
        assert (
            report["systems"][system_id]["adapter_evidence"]["model_execution"]
            == "NOT_PERFORMED_BY_EVALUATOR"
        )


def test_refuses_cross_corpus_comparison(tmp_path: Path):
    cases = [_case(1), _case(2, abstain=True)]
    cases_path, split_path = _write_inputs(tmp_path, cases)
    adapters = _adapters(cases)
    qwen = adapters["QWEN_BASE"]
    adapters["QWEN_BASE"] = FixtureAdapter(
        "QWEN_BASE",
        qwen._predictions,
        fixture_sha256=HEX_A,
        corpus_sha256="d" * 64,
        model_id="test/qwen-base",
        model_revision="revision-1",
        artifact_sha256=HEX_B,
        code_revision="test-code-revision",
    )
    with pytest.raises(EvaluationRefused, match="same corpus_sha256"):
        evaluate_retrieval(cases_path, split_path, adapters)
