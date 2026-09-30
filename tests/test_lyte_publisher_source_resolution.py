#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Deterministic admission/receipt regressions, not live publication evidence."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40
REQUIRED = (
    "python-compile", "lint", "unit", "api-contract", "release-gates",
    "database-migrations", "connector-contract", "truth-and-governance",
    "security-scan", "secret-scan", "frontend-static-contract", "accessibility",
    "responsive-overflow", "bundle-budget", "container-build", "container-smoke",
    "source-binding",
)


def load(name, path, monkeypatch):
    hub = ModuleType("huggingface_hub")
    hub.HfApi = type("HfApi", (), {})
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def publisher(monkeypatch):
    return load("lyte_resolution_fixture", "scripts/hf_publish_lyte_enterprise.py", monkeypatch)


def source_responses(publisher, monkeypatch):
    state = {
        "head": {"sha": REVISION, "commit": {"verification": {"verified": True}}},
        "checks": {"total_count": len(REQUIRED), "check_runs": [
            {"id": number, "name": name, "head_sha": REVISION,
             "status": "completed", "conclusion": "success",
             "app": {"id": 15368, "slug": "github-actions"}}
            for number, name in enumerate(REQUIRED, 1)
        ]},
        "run": {"id": 123, "run_attempt": 1, "head_sha": REVISION,
                "event": "push", "head_branch": "main", "workflow_id": 345363884,
                "repository": {"full_name": "szl-holdings/lyte-services"},
                "status": "completed", "conclusion": "success"},
        "jobs": {"total_count": len(REQUIRED), "jobs": [
            {"id": number, "name": name, "head_sha": REVISION, "run_id": 123,
             "run_attempt": 1, "status": "completed", "conclusion": "success"}
            for number, name in enumerate(REQUIRED, 1)
        ]},
    }
    requests = []
    def request(path):
        requests.append(path)
        if path.endswith("/commits/main"):
            return copy.deepcopy(state["head"])
        if path.endswith("/git/ref/heads/main"):
            return {"object": {"sha": state["head"]["sha"]}}
        if f"/commits/{REVISION}/check-runs" in path:
            return copy.deepcopy(state["checks"])
        if "/actions/workflows/compiler.yml/runs" in path:
            return {"total_count": 1, "workflow_runs": [copy.deepcopy(state["run"])]}
        if path.endswith("/actions/runs/123"):
            return copy.deepcopy(state["run"])
        if "/actions/runs/123/attempts/1/jobs" in path:
            return copy.deepcopy(state["jobs"])
        pytest.fail("unexpected GitHub evidence path: " + path)
    monkeypatch.setattr(publisher, "github_json", request)
    return state, requests


def test_verified_current_tip_and_all_source_gates_are_bound_once(publisher, monkeypatch):
    state, requests = source_responses(publisher, monkeypatch)
    revision, evidence = publisher.resolve_verified_source_tip()
    assert revision == REVISION
    assert evidence["revision"] == REVISION
    assert evidence["verified_commit"] is True
    assert tuple(publisher.SOURCE_REQUIRED_CHECKS) == REQUIRED
    assert tuple(evidence["required_checks"]) == REQUIRED
    assert evidence["live_health_check_used_as_source_gate"] is False
    assert evidence["check_app_id"] == 15368 and evidence["pagination_complete"] is True
    assert evidence["run_id"] == 123 and evidence["run_attempt"] == 1
    assert evidence["source_qualification"]["passed"] is True
    assert len(requests) == 7


def test_checks_from_wrong_numeric_app_identity_are_not_source_authority(publisher, monkeypatch):
    state, _ = source_responses(publisher, monkeypatch)
    state["checks"]["check_runs"][0]["app"]["id"] = 42
    with pytest.raises(RuntimeError): publisher.resolve_verified_source_tip()


@pytest.mark.parametrize("mutation", ["wrong-attempt", "wrong-job-head", "failed-job", "skipped-job", "wrong-repository", "wrong-workflow", "wrong-run-id"])
def test_passing_check_names_cannot_hide_unbound_native_job_evidence(publisher, monkeypatch, mutation):
    state, _ = source_responses(publisher, monkeypatch)
    row = state["jobs"]["jobs"][0]
    if mutation == "wrong-attempt": row["run_attempt"] = 2
    elif mutation == "wrong-job-head": row["head_sha"] = "b" * 40
    elif mutation == "failed-job": row["conclusion"] = "failure"
    elif mutation == "skipped-job": row["conclusion"] = "skipped"
    elif mutation == "wrong-repository": state["run"]["repository"]["full_name"] = "other/repo"
    elif mutation == "wrong-workflow": state["run"]["workflow_id"] = 1
    else: row["run_id"] = 124
    with pytest.raises(RuntimeError): publisher.resolve_verified_source_tip()


def test_all_native_collection_pages_are_required(publisher, monkeypatch):
    paths = []
    def page(path):
        paths.append(path)
        items = [{"id": index} for index in (range(1, 101) if path.endswith("page=1") else [101])]
        return {"total_count": 101, "jobs": items}
    monkeypatch.setattr(publisher, "github_json", page)
    assert len(publisher.github_rows("/repos/owner/repo/actions/jobs", "jobs")) == 101
    assert len(paths) == 2 and paths[1].endswith("page=2")


@pytest.mark.parametrize("payload", [
    {"jobs": [], "total_count": 1}, {"jobs": [{"id": 1}], "total_count": 2},
    {"jobs": [{"id": 1}, {"id": 1}], "total_count": 2},
    {"jobs": [{"id": True}], "total_count": 1},
    {"jobs": [], "total_count": 2001}, {"jobs": [], "total_count": False},
])
def test_missing_duplicate_or_excessive_native_collection_cannot_qualify(publisher, monkeypatch, payload):
    monkeypatch.setattr(publisher, "github_json", lambda path: payload)
    with pytest.raises(RuntimeError): publisher.github_rows("/repos/owner/repo/actions/jobs", "jobs")


@pytest.mark.parametrize("mutation", ["unsigned", "missing-signature", "missing-sha", "bad-sha", "zero-sha"])
def test_unverified_or_malformed_tip_is_rejected_before_checks(publisher, monkeypatch, mutation):
    state, requests = source_responses(publisher, monkeypatch)
    if mutation == "unsigned": state["head"]["commit"]["verification"]["verified"] = False
    elif mutation == "missing-signature": state["head"].pop("commit")
    elif mutation == "missing-sha": state["head"].pop("sha")
    elif mutation == "zero-sha": state["head"]["sha"] = "0" * 40
    else: state["head"]["sha"] = "main"
    with pytest.raises(RuntimeError): publisher.resolve_verified_source_tip()
    assert len(requests) == 1


@pytest.mark.parametrize("name", REQUIRED)
@pytest.mark.parametrize("mutation", ["missing", "failure", "pending", "skipped", "wrong-head", "wrong-app"])
def test_every_required_source_gate_must_pass_on_the_resolved_revision(publisher, monkeypatch, name, mutation):
    state, _ = source_responses(publisher, monkeypatch)
    row = next(row for row in state["checks"]["check_runs"] if row["name"] == name)
    if mutation == "missing":
        state["checks"]["check_runs"].remove(row)
        state["checks"]["total_count"] -= 1
    elif mutation == "failure": row["conclusion"] = "failure"
    elif mutation == "pending": row["status"] = "in_progress"
    elif mutation == "skipped": row["conclusion"] = "skipped"
    elif mutation == "wrong-head": row["head_sha"] = "b" * 40
    else: row["app"]["slug"] = "untrusted-check"
    with pytest.raises(RuntimeError): publisher.resolve_verified_source_tip()


def test_recheck_rejects_new_default_tip_or_unsigned_tip(publisher, monkeypatch):
    state, _ = source_responses(publisher, monkeypatch)
    publisher.require_current_source(REVISION)
    state["head"]["sha"] = "b" * 40
    with pytest.raises(RuntimeError): publisher.require_current_source(REVISION)


def test_conflicting_required_check_cannot_be_masked_by_a_success(publisher, monkeypatch):
    state, _ = source_responses(publisher, monkeypatch)
    duplicate = copy.deepcopy(state["checks"]["check_runs"][0])
    duplicate["conclusion"] = "failure"
    duplicate["id"] = 100
    state["checks"]["check_runs"].append(duplicate)
    state["checks"]["total_count"] += 1
    with pytest.raises(RuntimeError): publisher.resolve_verified_source_tip()
    state["head"]["sha"] = REVISION
    state["head"]["commit"]["verification"]["verified"] = False
    with pytest.raises(RuntimeError): publisher.require_current_source(REVISION)


def test_main_carries_one_qualified_revision_through_every_phase(publisher, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(publisher, "token_from_env", lambda: ("fixture", "FIXTURE"))
    monkeypatch.setattr(publisher, "HfApi", lambda **kwargs: object())
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    phases = []
    def resolve():
        phases.append("resolve")
        return REVISION, {"revision": REVISION, "verified_commit": True}
    monkeypatch.setattr(publisher, "resolve_verified_source_tip", resolve)
    def phase(name, result=None):
        def call(*args, revision, **kwargs):
            assert revision == REVISION
            phases.append(name)
            if name == "deploy": args[2].write_text(json.dumps({"github_sha": revision}))
            return result
        return call
    monkeypatch.setattr(publisher, "checkout_exact_source", phase("checkout"))
    monkeypatch.setattr(publisher, "fetch_pinned_controller", lambda path: phases.append("controller"))
    monkeypatch.setattr(publisher, "require_current_source", lambda revision: phases.append("recheck") if revision == REVISION else pytest.fail())
    monkeypatch.setattr(publisher, "require_current_publisher", lambda revision: None)
    monkeypatch.setattr(publisher, "controller_preflight", phase("preflight", {
        "manifest_sha256": "c" * 64, "source_marker": {"generated_from_source_sha": True}}))
    monkeypatch.setattr(publisher, "snapshot_previous", lambda api: {"expected_hf_parent": "d" * 40})
    monkeypatch.setattr(publisher, "require_published_commit", lambda *args, **kwargs: {
        "hf_commit_oid": "e" * 40, "current_target_matched": True})
    monkeypatch.setattr(publisher, "ensure_runtime_configuration", phase("configure", {"source_variable_value": REVISION}))
    monkeypatch.setattr(publisher, "deploy_with_controller", phase("deploy"))
    monkeypatch.setattr(publisher, "restart_with_controller", lambda *args: phases.append("restart"))
    monkeypatch.setattr(publisher, "attest_with_controller", lambda *args: phases.append("attest"))
    monkeypatch.setattr(publisher, "read_manifest", lambda *args, **kwargs: {"github_sha": REVISION})
    monkeypatch.setattr(publisher, "verify_contract", phase("verify", {"complete": True}))
    assert publisher.main() == 0
    receipt = json.loads((tmp_path / "hf-lyte-enterprise-receipt.json").read_text())
    assert receipt["source_revision"] == REVISION
    assert receipt["source_resolution"]["revision"] == REVISION
    assert receipt["deployment_manifest"]["github_sha"] == REVISION
    assert phases == ["resolve", "checkout", "controller", "preflight", "recheck", "deploy",
                      "recheck", "configure", "recheck", "restart", "attest", "verify", "recheck"]
    assert receipt["release_journal"]["complete"] is True


def test_admission_failure_leaves_no_mutation_and_retains_failure_receipt(publisher, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(publisher, "token_from_env", lambda: ("fixture", "FIXTURE"))
    monkeypatch.setattr(publisher, "resolve_verified_source_tip", lambda: (_ for _ in ()).throw(RuntimeError("source gate failed")))
    monkeypatch.setattr(publisher, "HfApi", lambda **kwargs: pytest.fail("admission must precede Hub mutation client"))
    assert publisher.main() == 1
    receipt = json.loads((tmp_path / "hf-lyte-enterprise-receipt.json").read_text())
    assert receipt["complete"] is False
    assert receipt["source_revision"] == "UNRESOLVED"
    assert receipt["error"] == "RuntimeError"
    assert receipt["state"] == "FAILED"


def test_lyte_only_scope_uses_existing_writer_and_rejects_failed_or_unbound_receipt(monkeypatch, tmp_path):
    wrapper = load("lyte_scope_fixture", "scripts/hf_publish_vertical_flagships_v4.py", monkeypatch)
    monkeypatch.chdir(tmp_path)
    calls = []
    receipt = {"complete": True, "source_repository": "szl-holdings/lyte-services",
               "source_revision": REVISION, "source_resolution": {
                   "schema": "szl.lyte-source-resolution/v1", "repository": "szl-holdings/lyte-services",
                   "branch": "main", "revision": REVISION, "verified_commit": True}}
    def run(name, path):
        calls.append(name)
        (tmp_path / "hf-lyte-enterprise-receipt.json").write_text(json.dumps(receipt))
        return 0, None, None
    monkeypatch.setattr(wrapper, "run_publisher", run)
    guard = type("Guard", (), {"guard_report": staticmethod(lambda: {})})
    assert wrapper.publish_lyte_only(guard) == 0
    batch = json.loads((tmp_path / "hf-vertical-flagships-receipt.json").read_text())
    assert batch["publication_scope"] == "lyte" and batch["sibling_publications"] == 0
    assert batch["source_revision"] == REVISION
    assert calls == ["szl_lyte_enterprise"]
    for change in ("unverified", "wrong-revision", "wrong-repo", "failure"):
        candidate = copy.deepcopy(receipt)
        if change == "unverified": candidate["source_resolution"]["verified_commit"] = False
        elif change == "wrong-revision": candidate["source_resolution"]["revision"] = "b" * 40
        elif change == "wrong-repo": candidate["source_repository"] = "other/repo"
        else: candidate["complete"] = False
        monkeypatch.setattr(wrapper, "read_receipt", lambda path, row=candidate: row)
        assert wrapper.publish_lyte_only(guard) == 1


def test_workflow_exposes_focused_scope_and_retains_partial_lyte_manifest():
    workflow = (ROOT / ".github/workflows/hf-publish-vertical-flagships.yml").read_text()
    assert "options: [finance, lyte, estate]" in workflow
    assert "hf-lyte-enterprise-manifest.failed.json" in workflow
    contract = (ROOT / ".github/workflows/hf-lyte-enterprise-contract.yml").read_text()
    assert contract.count("tests/test_lyte_publisher_source_resolution.py") == 2
    assert contract.count("tests/test_lyte_release_transaction.py") == 2
