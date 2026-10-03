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
        "checks": {"check_runs": [
            {"id": number, "name": name, "head_sha": REVISION,
             "status": "completed", "conclusion": "success",
             "app": {"slug": "github-actions"}}
            for number, name in enumerate(REQUIRED, 1)
        ]},
    }
    requests = []
    def request(path):
        requests.append(path)
        if path.endswith("/commits/main"):
            return copy.deepcopy(state["head"])
        assert f"/commits/{REVISION}/check-runs" in path
        return copy.deepcopy(state["checks"])
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
    assert len(requests) == 2


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
    if mutation == "missing": state["checks"]["check_runs"].remove(row)
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
    state["checks"]["check_runs"].append(duplicate)
    with pytest.raises(RuntimeError): publisher.resolve_verified_source_tip()
    state["head"]["sha"] = REVISION
    state["head"]["commit"]["verification"]["verified"] = False
    with pytest.raises(RuntimeError): publisher.require_current_source(REVISION)


def test_main_carries_one_qualified_revision_through_every_phase(publisher, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(publisher, "token_from_env", lambda: ("fixture", "FIXTURE"))
    monkeypatch.setattr(publisher, "HfApi", lambda **kwargs: object())
    phases = []
    def resolve():
        phases.append("resolve")
        return REVISION, {"revision": REVISION, "verified_commit": True}
    monkeypatch.setattr(publisher, "resolve_verified_source_tip", resolve)
    def phase(name, result=None):
        def call(*args, revision):
            assert revision == REVISION
            phases.append(name)
            if name == "deploy": args[2].write_text(json.dumps({"github_sha": revision}))
            return result
        return call
    monkeypatch.setattr(publisher, "checkout_exact_source", phase("checkout"))
    monkeypatch.setattr(publisher, "fetch_pinned_controller", lambda path: phases.append("controller"))
    monkeypatch.setattr(publisher, "require_current_source", lambda revision: phases.append("recheck") if revision == REVISION else pytest.fail())
    monkeypatch.setattr(publisher, "ensure_runtime_configuration", phase("configure", {"source_variable_value": REVISION}))
    monkeypatch.setattr(publisher, "deploy_with_controller", phase("deploy"))
    monkeypatch.setattr(publisher, "verify_contract", phase("verify", {"complete": True}))
    assert publisher.main() == 0
    receipt = json.loads((tmp_path / "hf-lyte-enterprise-receipt.json").read_text())
    assert receipt["source_revision"] == REVISION
    assert receipt["source_resolution"]["revision"] == REVISION
    assert receipt["deployment_manifest"]["github_sha"] == REVISION
    assert phases == ["resolve", "checkout", "controller", "recheck", "configure", "deploy", "verify", "recheck"]
    journal = receipt["release_journal"]
    assert journal["schema"] == "szl.release-journal-summary/v1"
    assert journal["execution_authority"] == "NONE"
    assert journal["signature_verified"] is False
    assert journal["complete"] is True
    assert journal["failed"] is False
    assert journal["source_revision"] == REVISION
    assert tuple(journal["required_phases"]) == publisher.WRITER_PHASES
    assert tuple(journal["completed_phases"]) == publisher.WRITER_PHASES
    assert receipt["raw_output_recorded"] is False
    assert receipt["execution_authority"] == "NONE"


def test_admission_failure_leaves_no_mutation_and_retains_failure_receipt(publisher, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(publisher, "token_from_env", lambda: ("fixture", "FIXTURE"))
    monkeypatch.setattr(publisher, "resolve_verified_source_tip", lambda: (_ for _ in ()).throw(RuntimeError("source gate failed")))
    monkeypatch.setattr(publisher, "HfApi", lambda **kwargs: pytest.fail("admission must precede Hub mutation client"))
    assert publisher.main() == 1
    receipt = json.loads((tmp_path / "hf-lyte-enterprise-receipt.json").read_text())
    assert receipt["complete"] is False
    assert receipt["source_revision"] == "UNRESOLVED"
    assert "source gate failed" in receipt["error"]


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
    assert "options: [finance, lyte, terra, sentra, counsel, estate]" in workflow
    assert "hf-lyte-enterprise-manifest.failed.json" in workflow
    contract = (ROOT / ".github/workflows/hf-lyte-enterprise-contract.yml").read_text()
    assert contract.count("tests/test_lyte_publisher_source_resolution.py") == 2
