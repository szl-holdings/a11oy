#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise refresh races, orphan recovery and truthful failure receipts offline."""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("brain_refresh", ROOT / "scripts/brain_frontier_v7_refresh.py")
assert SPEC and SPEC.loader
refresh = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = refresh
SPEC.loader.exec_module(refresh)


class FakeRunner:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def run(self, args, **kwargs):
        self.calls.append(tuple(args))
        code, payload = self.results.pop(0)
        if not isinstance(payload, str):
            payload = json.dumps(payload)
        if code and kwargs.get("check", True):
            raise refresh.RefreshError("simulated GitHub rejection")
        return refresh.Completed(tuple(args), code, payload, "rejected" if code else "")


def proposal(head="a" * 40, state="OPEN"):
    return {
        "number": 10, "state": state,
        "url": "https://github.com/szl-holdings/a11oy/pull/10",
        "headRefName": refresh.expected_branch("b" * 64),
        "baseRefName": "main", "headRefOid": head,
    }


def test_existing_orphan_gets_a_real_pr_with_readback():
    runner = FakeRunner([(0, []), (0, proposal()["url"]), (0, proposal())])
    state, url = refresh.ensure_review_pr(runner, proposal()["headRefName"], "a" * 40, "b" * 64, "c" * 64, "d" * 40)
    assert state == "NEW_REVIEW_PR" and url == proposal()["url"]
    assert runner.calls[1][:3] == ("gh", "pr", "create")
    assert runner.calls[2][:3] == ("gh", "pr", "view")


def test_existing_open_pr_is_idempotent_and_bound_to_head():
    runner = FakeRunner([(0, [proposal()])])
    state, _ = refresh.ensure_review_pr(runner, proposal()["headRefName"], "a" * 40, "b" * 64, "c" * 64, "d" * 40)
    assert state == "EXISTING_REVIEW_PR" and len(runner.calls) == 1
    with pytest.raises(refresh.RefreshError, match="observed branch head"):
        refresh.choose_pr_action([proposal()], proposal()["headRefName"], "main", "e" * 40)


def test_closed_unmerged_pr_is_reopened_and_verified():
    runner = FakeRunner([(0, [proposal(state="CLOSED")]), (0, ""), (0, proposal())])
    state, _ = refresh.ensure_review_pr(runner, proposal()["headRefName"], "a" * 40, "b" * 64, "c" * 64, "d" * 40)
    assert state == "RECOVERED_REVIEW_PR"
    assert runner.calls[1][:3] == ("gh", "pr", "reopen")


@pytest.mark.parametrize("change", [{"state": "CLOSED"}, {"headRefOid": "e" * 40}, {"url": "https://example.org/pull/10"}, {"baseRefName": "dev"}])
def test_pr_readback_rejects_wrong_identity(change):
    item = proposal() | change
    with pytest.raises(refresh.RefreshError, match="readback"):
        refresh.validate_pr(item, proposal()["headRefName"], "a" * 40)


@pytest.mark.parametrize("response", [(0, {"can_approve_pull_request_reviews": False}), (1, "permission denied"), (0, {})])
def test_bot_policy_is_checked_before_any_write(response):
    runner = FakeRunner([response])
    with pytest.raises(refresh.RefreshError):
        refresh.permissions_preflight(runner, "github-token")
    assert all(call[:2] == ("gh", "api") for call in runner.calls)


def test_external_token_does_not_inherit_bot_policy():
    result = refresh.permissions_preflight(FakeRunner([(0, {"can_approve_pull_request_reviews": False})]), "automation-token")
    assert result["github_token_pr_creation_allowed"] is False
    assert result["write_authority"] == "UNVERIFIED_UNTIL_WRITE_READBACK"


def receipt_args(tmp_path, **changes):
    values = dict(
        proposal=str(tmp_path / "proposal.json"), repository=refresh.REPOSITORY,
        ref="refs/heads/main", event_name="schedule", run_id="100", run_attempt="1",
        run_url="https://github.com/szl-holdings/a11oy/actions/runs/100",
        materialize_result="success", proposal_result="skipped", changed="false",
        source_sha="d" * 40, snapshot_digest="b" * 64, candidate_set="c" * 64,
    )
    return argparse.Namespace(**(values | changes))


@pytest.mark.parametrize("changes", [
    {"materialize_result": "failure"}, {"changed": ""}, {"source_sha": "main"},
    {"changed": "true", "proposal_result": "success"},
    {"proposal_result": "cancelled"}, {"ref": "refs/heads/attacker"},
])
def test_failed_or_missing_evidence_cannot_report_success(tmp_path, changes):
    receipt = refresh.build_receipt(receipt_args(tmp_path, **changes))
    assert receipt["terminal"] is False and receipt["outcome"] == "FAILED_CLOSED"
    path = tmp_path / "receipt.json"
    refresh.write_json(path, receipt)
    with pytest.raises(refresh.RefreshError, match="failed closed"):
        refresh.verify_receipt(path)


def test_no_change_requires_successful_materialization_and_labels_unsigned(tmp_path):
    receipt = refresh.build_receipt(receipt_args(tmp_path))
    assert receipt["terminal"] is True and receipt["outcome"] == "NO_CHANGE"
    assert receipt["signature_state"] == "UNSIGNED"
    path = tmp_path / "receipt.json"
    refresh.write_json(path, receipt)
    refresh.verify_receipt(path)
    receipt["source"]["revision"] = "e" * 40
    refresh.write_json(path, receipt)
    with pytest.raises(refresh.RefreshError, match="digest"):
        refresh.verify_receipt(path)


def test_successful_review_receipt_binds_the_actual_proposal(tmp_path):
    refresh.write_json(tmp_path / "proposal.json", {
        "state": "NEW_REVIEW_PR", "terminal": True,
        "url": proposal()["url"], "branch": refresh.expected_branch("b" * 64),
        "head_sha": "a" * 40, "source_sha": "d" * 40,
        "snapshot_sha256": "b" * 64, "candidate_set_sha256": "c" * 64,
    })
    receipt = refresh.build_receipt(receipt_args(tmp_path, changed="true", proposal_result="success"))
    path = tmp_path / "receipt.json"
    refresh.write_json(path, receipt)
    assert refresh.verify_receipt(path)["outcome"] == "REVIEW_PR_OPEN"


def test_old_orphan_terminal_is_rejected_even_with_a_success_job(tmp_path):
    refresh.write_json(tmp_path / "proposal.json", {
        "state": "EXISTING_BRANCH_NO_FORCE", "terminal": True,
        "url": None, "branch": refresh.expected_branch("b" * 64), "head_sha": "a" * 40,
        "source_sha": "d" * 40, "snapshot_sha256": "b" * 64, "candidate_set_sha256": "c" * 64,
    })
    receipt = refresh.build_receipt(receipt_args(tmp_path, changed="true", proposal_result="success"))
    assert receipt["outcome"] == "FAILED_CLOSED"
    assert "proposal_url_missing_or_invalid" in receipt["failures"]


@pytest.mark.parametrize("section,field,value", [
    ("source", "repository", "other/repository"),
    ("materialization", "changed", "false"),
    ("materialization", "job_result", "failure"),
    ("authority", "execution", "ALLOWED"),
    ("proposal", "state", "EXISTING_BRANCH_NO_FORCE"),
])
def test_recomputed_receipt_cannot_hide_invalid_terminal_semantics(tmp_path, section, field, value):
    receipt = refresh.build_receipt(receipt_args(tmp_path))
    receipt[section][field] = value
    receipt.pop("receipt_sha256")
    receipt["receipt_sha256"] = refresh.sha256(refresh.canonical_bytes(receipt))
    path = tmp_path / "forged.json"
    refresh.write_json(path, receipt)
    with pytest.raises(refresh.RefreshError):
        refresh.verify_receipt(path)


@pytest.fixture
def local_repository(tmp_path):
    remote = tmp_path / "remote.git"
    checkout = tmp_path / "checkout"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "init", "--initial-branch=main", str(checkout)], check=True, capture_output=True)
    runner = refresh.Runner(checkout)
    for key, value in [("user.name", "Refresh tests"), ("user.email", "test@example.org"), ("commit.gpgsign", "false")]:
        runner.run(("git", "config", key, value))
    runner.run(("git", "remote", "add", "origin", str(remote)))
    snapshot = json.loads((ROOT / refresh.SNAPSHOT_PATH).read_text(encoding="utf-8"))
    path = checkout / refresh.SNAPSHOT_PATH
    refresh.write_json(path, snapshot)
    runner.run(("git", "add", "."))
    runner.run(("git", "commit", "-m", "source"))
    runner.run(("git", "push", "origin", "HEAD:main"))
    original = path.read_text(encoding="utf-8")
    snapshot.pop("snapshot_sha256")
    snapshot["test_generation"] = 2
    digest = refresh.sha256(refresh.canonical_bytes(snapshot))
    snapshot["snapshot_sha256"] = digest
    refresh.write_json(path, snapshot)
    candidates = snapshot["sources"]["second_brain"]["candidate_set_sha256"]
    return runner, path, original, snapshot, digest, candidates


def test_real_git_branch_create_reuse_and_advance_preserve_main(local_repository):
    runner, path, original, snapshot, digest, candidates = local_repository
    source = refresh.git_text(runner, "rev-parse", "HEAD")
    branch = refresh.expected_branch(digest)
    tree = refresh.prepare_target_tree(runner)
    head, state = refresh.ensure_review_branch(runner, branch, tree, source, digest, candidates, "https://github.com/szl-holdings/a11oy/actions/runs/100")
    assert state == "CREATED_BRANCH"
    assert refresh.ensure_review_branch(runner, branch, tree, source, digest, candidates, "https://github.com/szl-holdings/a11oy/actions/runs/101") == (head, "REUSED_BRANCH")

    path.write_text(original, encoding="utf-8")
    (runner.cwd / "new-main-file.txt").write_text("new main content", encoding="utf-8")
    runner.run(("git", "add", "."))
    runner.run(("git", "commit", "-m", "main advanced"))
    runner.run(("git", "push", "origin", "HEAD:main"))
    source = refresh.git_text(runner, "rev-parse", "HEAD")
    refresh.write_json(path, snapshot)
    tree = refresh.prepare_target_tree(runner)
    advanced, state = refresh.ensure_review_branch(runner, branch, tree, source, digest, candidates, "https://github.com/szl-holdings/a11oy/actions/runs/102")
    assert state == "ADVANCED_BRANCH"
    assert refresh.git_text(runner, "show", f"{advanced}:new-main-file.txt") == "new main content"
    assert runner.run(("git", "merge-base", "--is-ancestor", head, advanced)).returncode == 0
    assert runner.run(("git", "merge-base", "--is-ancestor", source, advanced)).returncode == 0
    assert refresh.ensure_review_branch(runner, branch, tree, source, digest, candidates, "https://github.com/szl-holdings/a11oy/actions/runs/103") == (advanced, "REUSED_BRANCH")


def test_source_movement_prevents_a_branch_write(local_repository):
    runner, *_ = local_repository
    with pytest.raises(refresh.RefreshError, match="checkout HEAD"):
        refresh.require_exact_main(runner, "e" * 40, "main")


def test_remote_main_movement_prevents_a_branch_write(local_repository):
    runner, *_ = local_repository
    source = refresh.git_text(runner, "rev-parse", "HEAD")
    tree = refresh.git_text(runner, "rev-parse", "HEAD^{tree}")
    newer = refresh.create_commit(runner, tree, source, "new main commit")
    runner.run(("git", "push", "origin", f"{newer}:refs/heads/main"))
    with pytest.raises(refresh.RefreshError, match="main moved"):
        refresh.require_exact_main(runner, source, "main")


def test_existing_branch_with_an_extra_file_is_rejected(local_repository):
    runner, path, original, snapshot, digest, candidates = local_repository
    source = refresh.git_text(runner, "rev-parse", "HEAD")
    (runner.cwd / "unexpected.txt").write_text("out of scope", encoding="utf-8")
    runner.run(("git", "add", "."))
    tree = refresh.git_text(runner, "write-tree")
    commit = refresh.create_commit(runner, tree, source, refresh.commit_message(source, digest, candidates, "run"))
    with pytest.raises(refresh.RefreshError, match="outside the snapshot boundary"):
        refresh.validate_existing_branch(runner, commit, source, digest, candidates)


def test_non_force_push_race_reuses_the_verified_winner(local_repository, monkeypatch):
    runner, path, original, snapshot, digest, candidates = local_repository
    source = refresh.git_text(runner, "rev-parse", "HEAD")
    branch = refresh.expected_branch(digest)
    tree = refresh.prepare_target_tree(runner)
    original_run = runner.run
    raced = []

    def race(args, **kwargs):
        if tuple(args[:3]) == ("git", "push", "--porcelain") and not raced:
            competitor = refresh.create_commit(runner, tree, source, refresh.commit_message(source, digest, candidates, "competing-run"))
            original_run(("git", "push", "origin", f"{competitor}:refs/heads/{branch}"))
            raced.append(competitor)
        return original_run(args, **kwargs)

    monkeypatch.setattr(runner, "run", race)
    head, state = refresh.ensure_review_branch(runner, branch, tree, source, digest, candidates, "our-run")
    assert state == "REUSED_BRANCH" and head == raced[0]


def test_workflow_separates_reader_from_writer_and_always_enforces_receipt():
    workflow = yaml.safe_load((ROOT / ".github/workflows/brain-frontier-v7-refresh.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    reader = workflow["jobs"]["materialize"]
    writer = workflow["jobs"]["proposal"]
    assert "permissions" not in reader
    assert writer["permissions"] == {"contents": "write", "pull-requests": "write"}
    assert writer["needs"] == "materialize" and "always()" in writer["if"]
    for job in [reader, writer]:
        checkout = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@"))
        assert checkout["with"]["persist-credentials"] is False
        assert "github.ref == 'refs/heads/main'" in job["if"]
    assert writer["steps"][-1]["if"] == "always()"
    assert "verify-receipt" in writer["steps"][-1]["run"]
    assert writer["steps"][-2]["uses"].startswith("actions/upload-artifact@")
