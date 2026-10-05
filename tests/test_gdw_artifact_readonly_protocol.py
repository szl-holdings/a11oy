#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Portable closed protocol/import controls; no private stores or provider SDK."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import triage_gdw_artifacts_readonly as triage


def effects(expected=224, present=0):
    return {"expected_object_count": expected, "expected_object_set_sha256": "a" * 64,
        "candidate_unchanged": True, "all_retained_rows_validated": True,
        "classification": ("NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME" if not present else
            "PARTIAL_EXPECTED_OBJECT_SET_PRESENT_AT_READ_TIME" if present < expected else
            "ALL_EXPECTED_OBJECTS_PRESENT_AND_VALIDATED_AT_READ_TIME"),
        "present_object_count": present, "missing_object_count": expected - present,
        "observed_object_set_sha256": triage._aggregate([]) if not present else "b" * 64,
        "provider_objects_fully_validated": present == expected,
        "provider_writes_performed": False, "historical_writer_attribution": "NOT_ESTABLISHED"}


def request():
    return {"schema": triage.OBJECT_WORKER_SCHEMA, "workspace": "/tmp/gdw-readonly-triage-synthetic",
        "source_revision": "c" * 40, "candidate_sha256": "d" * 64,
        "run_id": 900, "run_attempt": 1, "deadline": 200.0}


def report(expected=224, present=0):
    binding = {key: request()[key] for key in ("source_revision", "candidate_sha256", "run_id", "run_attempt")}
    return {**triage._held_object_worker_report(), **binding, "state": "OBSERVED",
            "artifact_effect_observation": effects(expected, present)}


@pytest.mark.parametrize("expected,present", [(1, 0), (224, 0), (224, 1), (224, 224), (4096, 4096)])
def test_v2_counts_and_attribution_survive_closed_positive_wire(expected, present):
    value = report(expected, present)
    raw = triage.encode_object_worker_report(value)
    assert raw.endswith(b"\n") and len(raw) < triage.OBJECT_WORKER_BYTES
    assert triage.decode_object_worker_report(raw) == value
    assert value["artifact_effect_observation"]["historical_writer_attribution"] == "NOT_ESTABLISHED"
    assert all(value[key] is False for key in
        ("provider_writes_performed", "retry_admitted", "restore_admitted", "deployment_admitted"))


def test_closed_held_record_has_no_success_identity_or_effect_claim():
    value = triage._held_object_worker_report()
    assert triage.decode_object_worker_report(triage.encode_object_worker_report(value)) == value
    assert value["state"] == "HELD" and value["artifact_effect_observation"] is None


@pytest.mark.parametrize("field,value", [
    ("expected_object_count", 0), ("expected_object_count", 4097), ("expected_object_count", True),
    ("present_object_count", -1), ("present_object_count", 225), ("present_object_count", 0.0),
    ("missing_object_count", 223), ("missing_object_count", True),
    ("candidate_unchanged", False), ("all_retained_rows_validated", 1),
    ("provider_writes_performed", True), ("historical_writer_attribution", "CONFIRMED"),
    ("provider_objects_fully_validated", True), ("provider_objects_fully_validated", 0),
    ("classification", "UNKNOWN"), ("expected_object_set_sha256", "0" * 64),
    ("observed_object_set_sha256", "b" * 64), ("expected_object_set_sha256", "A" * 64)])
def test_effect_payload_requires_complete_current_v2_contract(field, value):
    item = effects()
    item[field] = value
    with pytest.raises(triage.TriageHeld):
        triage.validate_artifact_effect_observation(item)


@pytest.mark.parametrize("field", list(effects()))
def test_every_effect_field_is_required(field):
    value = effects()
    del value[field]
    with pytest.raises(triage.TriageHeld):
        triage.validate_artifact_effect_observation(value)


@pytest.mark.parametrize("field,value", [
    ("schema", "other"), ("workspace", None), ("workspace", ""), ("workspace", "x" * 1025),
    ("workspace", "private\npath"), ("workspace", "private\rpath"), ("workspace", "private\0path"),
    ("source_revision", "main"), ("source_revision", "0" * 40), ("source_revision", "C" * 40),
    ("candidate_sha256", "d" * 63), ("candidate_sha256", "0" * 64), ("candidate_sha256", True),
    ("run_id", True), ("run_id", 0), ("run_id", 2**63), ("run_attempt", True), ("run_attempt", 2),
    ("deadline", True), ("deadline", "200"), ("deadline", float("inf")), ("deadline", float("nan")),
    ("deadline", 100), ("deadline", 311)])
def test_request_rejects_unbound_identity_type_or_budget(field, value):
    item = request()
    item[field] = value
    with pytest.raises(triage.TriageHeld):
        triage.validate_object_worker_request(item, now=100)


@pytest.mark.parametrize("field", list(request()))
def test_request_requires_every_field(field):
    item = request()
    del item[field]
    with pytest.raises(triage.TriageHeld):
        triage.validate_object_worker_request(item, now=100)


def test_valid_request_is_detached_and_maximum_budget_is_explicit():
    item = request()
    item["deadline"] = 100 + triage.OBJECT_WORKER_SECONDS
    result = triage.validate_object_worker_request(item, now=100)
    assert result == item and result is not item


@pytest.mark.parametrize("kind", ["effect", "report", "request"])
def test_no_protocol_shape_accepts_private_extras_or_nonobject(kind):
    factory, validator = {"effect": (effects, triage.validate_artifact_effect_observation),
        "report": (report, triage.validate_object_worker_report),
        "request": (request, lambda v: triage.validate_object_worker_request(v, now=100))}[kind]
    for item in (None, [], {**factory(), "private-provider-field": "must-not-pass"}):
        with pytest.raises(triage.TriageHeld):
            validator(item)


@pytest.mark.parametrize("field,value", [("state", "UNKNOWN"), ("state", "HELD"),
    ("source_revision", None), ("candidate_sha256", "0" * 64), ("run_id", True),
    ("run_attempt", 2), ("retry_admitted", True), ("provider_writes_performed", 0),
    ("artifact_effect_observation", None)])
def test_worker_report_cannot_fabricate_binding_or_admission(field, value):
    item = report()
    item[field] = value
    with pytest.raises(triage.TriageHeld):
        triage.validate_object_worker_report(item)


@pytest.mark.parametrize("field", list(report()))
def test_worker_report_is_closed_and_complete(field):
    item = report()
    del item[field]
    with pytest.raises(triage.TriageHeld):
        triage.validate_object_worker_report(item)


@pytest.mark.parametrize("defect", ["no_lf", "extra_lf", "whitespace", "duplicate", "prefix", "oversize", "array", "nan"])
def test_malformed_or_noncanonical_child_output_is_held(defect):
    raw = triage.encode_object_worker_report(report())
    if defect == "no_lf": raw = raw[:-1]
    elif defect == "extra_lf": raw += b"\n"
    elif defect == "whitespace": raw = b" " + raw
    elif defect == "duplicate": raw = b'{"state":"OBSERVED",' + raw[1:]
    elif defect == "prefix": raw = b"private-provider-output\n" + raw
    elif defect == "oversize": raw += b" " * triage.OBJECT_WORKER_BYTES
    elif defect == "array": raw = b"[]\n"
    else: raw = raw.replace(b'"run_id":900', b'"run_id":NaN')
    with pytest.raises(Exception):
        triage.decode_object_worker_report(raw)


def test_real_isolated_bootstrap_imports_exact_trusted_qualification_helpers(tmp_path):
    code = """
import os, runpy, sys
from pathlib import Path
assert sys.flags.isolated and sys.flags.ignore_environment and sys.dont_write_bytecode
assert 'PYTHONPATH' not in os.environ and 'PYTHONSTARTUP' not in os.environ
source = Path(sys.argv[1]).resolve()
root = source.parents[1]
assert str(root) not in sys.path and str(root / 'scripts') not in sys.path
runpy.run_path(str(source), run_name='isolated_import_regression')
from scripts import qualify_gdw_store_recovery as recovery
assert Path(recovery.__file__).resolve() == root / 'scripts/qualify_gdw_store_recovery.py'
assert Path(recovery.preservation.__file__).resolve() == root / 'scripts/preserve_hf_gdw_store.py'
assert Path(recovery.orphan_forensics.__file__).resolve() == root / 'scripts/gdw_orphan_forensics.py'
assert not {'fcntl', 'huggingface_hub', 'requests'} & set(sys.modules)
sys.stdout.buffer.write(b'ISOLATED_IMPORT_READY\\n')
"""
    env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(Path(triage.__file__).resolve())],
        cwd=tmp_path, env={**env, "PATH": os.defpath}, capture_output=True, timeout=5, check=True)
    assert result.stdout == b"ISOLATED_IMPORT_READY\n" and result.stderr == b""
