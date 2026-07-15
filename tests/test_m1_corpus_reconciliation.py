#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Dependency-light checks for the current M1 Brain decision ledger."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from a11oy_brain_graph import get_brain_graph


ROOT = Path(__file__).resolve().parents[1]
M1 = ROOT / "model_release" / "m1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def _ledger_summary() -> dict[str, object]:
    node_ids: set[str] = set()
    decisions: dict[str, int] = {}
    rows = distinct = eligible = 0
    with (M1 / "brain-ingest-ledger.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            node_id = str(row.get("node_id") or "")
            assert node_id and node_id not in node_ids
            node_ids.add(node_id)
            rows += 1
            distinct += row.get("artifact_role") == "DISTINCT_ARTIFACT"
            eligible += row.get("training_eligible") is not False
            decision = str(row.get("training_decision") or "")
            decisions[decision] = decisions.get(decision, 0) + 1
    return {
        "node_ids": node_ids,
        "rows": rows,
        "distinct": distinct,
        "eligible": eligible,
        "decisions": decisions,
    }


def test_m1_ledger_exactly_covers_the_current_brain():
    graph = get_brain_graph(refresh=True)
    summary = _ledger_summary()
    current_ids = {str(node.get("id") or "") for node in graph["nodes"]}
    assert graph["node_count"] == summary["rows"] == 9464
    assert graph["distinct_artifacts"] == summary["distinct"] == 4229
    assert graph["person_node_count"] == 5235
    assert current_ids == summary["node_ids"]


def test_every_raw_brain_row_is_training_quarantined():
    summary = _ledger_summary()
    assert summary["eligible"] == 0
    assert summary["decisions"] == {"QUARANTINE": 9464}


def test_m1_manifests_bind_the_exact_reconciled_artifacts():
    corpus = json.loads((M1 / "corpus-ingestion-manifest.json").read_text(encoding="utf-8"))
    candidate = json.loads((M1 / "candidate-manifest.json").read_text(encoding="utf-8"))
    operational = json.loads((M1 / "operational-manifest.json").read_text(encoding="utf-8"))
    brain = M1 / "brain-ingest-ledger.jsonl"
    corpus_path = M1 / "corpus-ingestion-manifest.json"

    assert corpus["coverage"]["raw_nodes_training_quarantined"] == 9464
    assert corpus["coverage"]["training_eligible_nodes"] == 0
    assert corpus["ledgers"]["brain_nodes"]["sha256"] == _sha256(brain)
    assert candidate["full_corpus_proposal"]["manifest_sha256"] == _sha256(corpus_path)
    assert candidate["full_corpus_proposal"]["brain_raw_nodes"] == 9464
    assert operational["corpus_policy"]["require_raw_brain_training_quarantine"] is True
    assert operational["evidence"]["brain_ingest_ledger"]["sha256"] == _sha256(brain)
    assert operational["evidence"]["corpus_ingestion_manifest"]["sha256"] == _sha256(corpus_path)
