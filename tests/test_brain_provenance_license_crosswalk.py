# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import szl_brain_provenance_license_crosswalk as crosswalk


REVISION = "git:" + ("a" * 40)


def canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def ledger_row(
    node_id: str,
    content: str,
    *,
    source_family: str = "repository-metadata",
    kind: str = "repo",
    safety_decision: str = "QUARANTINE_LICENSE_UNKNOWN",
    licensed: bool = False,
    url: str = "https://github.com/example/project",
):
    return {
        "schema": crosswalk.LEDGER_SCHEMA,
        "node_id": node_id,
        "canonical_text": content,
        "canonical_text_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "canonical_artifact_id": node_id if licensed else None,
        "kind": kind,
        "source_family": source_family,
        "provenance": {"url": url},
        "license": {
            "state": "VERSIONED_REPOSITORY_LICENSE" if licensed else "UNKNOWN_ITEM_LEVEL_LICENSE",
            "spdx": "Apache-2.0" if licensed else None,
            "evidence": "LICENSE" if licensed else None,
        },
        "safety_decision": safety_decision,
        "training_decision": "QUARANTINE",
        "training_eligible": False,
    }


def write_inputs(tmp_path: Path, rows: list[dict]):
    ledger_path = tmp_path / crosswalk.LEDGER_REPOSITORY_PATH
    snapshot_path = tmp_path / crosswalk.SNAPSHOT_REPOSITORY_PATH
    license_path = tmp_path / crosswalk.LICENSE_REPOSITORY_PATH
    ledger_path.parent.mkdir(parents=True)
    snapshot_path.parent.mkdir(parents=True)
    ledger_bytes = b"".join(canonical_bytes(row) + b"\n" for row in rows)
    ledger_path.write_bytes(ledger_bytes)
    license_path.write_text("Apache License\nVersion 2.0\n", encoding="utf-8")
    snapshot = {
        "schema_version": crosswalk.SNAPSHOT_SCHEMA,
        "source": {
            "path": crosswalk.LEDGER_REPOSITORY_PATH,
            "sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        },
        "counts": {
            "rows": len(rows),
            "unique_node_ids": len(rows),
            "distinct_content_sha256": len(rows),
            "training_eligible_rows": 0,
            "duplicate_content_rows": 0,
        },
        "claims_boundary": {
            "model_promotion_allowed": False,
            "privacy_clearance_established": False,
            "rights_established": False,
            "training_authorized": False,
            "training_triggered": False,
        },
    }
    snapshot_path.write_bytes(canonical_bytes(snapshot) + b"\n")
    blobs = {
        crosswalk.LEDGER_REPOSITORY_PATH: ledger_path.read_bytes(),
        crosswalk.SNAPSHOT_REPOSITORY_PATH: snapshot_path.read_bytes(),
        crosswalk.LICENSE_REPOSITORY_PATH: license_path.read_bytes(),
    }
    return blobs


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_crosswalk_binds_known_license_but_keeps_every_row_quarantined(tmp_path: Path):
    rows = [
        ledger_row(
            "endpoint:/api/example",
            "title: local endpoint metadata\nkind: endpoint",
            source_family="a11oy-versioned-runtime",
            kind="endpoint",
            safety_decision="QUARANTINE_RAW_GRAPH_NOT_ADMITTED",
            licensed=True,
            url="https://github.com/szl-holdings/a11oy/blob/" + ("b" * 40) + "/serve.py",
        ),
        ledger_row("repo:external", "external repository metadata"),
    ]
    blobs = write_inputs(tmp_path, rows)
    output = tmp_path / "out"

    receipt = crosswalk.build_crosswalk(
        tmp_path,
        REVISION,
        output,
        expected_rows=2,
        blob_reader=blobs.__getitem__,
    )

    values = read_jsonl(output / "brain-row-provenance-license-crosswalk.v1.jsonl")
    assert len(values) == 2
    assert receipt["coverage"] == {
        "immutable_ledger_binding_pass": 2,
        "immutable_item_origin_pass": 0,
        "version_bound_license_pass": 1,
        "signed_privacy_clearance_pass": 0,
        "semantic_duplication_evidence_pass": 0,
        "signed_consent_or_permission_pass": 0,
        "signed_independent_review_pass": 0,
        "admitted_rows": 0,
        "quarantined_rows": 2,
    }
    assert sum(item["license"]["state"] == "PASS" for item in values) == 1
    assert all(item["immutable_item_origin"]["state"] == "MISSING" for item in values)
    assert all(item["admission"]["state"] == "QUARANTINE" for item in values)
    assert all(item["admission"]["training_eligible"] is False for item in values)
    serialized = json.dumps(values)
    assert "endpoint:/api/example" not in serialized
    assert "repo:external" not in serialized
    assert "title: local endpoint metadata" not in serialized
    assert rows[0]["canonical_text_sha256"] not in serialized
    assert receipt["authorization"]["signature_state"] == "UNSIGNED_NO_APPROVED_KEY"


def test_repository_or_pinned_looking_url_never_establishes_item_origin(tmp_path: Path):
    rows = [
        ledger_row(
            "repo:pinned-looking",
            "still lacks independent item evidence",
            url="https://github.com/example/project/blob/" + ("c" * 40) + "/README.md",
        )
    ]
    blobs = write_inputs(tmp_path, rows)
    output = tmp_path / "out"

    crosswalk.build_crosswalk(
        tmp_path,
        REVISION,
        output,
        expected_rows=1,
        blob_reader=blobs.__getitem__,
    )

    [value] = read_jsonl(output / "brain-row-provenance-license-crosswalk.v1.jsonl")
    assert value["immutable_item_origin"] == {
        "state": "MISSING",
        "reason": "NO_ITEM_LEVEL_IMMUTABLE_SOURCE_REVISION",
    }
    assert "IMMUTABLE_ITEM_ORIGIN_EVIDENCE_MISSING" in value["admission"]["blockers"]


def test_formula_duplicate_remains_explicitly_blocked(tmp_path: Path):
    rows = [
        ledger_row(
            "formula:F1",
            "duplicate formula view",
            source_family="brain-raw-formula-index",
            kind="formula",
            safety_decision="QUARANTINE_RAW_GRAPH_DUPLICATE_FORMULA",
            licensed=True,
            url="",
        )
    ]
    blobs = write_inputs(tmp_path, rows)
    output = tmp_path / "out"

    crosswalk.build_crosswalk(
        tmp_path,
        REVISION,
        output,
        expected_rows=1,
        blob_reader=blobs.__getitem__,
    )

    [value] = read_jsonl(output / "brain-row-provenance-license-crosswalk.v1.jsonl")
    assert value["duplication"]["semantic"] == "DUPLICATE_FLAGGED"
    assert "SEMANTIC_DUPLICATE_FLAGGED" in value["admission"]["blockers"]
    assert value["admission"]["state"] == "QUARANTINE"


def test_refuses_working_file_that_differs_from_pinned_git_blob(tmp_path: Path):
    rows = [ledger_row("repo:a", "alpha")]
    blobs = write_inputs(tmp_path, rows)
    blobs[crosswalk.LICENSE_REPOSITORY_PATH] = b"different license bytes\n"

    with pytest.raises(crosswalk.CrosswalkRefused, match="differs from the pinned Git blob"):
        crosswalk.build_crosswalk(
            tmp_path,
            REVISION,
            tmp_path / "out",
            expected_rows=1,
            blob_reader=blobs.__getitem__,
        )


def test_refuses_duplicate_content_even_with_different_node_ids(tmp_path: Path):
    rows = [ledger_row("repo:a", "same"), ledger_row("repo:b", "same")]
    blobs = write_inputs(tmp_path, rows)

    with pytest.raises(crosswalk.CrosswalkRefused, match="unique node/content identities"):
        crosswalk.build_crosswalk(
            tmp_path,
            REVISION,
            tmp_path / "out",
            expected_rows=2,
            blob_reader=blobs.__getitem__,
        )


def test_receipt_validates_against_committed_schema(tmp_path: Path):
    rows = [ledger_row("repo:a", "alpha")]
    blobs = write_inputs(tmp_path, rows)
    output = tmp_path / "out"
    receipt = crosswalk.build_crosswalk(
        tmp_path,
        REVISION,
        output,
        expected_rows=1,
        blob_reader=blobs.__getitem__,
    )
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "model_release"
        / "brain-row-admission"
        / "schemas"
        / "crosswalk-receipt.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(receipt)


def test_receipt_hash_binds_exact_core(tmp_path: Path):
    rows = [ledger_row("repo:a", "alpha")]
    blobs = write_inputs(tmp_path, rows)
    receipt = crosswalk.build_crosswalk(
        tmp_path,
        REVISION,
        tmp_path / "out",
        expected_rows=1,
        blob_reader=blobs.__getitem__,
    )
    core = dict(receipt)
    observed = core.pop("receipt_sha256")
    assert observed == hashlib.sha256(canonical_bytes(core)).hexdigest()


def test_committed_aggregate_receipt_is_schema_valid_and_self_bound():
    root = Path(__file__).resolve().parents[1]
    receipt_path = (
        root
        / "model_release"
        / "brain-row-admission"
        / "provenance-license-crosswalk-receipt.json"
    )
    schema_path = (
        root
        / "model_release"
        / "brain-row-admission"
        / "schemas"
        / "crosswalk-receipt.schema.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(receipt)
    assert receipt["coverage"]["immutable_ledger_binding_pass"] == 9464
    assert receipt["coverage"]["version_bound_license_pass"] == 163
    assert receipt["coverage"]["admitted_rows"] == 0
    assert receipt["coverage"]["quarantined_rows"] == 9464
    assert receipt["authorization"]["training_authorized"] is False
    assert receipt["authorization"]["training_triggered"] is False

    core = dict(receipt)
    observed = core.pop("receipt_sha256")
    assert observed == hashlib.sha256(canonical_bytes(core)).hexdigest()
