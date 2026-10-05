#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline native triage tests: no fake publication receipt, secrets or provider writes."""

import ast
import hashlib
import json
from pathlib import Path
import sqlite3
import time

import pytest
import yaml

from scripts import triage_gdw_artifacts_readonly as triage
from tests.test_gdw_durable_runtime import stores
from tests.test_gdw_durable_artifacts import exported, copy_database


def test_retained_rows_reach_blocked_callback_without_upload_or_database_change(stores, tmp_path):
    exported(stores)
    database = copy_database(stores, tmp_path)
    before = database.read_bytes()
    count = len(stores.artifact_publications)
    observed = triage.local_artifact_observation(database, tmp_path / "read-only-local", time.monotonic() + 10,
                                                logical_roots=stores.gate.artifacts.roots)
    assert observed == {"state": "OBSERVED", "diagnostic_code": "LOCAL_ROWS_VALIDATED_PUBLICATION_NOT_ATTEMPTED",
                        "publication_callback_reached": True, "candidate_unchanged": True}
    assert stores.artifact_publications[count:] == []
    assert database.read_bytes() == before


def test_invalid_record_is_diagnosed_before_callback_without_leaking_payload(stores, tmp_path):
    exported(stores)
    database = copy_database(stores, tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE effect_outbox SET artifact_json=? WHERE status='EXPORTED'",
                           (json.dumps({"private_test_marker": "do-not-disclose-private-owner"}),))
    before = database.read_bytes()
    observed = triage.local_artifact_observation(database, tmp_path / "invalid-local", time.monotonic() + 10,
                                                logical_roots=stores.gate.artifacts.roots)
    assert observed["state"] == "HELD" and observed["diagnostic_code"] == "ARTIFACT_RECONSTRUCTION_MISMATCH"
    assert observed["publication_callback_reached"] is False and observed["candidate_unchanged"] is True
    assert "do-not-disclose" not in json.dumps(observed)
    assert database.read_bytes() == before


def test_empty_retained_set_does_not_claim_artifact_publication(stores, tmp_path):
    database = copy_database(stores, tmp_path)
    observed = triage.local_artifact_observation(database, tmp_path / "empty-local", time.monotonic() + 10,
                                                logical_roots=stores.gate.artifacts.roots)
    assert observed["diagnostic_code"] == "NO_RETAINED_ARTIFACTS"
    assert observed["publication_callback_reached"] is False


def environment():
    source = "a" * 40
    return source, {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": triage.REPOSITORY,
        "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "triage", "GITHUB_SHA": source,
        "GITHUB_WORKFLOW_SHA": source, "GITHUB_RUN_ID": "900",
        "GITHUB_WORKFLOW_REF": f"{triage.REPOSITORY}/{triage.WORKFLOW}@refs/heads/main"}


@pytest.mark.parametrize("key,value", [("GITHUB_ACTIONS", "false"), ("GITHUB_REPOSITORY", "other/repo"),
    ("GITHUB_REF", "refs/heads/other"), ("GITHUB_EVENT_NAME", "push"), ("GITHUB_RUN_ATTEMPT", "2"),
    ("GITHUB_JOB", "other"), ("GITHUB_SHA", "b" * 40), ("GITHUB_WORKFLOW_SHA", "b" * 40),
    ("GITHUB_RUN_ID", "0"), ("GITHUB_WORKFLOW_REF", "untrusted")])
def test_invalid_context_never_admits_private_reads(key, value):
    source, env = environment()
    env[key] = value
    with pytest.raises(triage.TriageHeld):
        triage.native_context(env, source)


def test_exact_native_context():
    source, env = environment()
    assert triage.native_context(env, source) == {"source_revision": source, "run_id": 900, "run_attempt": 1}


@pytest.mark.parametrize("bad", ["main", "", "A" * 40, "a" * 39, "a" * 41])
def test_source_must_be_exact_lowercase_commit(bad):
    _source, env = environment()
    with pytest.raises(triage.TriageHeld):
        triage.native_context(env, bad)


def test_triage_source_has_no_provider_mutator_and_uses_real_readonly_qualification():
    source = Path(triage.__file__).read_text()
    tree = ast.parse(source)
    calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not calls & {"pause_space", "restart_space", "resume_space", "add_bucket_files", "copy_bucket_files",
        "delete_repo", "delete_file", "create_commit", "upload_file", "upload_folder", "sync_bucket", "publish_artifact"}
    assert "recovery.ReadOnlyCaptureHub(api)" in source
    assert "qualified.get(\"provider_writes_performed\") is False" in source
    callback = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "stop_before_publication")
    assert not any(isinstance(node, ast.Return) for node in ast.walk(callback))
    assert any(isinstance(node, ast.Raise) for node in ast.walk(callback))


def test_workflow_only_manual_triage_with_fixed_artifact_and_no_publish_path():
    raw = (triage.ROOT / triage.WORKFLOW).read_text()
    workflow = yaml.safe_load(raw)
    triggers = workflow.get("on", workflow.get(True))
    assert set(triggers) == {"pull_request", "workflow_dispatch"}
    jobs = workflow["jobs"]
    assert set(jobs) == {"contract", "triage"}
    job = jobs["triage"]
    assert job["needs"] == "contract"
    assert job["permissions"] == {"contents": "read", "actions": "read"}
    for required in ["github.event_name == 'workflow_dispatch'", "github.ref == 'refs/heads/main'",
                     "github.sha == inputs.source_sha", "github.run_attempt == 1"]:
        assert required in job["if"]
    assert all("continue-on-error" not in step for step in job["steps"])
    upload = [step for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(upload) == 1 and upload[0]["with"]["path"] == "${{ runner.temp }}/gdw-artifact-triage.json"
    assert not any(key in jobs["contract"].get("env", {}) for key in ("HF_TOKEN", "GH_TOKEN"))


def test_native_triage_roots_match_reviewed_worker_not_caller(monkeypatch):
    from gdw_durable_artifacts import LOGICAL_ROOTS
    monkeypatch.setenv("GDW_PROOF_DIR", "/untrusted/proofs")
    monkeypatch.setenv("GDW_RECEIPT_PROJECTION_DIR", "/untrusted/receipts")
    assert triage.trusted_artifact_environment() == {
        "GDW_PROOF_DIR": str(LOGICAL_ROOTS["proof_export"]),
        "GDW_RECEIPT_PROJECTION_DIR": str(LOGICAL_ROOTS["receipt_projection"]),
    }
    assert "os.environ.update(trusted_artifact_environment())" in Path(triage.__file__).read_text()
