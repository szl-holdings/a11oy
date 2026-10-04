#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publication-boundary negative controls; fixtures are not live HF evidence."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "a" * 40
PUBLISHER = "b" * 40
PARENT = "c" * 40
COMMIT = "d" * 40


@pytest.fixture
def writer(monkeypatch):
    hub = ModuleType("huggingface_hub")
    hub.HfApi = type("HfApi", (), {})
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("lyte_transaction_fixture", ROOT / "scripts/hf_publish_lyte_enterprise.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_manifest(writer):
    content = SOURCE + "\n"
    value = {"schema": 2, "github_repo": writer.SOURCE_REPOSITORY,
             "hf_repo": writer.HF_REPOSITORY, "ref": SOURCE, "source_sha": SOURCE,
             "source_revision_file": writer.SOURCE_MARKER, "unresolved_sources": [],
             "files_deployed": 3, "files": {
                 "Dockerfile": {}, "README.md": {}, writer.SOURCE_MARKER: {
                     "generated_from_source_sha": True, "generated_content_utf8": content,
                     "size": len(content), "sha256": hashlib.sha256(content.encode()).hexdigest()}}}
    value["manifest_sha256"] = writer.digest(value)
    return value


@pytest.mark.parametrize("value", ["UNAVAILABLE\n", "e" * 40 + "\n"])
def test_existing_producer_marker_is_bound_before_generated_projection(writer, tmp_path, value):
    marker = tmp_path / writer.SOURCE_MARKER
    marker.write_bytes(value.encode())
    evidence = writer.prepare_source_marker(tmp_path, revision=SOURCE)
    assert not marker.exists()
    assert evidence["original_sha256"] == hashlib.sha256(value.encode()).hexdigest()
    assert evidence["producer_file_modified_remotely"] is False
    assert evidence["generated_from_source_sha"] is True


@pytest.mark.parametrize("value", ["", "not-a-revision", "x" * 257])
def test_invalid_original_marker_cannot_be_replaced(writer, tmp_path, value):
    marker = tmp_path / writer.SOURCE_MARKER
    marker.write_text(value)
    with pytest.raises(RuntimeError): writer.prepare_source_marker(tmp_path, revision=SOURCE)
    assert marker.read_text() == value


def test_only_the_exact_generated_marker_can_be_reset(writer, tmp_path):
    marker = tmp_path / writer.SOURCE_MARKER
    marker.write_bytes(("e" * 40 + "\n").encode())
    with pytest.raises(RuntimeError): writer.reset_generated_marker(tmp_path, revision=SOURCE)
    assert marker.exists()
    marker.write_bytes((SOURCE + "\n").encode())
    writer.reset_generated_marker(tmp_path, revision=SOURCE)
    assert not marker.exists()


@pytest.mark.parametrize("mutation", ["repo", "target", "source", "marker", "marker-digest", "digest", "closure"])
def test_preflight_manifest_requires_source_target_marker_and_complete_digest(writer, tmp_path, mutation):
    manifest = fixture_manifest(writer)
    if mutation == "repo": manifest["github_repo"] = "other/source"
    elif mutation == "target": manifest["hf_repo"] = "SZLHOLDINGS/other"
    elif mutation == "source": manifest["source_sha"] = "e" * 40
    elif mutation == "marker": manifest["files"][writer.SOURCE_MARKER]["generated_from_source_sha"] = False
    elif mutation == "marker-digest": manifest["files"][writer.SOURCE_MARKER]["sha256"] = "0" * 64
    elif mutation == "digest": manifest["manifest_sha256"] = "0" * 64
    else: manifest["files"].pop("Dockerfile")
    if mutation != "digest":
        stable = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
        manifest["manifest_sha256"] = writer.digest(stable)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError): writer.read_manifest(path, revision=SOURCE)


def install_main_fixture(writer, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_SHA", PUBLISHER)
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setattr(writer, "token_from_env", lambda: ("fixture-only-token", "FIXTURE"))
    monkeypatch.setattr(writer, "HfApi", lambda **kwargs: object())
    monkeypatch.setattr(writer, "resolve_verified_source_tip", lambda: (SOURCE, {
        "schema": "szl.lyte-source-resolution/v1", "revision": SOURCE, "verified_commit": True}))
    monkeypatch.setattr(writer, "checkout_exact_source", lambda *args, **kwargs: None)
    monkeypatch.setattr(writer, "fetch_pinned_controller", lambda *args: None)
    monkeypatch.setattr(writer, "require_current_source", lambda *args: None)
    monkeypatch.setattr(writer, "require_current_publisher", lambda *args: None)
    monkeypatch.setattr(writer, "controller_preflight", lambda *args, **kwargs: {
        "manifest_sha256": "e" * 64, "remote_writes": 0})
    monkeypatch.setattr(writer, "snapshot_previous", lambda *args: {"expected_hf_parent": PARENT})
    calls = []
    def publication(*args, **kwargs): calls.append("publish")
    monkeypatch.setattr(writer, "deploy_with_controller", publication)
    monkeypatch.setattr(writer, "require_published_commit", lambda *args, **kwargs: {
        "hf_commit_oid": COMMIT, "current_target_matched": True})
    def bind(*args, **kwargs):
        assert calls == ["publish"]
        calls.append("bind")
        return {"source_variable_value": kwargs["revision"]}
    monkeypatch.setattr(writer, "ensure_runtime_configuration", bind)
    monkeypatch.setattr(writer, "restart_with_controller", lambda *args: calls.append("restart"))
    monkeypatch.setattr(writer, "attest_with_controller", lambda *args: calls.append("attest"))
    monkeypatch.setattr(writer, "read_manifest", lambda *args, **kwargs: {})
    monkeypatch.setattr(writer, "verify_contract", lambda **kwargs: {"complete": True})
    return calls


@pytest.mark.parametrize("function,expected_calls", [
    ("checkout_exact_source", []), ("fetch_pinned_controller", []),
    ("controller_preflight", []), ("admit_fresh_operation", []), ("snapshot_previous", []),
    ("require_current_source", []), ("require_current_publisher", []),
    ("deploy_with_controller", []), ("require_published_commit", ["publish"]),
    ("ensure_runtime_configuration", ["publish"]),
    ("restart_with_controller", ["publish", "bind"]),
    ("attest_with_controller", ["publish", "bind", "restart"]),
    ("verify_contract", ["publish", "bind", "restart", "attest"]),
])
def test_every_failed_phase_stops_later_mutations_and_cannot_complete(writer, monkeypatch, tmp_path, function, expected_calls):
    calls = install_main_fixture(writer, monkeypatch, tmp_path)
    def fail(*args, **kwargs): raise RuntimeError("private-marker-must-never-be-published")
    monkeypatch.setattr(writer, function, fail)
    assert writer.main() == 1
    receipt = json.loads((tmp_path / writer.RECEIPT_PATH).read_text())
    assert receipt["complete"] is False and receipt["release_journal"]["complete"] is False
    assert calls == expected_calls
    assert "private-marker-must-never-be-published" not in json.dumps(receipt)
    events = [json.loads(path.read_text()) for path in Path(receipt["release_evidence_directory"]).glob("*.json")]
    phases = sorted((event for event in events if event.get("schema") == "szl.release-phase/v1"), key=lambda event: event["sequence"])
    assert phases[-1]["state"] == "FAIL"


@pytest.mark.parametrize("exception,state", [("SourceSuperseded", "SUPERSEDED"), ("OutcomeUncertain", "OUTCOME_UNCERTAIN")])
def test_typed_failure_survives_journal_wrapping_and_never_retries(writer, monkeypatch, tmp_path, exception, state):
    calls = install_main_fixture(writer, monkeypatch, tmp_path)
    def fail(*args, **kwargs):
        calls.append("attempt")
        raise getattr(writer, exception)("fixture") from RuntimeError("private-cause")
    monkeypatch.setattr(writer, "deploy_with_controller", fail)
    assert writer.main() == 1 and calls == ["attempt"]
    receipt = json.loads((tmp_path / writer.RECEIPT_PATH).read_text())
    assert receipt["state"] == state and receipt["complete"] is False
    assert receipt["reconciliation_required"] == (state == "OUTCOME_UNCERTAIN")
    assert "private-cause" not in json.dumps(receipt)


def test_success_requires_all_real_phase_callbacks_and_durable_event_chain(writer, monkeypatch, tmp_path):
    calls = install_main_fixture(writer, monkeypatch, tmp_path)
    assert writer.main() == 0
    receipt = json.loads((tmp_path / writer.RECEIPT_PATH).read_text())
    assert calls == ["publish", "bind", "restart", "attest"]
    assert receipt["release_journal"]["completed_phases"] == list(writer.RELEASE_PHASES)
    assert receipt["release_journal"]["event_count"] == 2 * len(writer.RELEASE_PHASES)
    assert receipt["release_journal"]["signature_verified"] is False
    assert receipt["release_plan"]["expected_hf_parent"] == PARENT
    assert len(receipt["release_plan"]["operation_id"]) == 64


def test_operation_identity_does_not_change_with_attempt_or_evidence_directory(writer, monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    first = writer.operation_identity(revision=SOURCE, publisher=PUBLISHER, manifest_sha256="e" * 64)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    monkeypatch.chdir(tmp_path)
    assert writer.operation_identity(revision=SOURCE, publisher=PUBLISHER, manifest_sha256="e" * 64) == first
    monkeypatch.setenv("GITHUB_RUN_ID", "67890")
    assert writer.operation_identity(revision=SOURCE, publisher=PUBLISHER, manifest_sha256="e" * 64) != first


@pytest.mark.parametrize("attempt", ["2", "3", "0", "", "01", "not-an-attempt"])
def test_fresh_runner_without_prior_intent_cannot_retry_or_snapshot_new_parent(writer, monkeypatch, tmp_path, attempt):
    calls = install_main_fixture(writer, monkeypatch, tmp_path)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", attempt)
    monkeypatch.setattr(writer, "snapshot_previous", lambda *args: pytest.fail("retry refreshed parent"))
    assert writer.main() == 1
    receipt = json.loads(writer.RECEIPT_PATH.read_text())
    assert receipt["state"] == "OUTCOME_UNCERTAIN"
    assert receipt["reconciliation_required"] is True and receipt["complete"] is False
    assert "release_plan" not in receipt and calls == []
    assert "admit-operation" not in receipt["release_journal"]["completed_phases"]


@pytest.mark.parametrize("reconciled", [False, True])
@pytest.mark.parametrize("failed_phase", ["publish", "bind"])
def test_second_invocation_reconciles_same_intent_and_never_replays_any_mutation(
    writer, monkeypatch, tmp_path, reconciled, failed_phase,
):
    calls = install_main_fixture(writer, monkeypatch, tmp_path)
    snapshots = []
    monkeypatch.setattr(writer, "snapshot_previous", lambda *args: snapshots.append(PARENT) or {
        "expected_hf_parent": PARENT})
    def publish(*args, **kwargs):
        calls.append("publish")
        kwargs["intent"].write_text(json.dumps({"operation_id": kwargs["plan"]["operation_id"]}))
        if failed_phase == "publish":
            raise writer.OutcomeUncertain("fixture-private-provider-error")
    monkeypatch.setattr(writer, "deploy_with_controller", publish)
    if failed_phase == "bind":
        def bind(*args, **kwargs):
            calls.append("bind")
            raise writer.OutcomeUncertain("fixture-private-variable-error")
        monkeypatch.setattr(writer, "ensure_runtime_configuration", bind)
    assert writer.main() == 1
    first = json.loads(writer.RECEIPT_PATH.read_text())
    intent = Path(first["transaction_journal"])
    retained = intent.read_bytes()
    assert first["state"] == "OUTCOME_UNCERTAIN"
    before = list(calls)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    monkeypatch.setattr(writer, "snapshot_previous", lambda *args: pytest.fail("retry changed the HF parent"))
    reconciliation = []
    def reconcile(command):
        assert command[2:] == ["--reconcile-transaction", str(intent.relative_to(tmp_path)),
                               "--hf-repo", writer.HF_REPOSITORY]
        reconciliation.append(command)
        if not reconciled:
            raise RuntimeError("fixture-private-reconciliation-failure")
    monkeypatch.setattr(writer, "run_checked", reconcile)
    assert writer.main() == 1
    second = json.loads(writer.RECEIPT_PATH.read_text())
    assert second["state"] == ("REPLAY_HELD" if reconciled else "OUTCOME_UNCERTAIN")
    assert second["reconciliation_required"] is (not reconciled)
    assert second["complete"] is False and second["release_journal"]["failed"] is True
    assert first["release_evidence_directory"] != second["release_evidence_directory"]
    assert first["transaction_journal"] == second["transaction_journal"]
    assert "release_plan" not in second
    assert calls == before and snapshots == [PARENT] and len(reconciliation) == 1
    assert intent.read_bytes() == retained
    assert "fixture-private" not in json.dumps(second)


@pytest.mark.parametrize("kind", ["invalid-json", "wrong-operation", "symlink", "other-operation"])
def test_retained_evidence_ambiguity_cannot_be_treated_as_fresh_admission(writer, monkeypatch, tmp_path, kind):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    operation = "e" * 64
    intent = writer.EVIDENCE_DIRECTORY / "operations" / ("operation-" + operation + ".json")
    intent.parent.mkdir(parents=True)
    if kind == "invalid-json": intent.write_text("{broken")
    elif kind == "wrong-operation": intent.write_text(json.dumps({"operation_id": "f" * 64}))
    elif kind == "symlink": intent.symlink_to(tmp_path / "missing")
    else: intent.with_name("operation-other.json").write_text("{}")
    monkeypatch.setattr(writer, "run_checked", lambda *args: pytest.fail("unbound evidence reached controller"))
    with pytest.raises(writer.OutcomeUncertain):
        writer.admit_fresh_operation(tmp_path / "controller.py", operation=operation, intent=intent)


@pytest.mark.parametrize("observed", [None, "e" * 40, SOURCE])
def test_source_binding_requires_provider_metadata_readback(writer, observed):
    calls = []
    class Api:
        def auth_check(self, **kwargs): calls.append("authorize")
        def add_space_variable(self, **kwargs):
            assert kwargs["value"] == SOURCE
            calls.append("write")
        def get_space_variables(self, **kwargs):
            calls.append("observe")
            return {writer.SOURCE_VARIABLE: {"value": observed}}
    if observed == SOURCE:
        assert writer.ensure_runtime_configuration(Api(), revision=SOURCE)["source_variable_readback_matched"] is True
    else:
        with pytest.raises(writer.OutcomeUncertain): writer.ensure_runtime_configuration(Api(), revision=SOURCE)
    assert calls == ["authorize", "write", "observe"]


def test_both_actual_vertical_jobs_share_one_non_cancelling_writer_lifecycle():
    """Workflow-level groups stay distinct; only the vertical jobs serialize."""
    manual = (ROOT / ".github/workflows/hf-publish-vertical-flagships.yml").read_text()
    canonical = (ROOT / ".github/workflows/hf-sync.yml").read_text()
    group = "    concurrency:\n      group: hf-vertical-estate\n      cancel-in-progress: false"
    assert manual.count(group) == 1 and canonical.count(group) == 2
    assert "  group: hf-publish-vertical-flagships\n" in manual
    assert "  group: sync-relock-canonical-a11oy\n" in canonical
    assert "github.event_name == 'workflow_dispatch' && inputs.publish_vertical_flagships" in canonical
    assert "options: [finance, lyte, terra, sentra, counsel, estate]" in manual
    assert "SZL_FLAGSHIP_SCOPE: finance" in canonical
    assert "hf-lyte-release-evidence/" in manual and "hf-lyte-release-evidence/" in canonical


def test_real_pinned_controller_cli_derives_identical_marker_projection_twice(writer, monkeypatch, tmp_path):
    """Real argv/parser/derivation; no provider client, fixture source only."""
    peer = os.getenv("SZL_RELEASE_CONTROLLER_ROOT")
    if not peer:
        pytest.skip("pinned controller checkout is required for actual CLI proof")
    controller = Path(peer) / ".github/scripts/hf_deploy_from_dockerfile.py"
    assert controller.is_file()
    assert writer.git_blob_sha1(controller.read_bytes()) == writer.CONTROLLER_BLOB_SHA1
    source = tmp_path / "source"
    source.mkdir()
    (source / "Dockerfile").write_text("FROM scratch\nCOPY app.py source_revision.txt ./\n")
    (source / "app.py").write_text("print('fixture')\n")
    (source / "README.md").write_text("---\nsdk: docker\n---\nFixture source only\n")
    (source / writer.SOURCE_MARKER).write_text("UNAVAILABLE\n")
    def run(command):
        result = subprocess.run(command, capture_output=True, timeout=15, shell=False)
        assert len(result.stdout) + len(result.stderr) < 100_000
        assert result.returncode == 0, result.stderr.decode(errors="replace")[:1000]
    monkeypatch.setattr(writer, "run_checked", run)
    manifest = tmp_path / "manifest.json"
    evidence = writer.controller_preflight(source, controller, manifest, revision=SOURCE)
    first = writer.read_manifest(manifest, revision=SOURCE)
    assert evidence["remote_writes"] == 0
    assert (source / writer.SOURCE_MARKER).read_text() == SOURCE + "\n"
    writer.reset_generated_marker(source, revision=SOURCE)
    run(writer.controller_publish_command(source, controller, manifest, revision=SOURCE) + ["--dry-run"])
    assert writer.read_manifest(manifest, revision=SOURCE)["manifest_sha256"] == first["manifest_sha256"]


@pytest.mark.parametrize("scenario", ["confirmed", "superseded", "missing-marker", "wrong-parent", "wrong-bytes"])
def test_retained_replay_uses_actual_pinned_controller_read_only_reconciliation(
    writer, monkeypatch, tmp_path, capsys, scenario,
):
    """Actual parser/reconciler; only provider reads are fixture responses."""
    peer = os.getenv("SZL_RELEASE_CONTROLLER_ROOT")
    if not peer:
        pytest.skip("pinned controller checkout is required for actual CLI proof")
    path = Path(peer) / ".github/scripts/hf_deploy_from_dockerfile.py"
    assert writer.git_blob_sha1(path.read_bytes()) == writer.CONTROLLER_BLOB_SHA1
    spec = importlib.util.spec_from_file_location("pinned_lyte_reconciler_fixture", path)
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    operation = "e" * 64
    content = b"fixture-only-app"
    manifest = {"hf_repo": writer.HF_REPOSITORY, "files": {"app.py": {
        "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}}}
    manifest_sha = controller.manifest_identity(manifest)
    intent = writer.EVIDENCE_DIRECTORY / "operations" / ("operation-" + operation + ".json")
    intent.parent.mkdir(parents=True)
    record = {"schema": "szl.hf-deploy-operation/v1", "operation_id": operation,
              "expected_parent": PARENT, "manifest_sha256": manifest_sha,
              "manifest": manifest, "pruned": [], "state": "OUTCOME_UNCERTAIN"}
    record["intent_sha256"] = controller.intent_identity(record)
    intent.write_text(json.dumps(record))
    retained = intent.read_bytes()
    message = "\n".join(["SZL-Operation-ID: " + operation,
                          "SZL-Manifest-SHA256: " + manifest_sha,
                          "SZL-Expected-Parent: " + PARENT])
    history = [{"id": COMMIT, "message": message}, {"id": PARENT, "message": "prior"}]
    if scenario == "superseded": history.insert(0, {"id": "f" * 40, "message": "newer"})
    elif scenario == "missing-marker": history[0]["message"] = "unrelated"
    elif scenario == "wrong-parent": history[1]["id"] = "f" * 40
    reads = []
    def http(url, **kwargs):
        assert url == controller.HF_HOST + "/api/spaces/" + writer.HF_REPOSITORY + "/commits/main"
        assert kwargs.get("method", "GET") == "GET" and kwargs.get("data") is None
        reads.append("history")
        return 200, json.dumps(history).encode()
    def resolve(repo, target, revision):
        assert (repo, target, revision) == (writer.HF_REPOSITORY, "app.py", COMMIT)
        reads.append("immutable-file")
        return 200, (b"different" if scenario == "wrong-bytes" else content)
    monkeypatch.setattr(controller, "_http", http)
    monkeypatch.setattr(controller, "hf_resolve", resolve)
    monkeypatch.setattr(controller, "deploy", lambda *args: pytest.fail("reconcile attempted publication"))
    monkeypatch.setattr(controller, "restart_from_manifest", lambda *args: pytest.fail("reconcile attempted restart"))
    def run(command):
        assert command[:2] == [sys.executable, str(path)]
        if controller.main(command[2:]) != 0:
            raise RuntimeError("fixture controller held reconciliation")
    monkeypatch.setattr(writer, "run_checked", run)
    expected = writer.PublicationReplayHeld if scenario == "confirmed" else writer.OutcomeUncertain
    with pytest.raises(expected):
        writer.admit_fresh_operation(path, operation=operation, intent=intent)
    assert reads and reads[0] == "history"
    assert intent.read_bytes() == retained
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == {
        "confirmed": "CONFIRMED", "superseded": "SUPERSEDED",
        "missing-marker": "OUTCOME_UNCERTAIN", "wrong-parent": "OUTCOME_UNCERTAIN",
        "wrong-bytes": "HOLD_BYTE_MISMATCH",
    }[scenario]


@pytest.mark.skipif(os.name != "posix", reason="the release runner explicitly requires POSIX process groups")
def test_actual_writer_runner_bounds_hanging_descendant_group(writer, tmp_path):
    destination = tmp_path / "child-survived"
    child = "import time,pathlib; time.sleep(1); pathlib.Path(" + repr(str(destination)) + ").write_text('unexpected')"
    parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(child) + "]); time.sleep(20)"
    observation = writer.guard_run_bounded([sys.executable, "-c", parent], cwd=tmp_path, timeout=0.2)
    assert observation["passed"] is False and observation["timed_out"] is True
    assert observation["process_group_kill_attempted"] is True
    assert observation["elapsed_seconds"] < 4
    time.sleep(1.1)
    assert not destination.exists()


@pytest.mark.skipif(os.name != "posix", reason="the release runner explicitly requires POSIX process groups")
def test_actual_writer_runner_caps_both_output_streams_and_retains_no_raw_diagnostics(writer, tmp_path):
    code = "import os; data=b'fixture-private-diagnostic'*10000; os.write(1,data); os.write(2,data)"
    observation = writer.guard_run_bounded([sys.executable, "-c", code], cwd=tmp_path, timeout=3, max_output=1024)
    assert observation["passed"] is False and observation["output_limited"] is True
    assert sum(stream["captured_bytes"] for stream in observation["streams"].values()) <= 1024
    assert "fixture-private-diagnostic" not in json.dumps(observation)
    assert observation["raw_output_recorded"] is False
