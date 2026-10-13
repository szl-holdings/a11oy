#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic classifier cases; these tests never qualify a real database."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "classify_gdw_historical_qualification", ROOT / "scripts/classify_gdw_historical_qualification.py")
assert SPEC and SPEC.loader
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)
SOURCE = "a" * 40
PRIVATE = "PRIVATE_PROVIDER_TEXT_PATH_OR_ROW_NEVER_PUBLISHED"
PUBLIC_KEYS = {
    "schema", "source_revision", "run_id", "run_attempt", "evidence_class", "scope", "state",
    "historical_rehearsal_state", "diagnostic_code", "restore_admitted", "deployment_admitted",
    "later_acknowledged_writes_verified",
}


@pytest.fixture
def valid_report():
    capture = json.loads(c.CAPTURE_PATH.read_bytes())
    anchors = json.loads(c.ANCHORS_PATH.read_bytes())
    report = {
        "schema": c.SCHEMA, "state": "LOGICAL_CONTINUITY_VERIFIED",
        "inspector_source_revision": SOURCE, "diagnostic_code": "RESTORE_CONTRACT_REQUIRED",
        "historical_anchor_state": "VERIFIED", "captured_historical_anchor_state": "VERIFIED",
        "historical_anchor_reference": {key: anchors[key] for key in c.ANCHOR_REFERENCE_FIELDS},
        "capture_id": capture["capture_id"], "capture_source_revision": capture["source_revision"],
        "preservation_manifest_sha256": capture["private_manifest"]["sha256"], "databases": {},
        **{key: False for key in c.FALSE_FLAGS},
    }
    for label in ("gdw", "series_a"):
        anchor = {"state": "VERIFIED", "sequence": anchors[label]["sequence"],
                  "receipt_sha256": anchors[label]["receipt_sha256"], "generation_unchanged": True}
        if label == "gdw":
            anchor.update(signature_verification="VERIFIED_PINNED_PUBLIC_KEY",
                          pinned_key_der_sha256=anchors[label]["pinned_key_der_sha256"],
                          chain_sha256=anchors[label]["chain_sha256"],
                          audit_scope_unchanged=True, report_payload_bindings_verified=True,
                          payload_sha256="c" * 64)
        else:
            anchor.update(signature_verification="NOT_PERFORMED", storage_created_at_unchanged=True,
                          minimum_receipt_count=anchors[label]["minimum_receipt_count"],
                          receipt_count=capture["databases"][label]["table_counts"]["receipts"])
        report["databases"][label] = {
            "state": "LOGICAL_CONTINUITY_VERIFIED", "diagnostic_code": "RESTORE_CONTRACT_REQUIRED",
            "historical_anchor_state": "VERIFIED", "restore_admitted": False,
            "durable_storage_qualified": False, "database_generation_id": anchors[label]["database_generation_id"],
            "original_historical_anchor": anchor, "candidate_historical_anchor": copy.deepcopy(anchor),
            "candidate_integrity": {"classification": "OK", "foreign_key_violation_count": 0,
                                    "foreign_key_check_complete": True, "integrity_check_complete": True,
                                    "unreferenced_page_count": 0, "result_sha256": "d" * 64},
            **{key: True for key in c.UNCHANGED_FLAGS},
        }
    return report


def classify(report, **kwargs):
    return c.classify(report, **{"exit_code": 0, "expected_sha": SOURCE,
                                "run_id": "123456", "run_attempt": "1", **kwargs})


def assert_blocked(public):
    assert set(public) == PUBLIC_KEYS
    assert public["evidence_class"] == "SAMPLE"
    assert public["scope"] == "HISTORICAL_CAPTURE_ONLY"
    assert public["state"] == "BLOCKED"
    assert public["restore_admitted"] is False
    assert public["deployment_admitted"] is False
    assert public["later_acknowledged_writes_verified"] is False
    assert PRIVATE not in json.dumps(public)


def test_verified_rehearsal_is_not_release_admission(valid_report):
    public, verified = classify(valid_report)
    assert verified
    assert public["historical_rehearsal_state"] == "VERIFIED"
    assert public["diagnostic_code"] == "RESTORE_CONTRACT_REQUIRED"
    assert public["evidence_class"] == "SAMPLE"
    assert_blocked(public)


def test_private_fields_are_never_projected(valid_report):
    valid_report.update(provider_error=PRIVATE, private_capture_prefix=PRIVATE, credential=PRIVATE)
    valid_report["databases"]["gdw"]["raw_private_rows"] = [PRIVATE]
    public, verified = classify(valid_report)
    assert verified
    assert_blocked(public)
    assert valid_report["capture_id"] not in json.dumps(public)
    assert "historical_anchor_reference" not in public


@pytest.mark.parametrize("field", c.FALSE_FLAGS + ("space_mutated",))
@pytest.mark.parametrize("unsafe", [True, 0, None, "false"])
def test_effect_and_private_flags_fail_closed(valid_report, field, unsafe):
    valid_report[field] = unsafe
    public, verified = classify(valid_report)
    assert not verified
    assert public["historical_rehearsal_state"] == "NOT_VERIFIED"
    assert_blocked(public)


@pytest.mark.parametrize("field", c.FALSE_FLAGS)
def test_missing_safety_flag_fails_closed(valid_report, field):
    del valid_report[field]
    assert not classify(valid_report)[1]


@pytest.mark.parametrize("field", ["schema", "state", "diagnostic_code", "inspector_source_revision",
                                  "capture_id", "capture_source_revision", "preservation_manifest_sha256",
                                  "historical_anchor_state", "captured_historical_anchor_state"])
def test_report_binding_mismatch_fails_closed(valid_report, field):
    valid_report[field] = PRIVATE
    public, verified = classify(valid_report)
    assert not verified
    assert_blocked(public)


@pytest.mark.parametrize("field", c.ANCHOR_REFERENCE_FIELDS)
def test_historical_reference_mismatch_fails_closed(valid_report, field):
    valid_report["historical_anchor_reference"][field] = PRIVATE
    assert not classify(valid_report)[1]


@pytest.mark.parametrize("label", ["gdw", "series_a"])
@pytest.mark.parametrize("field", ["state", "historical_anchor_state", "database_generation_id",
                                  "restore_admitted", "durable_storage_qualified", *c.UNCHANGED_FLAGS])
def test_both_databases_must_be_logically_verified(valid_report, label, field):
    valid_report["databases"][label][field] = None
    assert not classify(valid_report)[1]


@pytest.mark.parametrize("label", ["gdw", "series_a"])
def test_database_anchor_must_match_fixed_source(valid_report, label):
    for kind in ("original_historical_anchor", "candidate_historical_anchor"):
        valid_report["databases"][label][kind]["receipt_sha256"] = "b" * 64
    assert not classify(valid_report)[1]


@pytest.mark.parametrize("field,invalid", [
    ("signature_verification", "NOT_PERFORMED"), ("pinned_key_der_sha256", "b" * 64),
    ("chain_sha256", "b" * 64), ("audit_scope_unchanged", False),
    ("report_payload_bindings_verified", False), ("payload_sha256", "not-a-hash"),
])
def test_gdw_contradictory_anchor_evidence_is_rejected(valid_report, field, invalid):
    for kind in ("original_historical_anchor", "candidate_historical_anchor"):
        valid_report["databases"]["gdw"][kind][field] = invalid
    assert not classify(valid_report)[1]


@pytest.mark.parametrize("field,invalid", [
    ("signature_verification", "VERIFIED_PINNED_PUBLIC_KEY"), ("storage_created_at_unchanged", False),
    ("minimum_receipt_count", 1), ("minimum_receipt_count", True),
    ("receipt_count", 1), ("receipt_count", True), ("receipt_count", 1_000_001),
])
def test_series_a_contradictory_anchor_evidence_is_rejected(valid_report, field, invalid):
    for kind in ("original_historical_anchor", "candidate_historical_anchor"):
        valid_report["databases"]["series_a"][kind][field] = invalid
    assert not classify(valid_report)[1]


@pytest.mark.parametrize("label,field", [
    ("gdw", "signature_verification"), ("gdw", "pinned_key_der_sha256"), ("gdw", "chain_sha256"),
    ("gdw", "audit_scope_unchanged"), ("gdw", "report_payload_bindings_verified"), ("gdw", "payload_sha256"),
    ("series_a", "signature_verification"), ("series_a", "storage_created_at_unchanged"),
    ("series_a", "minimum_receipt_count"), ("series_a", "receipt_count"),
])
def test_complete_producer_anchor_evidence_is_required(valid_report, label, field):
    for kind in ("original_historical_anchor", "candidate_historical_anchor"):
        del valid_report["databases"][label][kind][field]
    assert not classify(valid_report)[1]


@pytest.mark.parametrize("label,field", [("gdw", "generation_unchanged"), ("gdw", "sequence"),
                                        ("series_a", "storage_created_at_unchanged"),
                                        ("series_a", "minimum_receipt_count")])
def test_candidate_anchor_must_preserve_json_types(valid_report, label, field):
    candidate = valid_report["databases"][label]["candidate_historical_anchor"]
    candidate[field] = int(candidate[field]) if type(candidate[field]) is bool else float(candidate[field])
    assert not classify(valid_report)[1]


@pytest.mark.parametrize("field,invalid", [
    ("classification", "OTHER_SQLITE_INTEGRITY_ERROR"), ("integrity_check_complete", False),
    ("unreferenced_page_count", 1), ("unreferenced_page_count", False), ("result_sha256", "invalid"),
    ("foreign_key_violation_count", 1), ("foreign_key_violation_count", False),
    ("foreign_key_check_complete", False),
])
def test_candidate_integrity_must_be_complete(valid_report, field, invalid):
    valid_report["databases"]["gdw"]["candidate_integrity"][field] = invalid
    assert not classify(valid_report)[1]


@pytest.mark.parametrize("change", [{"exit_code": 2}, {"exit_code": False}, {"expected_sha": "b" * 40},
                                    {"expected_sha": PRIVATE}, {"run_id": PRIVATE}, {"run_attempt": "0"}])
def test_execution_context_must_match(valid_report, change):
    public, verified = classify(valid_report, **change)
    assert not verified
    assert_blocked(public)


@pytest.mark.parametrize("report", [None, [], "private", 0, {}])
def test_malformed_report_is_safe(report):
    public, verified = classify(report)
    assert not verified
    assert_blocked(public)


def test_capture_byte_change_invalidates_source_anchor(valid_report, tmp_path, monkeypatch):
    changed = tmp_path / "changed-capture.json"
    changed.write_bytes(c.CAPTURE_PATH.read_bytes() + b" ")
    monkeypatch.setattr(c, "CAPTURE_PATH", changed)
    assert not classify(valid_report)[1]


def test_changed_source_historical_anchor_fails(valid_report, tmp_path, monkeypatch):
    anchors = json.loads(c.ANCHORS_PATH.read_bytes())
    anchors["artifact_archive_sha256"] = "b" * 64
    changed = tmp_path / "changed-anchors.json"
    changed.write_text(json.dumps(anchors), encoding="utf-8")
    monkeypatch.setattr(c, "ANCHORS_PATH", changed)
    assert not classify(valid_report)[1]


def run_cli(tmp_path, monkeypatch, payload):
    source, output = tmp_path / "private.json", tmp_path / "public.json"
    source.write_bytes(payload)
    monkeypatch.setattr(sys, "argv", ["classifier", "--report", str(source), "--output", str(output),
        "--expected-source-sha", SOURCE, "--run-id", "123456", "--run-attempt", "1",
        "--qualification-exit-code", "0"])
    result = c.main()
    return result, json.loads(output.read_text(encoding="utf-8"))


def test_cli_valid_report(valid_report, tmp_path, monkeypatch, capsys):
    valid_report["provider_error"] = PRIVATE
    result, public = run_cli(tmp_path, monkeypatch, json.dumps(valid_report).encode())
    assert result == 0
    assert PRIVATE not in capsys.readouterr().out
    assert_blocked(public)


@pytest.mark.parametrize("payload", [b"{", b"\xff", b'{"state":1,"state":2}', b'{"x":NaN}',
                                     b"x" * (c.MAX_INPUT_BYTES + 1), b"[" * 2000],
                         ids=["invalid-json", "invalid-utf8", "duplicate-key", "non-finite", "oversized", "deep"])
def test_cli_rejects_malformed_or_unbounded_input(tmp_path, monkeypatch, payload, capsys):
    result, public = run_cli(tmp_path, monkeypatch, payload)
    assert result == 1
    assert public["historical_rehearsal_state"] == "NOT_VERIFIED"
    assert PRIVATE not in capsys.readouterr().out
    assert_blocked(public)
