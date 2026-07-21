from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from szl_brain_snapshot import SnapshotError, build_snapshot, load_ledger


def _row(node_id: str, content: str) -> dict:
    import hashlib

    return {
        "schema": "szl.m1-brain-ingest-decision/v1",
        "node_id": node_id,
        "kind": "paper",
        "canonical_text": content,
        "canonical_text_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "source_family": "academic-publication-metadata",
        "provenance": {"source": "arxiv"},
        "license": {"state": "UNKNOWN_ITEM_LEVEL_LICENSE"},
        "freshness": {"state": "UNKNOWN_NO_SOURCE_TIMESTAMP"},
        "safety_decision": "QUARANTINE_LICENSE_UNKNOWN",
        "training_decision": "QUARANTINE",
        "training_eligible": False,
    }


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_snapshot_is_deterministic_and_never_authorizes_training(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    _write(ledger, [_row("paper:1", "one"), _row("paper:2", "two")])

    first = build_snapshot(ledger)
    second = build_snapshot(ledger)

    assert first == second
    assert first["counts"] == {
        "rows": 2,
        "unique_node_ids": 2,
        "distinct_content_sha256": 2,
        "duplicate_content_rows": 0,
        "person_rows": 0,
        "training_eligible_rows": 0,
    }
    assert len(first["integrity"]["merkle_root_sha256"]) == 64
    assert first["claims_boundary"]["training_authorized"] is False
    assert first["claims_boundary"]["training_triggered"] is False


def test_snapshot_changes_when_a_bound_row_changes(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    _write(ledger, [_row("paper:1", "one")])
    first = build_snapshot(ledger)
    _write(ledger, [_row("paper:1", "changed")])
    second = build_snapshot(ledger)
    assert first["snapshot_sha256"] != second["snapshot_sha256"]
    assert (
        first["integrity"]["merkle_root_sha256"]
        != second["integrity"]["merkle_root_sha256"]
    )


def test_snapshot_rejects_duplicate_ids_and_bad_content_binding(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    row = _row("paper:1", "one")
    _write(ledger, [row, row])
    with pytest.raises(SnapshotError, match="LEDGER_DUPLICATE_NODE_ID"):
        load_ledger(ledger)

    bad = _row("paper:2", "two")
    bad["canonical_text_sha256"] = "0" * 64
    _write(ledger, [bad])
    with pytest.raises(SnapshotError, match="LEDGER_CONTENT_BINDING_INVALID:1"):
        load_ledger(ledger)


def test_real_snapshot_matches_committed_ledger():
    root = Path(__file__).resolve().parents[1]
    snapshot = build_snapshot(root / "model_release/m1/brain-ingest-ledger.jsonl")
    schema = json.loads(
        (root / "model_release/brain-row-admission/schemas/raw-snapshot.schema.json")
        .read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(snapshot)
    assert snapshot["counts"]["rows"] == 9464
    assert snapshot["counts"]["training_eligible_rows"] == 0
    assert snapshot["facets"]["license_state"] == {
        "UNKNOWN_ITEM_LEVEL_LICENSE": 9301,
        "VERSIONED_REPOSITORY_LICENSE": 163,
    }
    assert snapshot["facets"]["freshness_state"] == {
        "CAPTURED_SOURCE_DATE": 34,
        "UNKNOWN_NO_SOURCE_TIMESTAMP": 9267,
        "VERSION_BOUND_NOT_TIME_FRESH": 163,
    }
