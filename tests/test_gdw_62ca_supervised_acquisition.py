# SPDX-License-Identifier: Apache-2.0
"""Offline exact native receipts and fixed-incident read/fence boundaries only."""
import ast
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import time
from types import SimpleNamespace
import zipfile

import httpx
import pytest

from scripts import gdw_acquisition_evidence as native
from scripts import reconcile_gdw_62ca_retained_observation as retained
from scripts import reconcile_gdw_62ca_supervised_acquisition as successor
from tests.test_gdw_62ca_retained_observation import fixture_metadata

SOURCE, RUN, JOB, SOURCE_JOB, SOURCE_ARTIFACT = "b" * 40, 900, 901, 902, 904


@pytest.fixture(autouse=True)
def fixed_native_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, _zone=None):
            return datetime(2026, 10, 5, 15, tzinfo=timezone.utc)
    for module in (native, retained, successor):
        monkeypatch.setattr(module, "datetime", Clock)


def state_fixture(job_key=successor.RECONCILIATION_JOB_KEY):
    source_receipt = successor._canonical({"schema": "szl.hf-main-ownership/v1", "repository": native.REPOSITORY,
        "branch": "main", "expected_sha": SOURCE, "observed_main_sha": SOURCE, "status": "OWNED",
        "source_verified": True, "publish": True, "external_writes_performed": False,
        "secret_values_recorded": False})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("canonical-source-admission.json", source_receipt)
    raw = buffer.getvalue()
    run = {"id": RUN, "run_attempt": 1, "workflow_id": 400, "path": native.WORKFLOW,
        "event": "push", "head_sha": SOURCE, "head_branch": "main", "status": "in_progress", "conclusion": None,
        "repository": {"id": retained.REPOSITORY_ID, "full_name": native.REPOSITORY},
        "head_repository": {"id": retained.REPOSITORY_ID}, "run_started_at": "2026-10-05T14:40:00Z"}
    jobs = [{"id": identifier, "name": name, "run_id": RUN, "run_attempt": 1, "head_sha": SOURCE,
        "status": status, "conclusion": conclusion, "started_at": started, "completed_at": completed}
        for identifier, name, status, conclusion, started, completed in (
            (SOURCE_JOB, native.SOURCE_JOB, "completed", "success", "2026-10-05T14:40:01Z", "2026-10-05T14:40:10Z"),
            (903, native.QUALIFICATION_JOB, "completed", "success", "2026-10-05T14:40:12Z", "2026-10-05T14:40:20Z"),
            (JOB, successor.JOB_NAMES[job_key], "in_progress", None, "2026-10-05T14:45:00Z", None))]
    meta = {"id": SOURCE_ARTIFACT, "name": f"canonical-source-admission-{RUN}-1", "expired": False,
        "size_in_bytes": len(raw), "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "created_at": "2026-10-05T14:40:09Z", "expires_at": "2027-01-03T14:40:00Z",
        "workflow_run": {"id": RUN, "head_sha": SOURCE, "head_branch": "main",
            "repository_id": retained.REPOSITORY_ID, "head_repository_id": retained.REPOSITORY_ID}}
    return {"run": run, "current": copy.deepcopy(run), "jobs": {"total_count": 3, "jobs": jobs},
        "commit": {"sha": SOURCE, "parents": [{"sha": successor.PARENT_SOURCE}],
            "verification": {"verified": True, "reason": "valid"}},
        "runs": {"total_count": 1, "workflow_runs": [copy.deepcopy(run)]},
        "branch": {"name": "main", "protected": True, "commit": {"sha": SOURCE}},
        "artifact": meta, "artifacts": {"total_count": 1, "artifacts": [copy.deepcopy(meta)]},
        "archive": raw, "historical": fixture_metadata(), "job_key": job_key}


def native_reader(state, monkeypatch):
    calls, branch_reads = [], [0]
    def transport(request):
        assert request.method == "GET"
        calls.append(str(request.url))
        if request.url.host == "safe.actions.githubusercontent.com":
            assert "authorization" not in request.headers
            return httpx.Response(200, content=(state["archive"] if request.url.path == "/source.zip"
                else state["historical"]["archive"]))
        assert request.url.host == "api.github.com"
        suffix = str(request.url).split(f"/repos/{native.REPOSITORY}/", 1)[1]
        redirects = {f"actions/artifacts/{SOURCE_ARTIFACT}/zip": "source.zip",
            f"actions/artifacts/{retained.ARTIFACT}/zip": "historical.zip"}
        if suffix in redirects:
            return httpx.Response(302, headers={"location": "https://safe.actions.githubusercontent.com/" + redirects[suffix]})
        if suffix == "branches/main":
            branch_reads[0] += 1
            value = state.get("late_branch", state["branch"]) if branch_reads[0] > 2 else state["branch"]
        else:
            current = {f"actions/runs/{RUN}/attempts/1": "run", f"actions/runs/{RUN}": "current",
                f"actions/runs/{RUN}/attempts/1/jobs?per_page=100": "jobs", f"git/commits/{SOURCE}": "commit",
                f"actions/workflows/hf-sync.yml/runs?event=push&head_sha={SOURCE}&per_page=100": "runs",
                f"actions/runs/{RUN}/artifacts?per_page=100": "artifacts", f"actions/artifacts/{SOURCE_ARTIFACT}": "artifact"}
            historical = {f"actions/runs/{retained.RUN}/attempts/1": "run", f"actions/runs/{retained.RUN}": "current",
                f"actions/runs/{retained.RUN}/attempts/1/jobs?per_page=100": "jobs",
                f"git/commits/{retained.SOURCE}": "commit", f"actions/artifacts/{retained.ARTIFACT}": "artifact"}
            value = state[current[suffix]] if suffix in current else state["historical"][historical[suffix]]
        return httpx.Response(200, json=value)
    env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": native.REPOSITORY,
        "GITHUB_REPOSITORY_ID": str(retained.REPOSITORY_ID), "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": SOURCE, "GITHUB_WORKFLOW_SHA": SOURCE, "GITHUB_RUN_ID": str(RUN), "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": native.REPOSITORY + "/" + native.WORKFLOW + "@refs/heads/main",
        "GITHUB_EVENT_NAME": "push", "GITHUB_JOB": state["job_key"], "GH_TOKEN": "synthetic-read-token"}
    for key, value in env.items(): monkeypatch.setenv(key, value)
    return native.NativeEvidence(env, time.monotonic() + 60,
        client=httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=False, trust_env=False)), calls


@pytest.mark.parametrize("job_key", list(successor.JOB_NAMES))
def test_exact_live_native_owner_and_real_historical_safe_receipt_are_read_only(monkeypatch, job_key):
    state = state_fixture(job_key); evidence, calls = native_reader(state, monkeypatch)
    try:
        context = successor.verify_native_prerequisite(evidence)
    finally:
        evidence.client.close()
    assert context == {"source_revision": SOURCE, "run_id": RUN, "run_attempt": 1, "job_id": JOB,
        "job_key": job_key, "source_admission_artifact_id": SOURCE_ARTIFACT,
        "source_admission_archive_sha256": state["artifact"]["digest"][7:],
        "source_admission_sha256": hashlib.sha256(native.validate_archive(state["artifact"], state["archive"],
            artifact_id=SOURCE_ARTIFACT, expected_digest=state["artifact"]["digest"][7:],
            expected_name=state["artifact"]["name"], source=SOURCE, run_id=RUN,
            repository_id=retained.REPOSITORY_ID, members=frozenset({"canonical-source-admission.json"}))
            ["canonical-source-admission.json"]).hexdigest()}
    assert len(calls) == 26 and any(str(retained.ARTIFACT) in url for url in calls)


@pytest.mark.parametrize("defect", ["attempt", "manual", "source", "unsigned", "parent", "parents", "rerun",
    "census", "job_failed", "job_future", "producer_failed", "workflow", "duplicate_artifact", "artifact_census",
    "artifact_source", "artifact_run", "artifact_repo", "artifact_expired", "artifact_time", "artifact_expires",
    "archive", "historical_expired", "historical_attempt", "historical_census", "late_main"])
def test_current_or_historical_substitution_holds_without_provider_access(monkeypatch, defect):
    state = state_fixture(native.ACQUISITION_JOB_KEY)
    if defect == "attempt": state["run"]["run_attempt"] = 2
    if defect == "manual": state["run"]["event"] = "workflow_dispatch"
    if defect == "source": state["run"]["head_sha"] = "a" * 40
    if defect == "unsigned": state["commit"]["verification"]["verified"] = False
    if defect == "parent": state["commit"]["parents"][0]["sha"] = "a" * 40
    if defect == "parents": state["commit"]["parents"].append({"sha": "a" * 40})
    if defect == "rerun": state["current"]["run_attempt"] = 2
    if defect == "census": state["jobs"]["total_count"] = 4
    if defect == "job_failed": state["jobs"]["jobs"][2]["conclusion"] = "failure"
    if defect == "job_future": state["jobs"]["jobs"][2]["started_at"] = "2050-01-01T00:00:00Z"
    if defect == "producer_failed": state["jobs"]["jobs"][0]["conclusion"] = "failure"
    if defect == "workflow": state["runs"]["workflow_runs"][0]["workflow_id"] += 1
    if defect == "duplicate_artifact":
        state["artifacts"]["artifacts"].append(copy.deepcopy(state["artifact"])); state["artifacts"]["total_count"] = 2
    if defect == "artifact_census": state["artifacts"]["total_count"] = 2
    if defect in {"artifact_source", "artifact_run", "artifact_repo"}:
        row = state["artifacts"]["artifacts"][0]["workflow_run"]
        row[{"artifact_source": "head_sha", "artifact_run": "id", "artifact_repo": "repository_id"}[defect]] = "a" * 40
    if defect == "artifact_expired": state["artifact"]["expired"] = True
    if defect == "artifact_time": state["artifacts"]["artifacts"][0]["created_at"] = "2026-10-05T14:40:00Z"
    if defect == "artifact_expires": state["artifacts"]["artifacts"][0]["expires_at"] = "2026-10-05T14:40:10Z"
    if defect == "archive": state["archive"] += b"x"
    if defect == "historical_expired": state["historical"]["artifact"]["expired"] = True
    if defect == "historical_attempt": state["historical"]["current"]["run_attempt"] = 2
    if defect == "historical_census": state["historical"]["jobs"]["total_count"] = 3
    if defect == "late_main": state["late_branch"] = {"name": "main", "protected": True, "commit": {"sha": "a" * 40}}
    evidence, _calls = native_reader(state, monkeypatch)
    try:
        with pytest.raises(successor.ReconciliationHeld) as error: successor.verify_native_prerequisite(evidence)
    finally:
        evidence.client.close()
    assert str(error.value) in successor.CODES


class ReadFence:
    endpoint = successor.ENDPOINT
    def __init__(self): self.calls, self.revisions, self.paths = [], [retained.DATASET_REVISION] * 2, []
    def dataset_info(self, repo, **kwargs):
        self.calls.append(("dataset", repo, kwargs))
        return {"id": repo, "private": True, "sha": self.revisions.pop(0)}
    def get_paths_info(self, repo, paths, **kwargs):
        self.calls.append(("head", repo, paths, kwargs)); return self.paths


def test_each_fence_call_has_two_fresh_source_gets_and_two_complete_metadata_rounds():
    events = []
    owner = SimpleNamespace(source=SOURCE, require_current_main=lambda: events.append("main"))
    for _ in range(2):
        api = ReadFence()
        result = successor.require_expected_absent(api, owner, time.monotonic() + 10)
        assert [row[0] for row in api.calls] == ["dataset", "head", "dataset", "head"]
        assert all(row[-1]["revision"] == ("main" if row[0] == "dataset" else retained.DATASET_REVISION) for row in api.calls)
        assert result["provider_writes_performed"] is False
    assert events == ["main"] * 4


@pytest.mark.parametrize("defect", ["head", "revision", "late_revision", "unprotected", "expired", "endpoint", "unavailable"])
def test_fence_failure_is_terminal_and_closed(defect):
    api = ReadFence(); calls = []
    def owner_check():
        calls.append("main")
        if defect == "unprotected": raise RuntimeError("secret-marker")
    owner = SimpleNamespace(source=SOURCE, require_current_main=owner_check)
    if defect == "head": api.paths = [{"path": successor.HEAD_PATH}]
    if defect == "revision": api.revisions[0] = "a" * 40
    if defect == "late_revision": api.revisions[1] = "a" * 40
    if defect == "endpoint": api.endpoint = "https://evil.example"
    if defect == "unavailable": api.dataset_info = lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("secret-marker"))
    with pytest.raises(successor.ReconciliationHeld) as error:
        successor.require_expected_absent(api, owner, time.monotonic() + (-1 if defect == "expired" else 10))
    assert str(error.value) in successor.CODES and "secret-marker" not in str(error.value)


def context_fixture():
    return {"source_revision": SOURCE, "run_id": RUN, "run_attempt": 1, "job_id": JOB,
        "job_key": native.ACQUISITION_JOB_KEY, "source_admission_artifact_id": SOURCE_ARTIFACT,
        "source_admission_archive_sha256": "a" * 64, "source_admission_sha256": "c" * 64}


def test_closed_reports_never_turn_observations_into_provider_write_authority():
    context = context_fixture()
    pre = successor.validate_reconciliation_report(successor._canonical(successor._report(context)))
    pair = {"gdw": {"sha256": "d" * 64, "size": 4096}, "series_a": {"sha256": "e" * 64, "size": 8192}}
    scan = successor.validate_scan_report(successor._canonical(successor._scan_report(context, pair, "f" * 64)))
    assert scan["candidates"] == pair and scan["candidate_sha256"] == pair["gdw"]["sha256"]
    assert pre["provider_objects_verified"] is False and pre["retained_object_scan_required_before_pause"] is True
    for report in (pre, scan):
        assert report["prior_provider_effects"] == report["historical_writer_attribution"] == "NOT_ESTABLISHED"
        assert all(report[key] is False for key in ("provider_writes_performed", "retry_admitted", "restore_admitted", "deployment_admitted"))


def test_initial_native_worker_reads_metadata_only_after_full_evidence_admission(monkeypatch, tmp_path):
    import gdw_durable_storage as storage
    evidence, calls = native_reader(state_fixture(), monkeypatch)
    monkeypatch.setattr(storage, "_private_directory", lambda path: path)
    monkeypatch.setattr(native, "NativeEvidence", lambda *_: evidence)
    api = ReadFence(); constructor_reads = []
    def api_factory(_token):
        constructor_reads.append(len(calls)); return api
    monkeypatch.setattr(storage, "_hub_api", api_factory)
    try:
        report = successor.execute_native_reconciliation(tmp_path, time.monotonic() + 60)
    finally:
        evidence.client.close()
    assert constructor_reads == [26] and [row[0] for row in api.calls] == ["dataset", "head", "dataset", "head"]
    assert report["state"] == "PREREQUISITE_VERIFIED" and report["retained_object_scan_required_before_pause"] is True
    assert not list(tmp_path.iterdir())


def test_unqualified_native_receipt_never_constructs_provider_client(monkeypatch, tmp_path):
    import gdw_durable_storage as storage
    state = state_fixture(); state["historical"]["artifact"]["expired"] = True
    evidence, _calls = native_reader(state, monkeypatch)
    monkeypatch.setattr(storage, "_private_directory", lambda path: path)
    monkeypatch.setattr(native, "NativeEvidence", lambda *_: evidence)
    monkeypatch.setattr(storage, "_hub_api", lambda *_: pytest.fail("provider constructed before native evidence"))
    try:
        with pytest.raises(successor.ReconciliationHeld):
            successor.execute_native_reconciliation(tmp_path, time.monotonic() + 60)
    finally:
        evidence.client.close()


@pytest.mark.parametrize("seconds", [-1, 121, float("inf"), float("nan")])
def test_initial_worker_cannot_expand_its_120_second_boundary(monkeypatch, tmp_path, seconds):
    monkeypatch.setattr(native, "NativeEvidence", lambda *_: pytest.fail("invalid budget reached native reads"))
    with pytest.raises(successor.ReconciliationHeld):
        successor.execute_native_reconciliation(tmp_path, time.monotonic() + seconds)


def test_initial_worker_rechecks_deadline_after_its_closed_decoder(monkeypatch, tmp_path):
    import gdw_durable_storage as storage
    clock = [0.0]; context = context_fixture(); context["job_key"] = successor.RECONCILIATION_JOB_KEY
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(storage, "_private_directory", lambda path: path)
    monkeypatch.setattr(native, "NativeEvidence", lambda *_: object())
    monkeypatch.setattr(successor, "verify_native_prerequisite", lambda _: context)
    monkeypatch.setattr(storage, "_hub_api", lambda _: object())
    monkeypatch.setattr(successor, "require_expected_absent", lambda *_: None)
    validate = successor.validate_reconciliation_report
    def late_decode(raw):
        result = validate(raw); clock[0] = 11.0; return result
    monkeypatch.setattr(successor, "validate_reconciliation_report", late_decode)
    with pytest.raises(successor.ReconciliationHeld): successor.execute_native_reconciliation(tmp_path, 10.0)


@pytest.mark.parametrize("defect", ["extra", "bool_attempt", "old_source", "retry", "expected_hash", "present",
    "pair_missing", "pair_extra", "pair_hash", "pair_size", "alias", "reconcile_job", "duplicate", "loose", "overflow"])
def test_scan_decoder_rejects_loose_or_broader_observation(defect):
    pair = {"gdw": {"sha256": "d" * 64, "size": 4096}, "series_a": {"sha256": "e" * 64, "size": 8192}}
    report = successor._scan_report(context_fixture(), pair, "f" * 64)
    if defect == "extra": report["writer"] = True
    if defect == "bool_attempt": report["run_attempt"] = True
    if defect == "old_source": report["source_revision"] = successor.PARENT_SOURCE
    if defect == "retry": report["retry_admitted"] = True
    if defect == "expected_hash": report["expected_object_set_sha256"] = "a" * 64
    if defect == "present": report["present_object_count"] = 1
    if defect == "pair_missing": report["candidates"].pop("series_a")
    if defect == "pair_extra": report["candidates"]["gdw"]["selector"] = "arbitrary"
    if defect == "pair_hash": report["candidates"]["series_a"]["sha256"] = "0" * 64
    if defect == "pair_size": report["candidates"]["gdw"]["size"] = True
    if defect == "alias": report["candidate_sha256"] = "a" * 64
    if defect == "reconcile_job": report["job_key"] = successor.RECONCILIATION_JOB_KEY
    raw = successor._canonical(report)
    if defect == "duplicate": raw = raw[:-2] + b',"run_attempt":1}\n'
    if defect == "loose": raw += b" "
    if defect == "overflow": raw += b" " * 4096
    with pytest.raises(successor.ReconciliationHeld): successor.validate_scan_report(raw)


def mock_checkout(monkeypatch, source=SOURCE, *, dirty=False):
    def checkout(arguments, **kwargs):
        assert arguments[:3] == ["git", "-C", str(successor.ROOT)] and 0 < kwargs["timeout"] <= 10
        if arguments[3] == "diff" and dirty: raise RuntimeError("secret-marker")
        return SimpleNamespace(stdout=(source + "\n").encode(), returncode=0)
    monkeypatch.setattr(successor.subprocess, "run", checkout)


def scan_env(monkeypatch):
    for key, value in {"GITHUB_SHA": SOURCE, "GITHUB_WORKFLOW_SHA": SOURCE, "GITHUB_RUN_ID": str(RUN),
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": native.ACQUISITION_JOB_KEY}.items(): monkeypatch.setenv(key, value)


def test_read_only_guard_is_batched_not_a_noop_or_per_write_cached_lease(monkeypatch):
    scan_env(monkeypatch); mock_checkout(monkeypatch); reads = []
    evidence = SimpleNamespace(source=SOURCE, run_id=RUN, attempt=1, executing_job=native.ACQUISITION_JOB_KEY,
        require_current_main=lambda: reads.append("main"))
    guard = successor._ReadOnlyScanGuard(evidence, context_fixture(), time.monotonic() + 10)
    for _ in range(450): guard()
    guard.observe()
    assert len(reads) == 16  # initial + floor(450/32) + final, not 450 GETs
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    with pytest.raises(successor.ReconciliationHeld): guard()


@pytest.mark.parametrize("defect", ["checkout", "dirty", "main", "deadline", "context"])
def test_read_only_guard_still_aborts_on_source_context_or_budget_drift(monkeypatch, defect):
    scan_env(monkeypatch); mock_checkout(monkeypatch, "a" * 40 if defect == "checkout" else SOURCE, dirty=defect == "dirty")
    def current():
        if defect == "main": raise RuntimeError("secret-marker")
    evidence = SimpleNamespace(source=SOURCE, run_id=RUN + (defect == "context"), attempt=1,
        executing_job=native.ACQUISITION_JOB_KEY, require_current_main=current)
    with pytest.raises((successor.ReconciliationHeld, RuntimeError)):
        successor._ReadOnlyScanGuard(evidence, context_fixture(), time.monotonic() + (-1 if defect == "deadline" else 10))


def scan_fixture(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(successor.ROOT / "scripts"))
    import gdw_durable_storage as storage
    from gdw_durable_artifacts import LOGICAL_ROOTS
    from scripts import acquire_gdw_durable_storage as acquisition
    from scripts import qualify_gdw_store_recovery as recovery
    from scripts import triage_gdw_artifacts_readonly as triage
    scan_env(monkeypatch); mock_checkout(monkeypatch)
    for name, value in {"GDW_PROOF_DIR": str(LOGICAL_ROOTS["proof_export"]),
        "GDW_RECEIPT_PROJECTION_DIR": str(LOGICAL_ROOTS["receipt_projection"])}.items(): monkeypatch.setenv(name, value)
    calls = []
    context = context_fixture()
    evidence = SimpleNamespace(source=SOURCE, run_id=RUN, attempt=1, executing_job=native.ACQUISITION_JOB_KEY,
        require_current_main=lambda: calls.append("main"))
    qualified = {"state": "LOGICAL_CONTINUITY_VERIFIED", "provider_writes_performed": False, "originals_mutated": False,
        "restore_admitted": False, "deployment_admitted": False, "databases": {label: {
            "state": "LOGICAL_CONTINUITY_VERIFIED", "captured_originals_unchanged": True,
            "all_declared_stored_values_unchanged": True, "candidate_sha256": digest * 64, "candidate_bytes": size}
            for label, digest, size in (("gdw", "d", 4096), ("series_a", "e", 8192))}}
    monkeypatch.setattr(storage, "_private_directory", lambda path: path)
    monkeypatch.setattr(storage, "_file_identity", lambda path, *_: {
        "sha256": qualified["databases"][path.parent.name]["candidate_sha256"],
        "size": qualified["databases"][path.parent.name]["candidate_bytes"]})
    monkeypatch.setattr(successor, "verify_native_prerequisite", lambda _: dict(context))
    monkeypatch.setattr(successor, "_current_context", lambda _: {key: context[key]
        for key in ("source_revision", "run_id", "run_attempt", "job_id", "job_key")})
    monkeypatch.setattr(acquisition, "_references", lambda: ({}, b"{}", {}, b"{}"))
    monkeypatch.setattr(recovery, "ReadOnlyCaptureHub", lambda api: api)
    def qualify(_api, _reference, directory, owned, deadline, **_kwargs):
        calls.append("qualification"); owned(); assert directory == tmp_path / "fixed-62ca-retained-scan/capture"
        return qualified
    monkeypatch.setattr(recovery, "qualify_capture", qualify)
    effects = copy.deepcopy(retained._expected_report()["artifact_effect_observation"])
    def observe(_api, _database, _directory, owned, _deadline, **_kwargs):
        calls.append("object-scan")
        for _ in range(450): owned()
        return effects
    monkeypatch.setattr(triage, "artifact_effect_observation", observe)
    return evidence, qualified, effects, calls


def test_fresh_one_time_scan_binds_both_candidates_and_fixed_complete_expected_set(monkeypatch, tmp_path):
    evidence, _qualified, _effects, calls = scan_fixture(monkeypatch, tmp_path)
    api = ReadFence(); api.revisions *= 2
    report = successor.verify_candidate_scan(api, evidence, tmp_path, time.monotonic() + 60)
    assert report["candidates"] == {"gdw": {"sha256": "d" * 64, "size": 4096},
        "series_a": {"sha256": "e" * 64, "size": 8192}}
    assert report["missing_object_count"] == 224 and report["expected_object_set_sha256"] == retained.EXPECTED_SET_SHA256
    assert report["provider_writes_performed"] is False and calls.index("qualification") < calls.index("object-scan")
    assert len([call for call in calls if call == "main"]) == 21  # fence4 + qualification1 + batched16
    with pytest.raises(successor.ReconciliationHeld):
        successor.verify_candidate_scan(api, evidence, tmp_path, time.monotonic() + 60)


@pytest.mark.parametrize("defect", ["expected_set", "present", "pair", "candidate_changed", "main", "roots", "job", "qualified"])
def test_scan_failure_cannot_reach_pause_or_write_and_preserves_unknown_history(monkeypatch, tmp_path, defect):
    import gdw_durable_storage as storage
    evidence, qualified, effects, _calls = scan_fixture(monkeypatch, tmp_path)
    if defect == "expected_set": effects["expected_object_set_sha256"] = "a" * 64
    if defect == "present":
        effects.update(present_object_count=1, missing_object_count=223,
            classification="PARTIAL_EXPECTED_OBJECT_SET_PRESENT_AT_READ_TIME", observed_object_set_sha256="a" * 64)
    if defect == "pair": qualified["databases"].pop("series_a")
    if defect == "candidate_changed":
        counts = [0]
        def identity(path, *_):
            counts[0] += 1
            return {"sha256": ("d" if path.parent.name == "gdw" else "e") * 64,
                "size": (4096 if path.parent.name == "gdw" else 8192) + (counts[0] > 2)}
        monkeypatch.setattr(storage, "_file_identity", identity)
    if defect == "main": evidence.require_current_main = lambda: (_ for _ in ()).throw(RuntimeError("secret-marker"))
    if defect == "roots": monkeypatch.setenv("GDW_PROOF_DIR", "arbitrary-owner-path")
    if defect == "job": evidence.executing_job = successor.RECONCILIATION_JOB_KEY
    if defect == "qualified": qualified["provider_writes_performed"] = True
    api = ReadFence(); api.revisions *= 2
    with pytest.raises(successor.ReconciliationHeld) as error:
        successor.verify_candidate_scan(api, evidence, tmp_path, time.monotonic() + 60)
    assert str(error.value) in successor.CODES and "secret-marker" not in str(error.value)


def test_helper_has_no_cli_writer_dispatch_or_generic_incident_selector():
    text = Path(successor.__file__).read_text(encoding="utf-8")
    tree = ast.parse(text)
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert not {"main", "acquire", "retry", "restore", "dispatch"} & functions
    methods = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not {"upload_file", "upload_folder", "create_commit", "batch_bucket_files", "pause_space", "restart_space"} & methods
