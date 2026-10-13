# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Real SQLite and signature continuity with offline provider boundaries."""
import copy
import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_gdw_store_recovery as fixtures
from test_gdw_store_recovery import originals, historical_fixture  # noqa: F401

c = fixtures.load("qualify_gdw_current_capture", fixtures.ROOT / "scripts/qualify_gdw_current_capture.py")
q, p = fixtures.q, fixtures.p
SOURCE, RUN = "a" * 40, "37216937874"


@pytest.fixture
def current(originals, historical_fixture, tmp_path, monkeypatch, request):
    monkeypatch.setattr(c, "recovery", q)
    monkeypatch.setattr(c, "p", p)
    # All these fixtures are regular files. Windows has no POSIX link/open
    # flags; hosted Linux runs exercise those unmodified native boundaries.
    if os.name == "nt":
        monkeypatch.setattr(q.os, "O_NOFOLLOW", 0, raising=False)
        monkeypatch.setattr(q.os, "O_NONBLOCK", 0, raising=False)
    hub = fixtures.fixtures.FakeHub({path: originals[label].read_bytes() for label, path in p.DATABASES.items()})
    if getattr(request, "param", None) == "fallback":
        hub.batch_behavior = lambda fake, copies, additions: fake.apply_batch([], additions)
    reference = p.preserve(hub, source_sha=SOURCE, run_id=RUN, run_attempt="1", nonce="b" * 32,
                           workspace=tmp_path / "preserved", require_owned_source=lambda: None, sleep=lambda _: None)
    assert reference["preservation_state"] == "VERIFIED", reference
    historical = copy.deepcopy(reference)
    historical["source_revision"] = "9" * 40
    digest = hashlib.sha256(p._json_bytes(historical)).hexdigest()
    historical_fixture["capture_report_sha256"] = digest
    hub.head = None
    hub.head_revision = "6" * 40
    hub.head_reads = 0
    hub.after_head_read = None

    def dataset_info(**kwargs):
        assert kwargs["repo_id"] == p.BUCKET and kwargs["revision"] == "main"
        return SimpleNamespace(id=p.BUCKET, private=True, sha=hub.head_revision, resource_group=None)

    def get_paths_info(**kwargs):
        assert kwargs == {"repo_id": p.BUCKET, "paths": [c.HEAD_PATH], "repo_type": "dataset", "revision": hub.head_revision}
        hub.head_reads += 1
        result = [] if hub.head is None else [SimpleNamespace(path=c.HEAD_PATH, size=len(hub.head), lfs=None,
            blob_id=hashlib.sha1(b"blob " + str(len(hub.head)).encode() + b"\0" + hub.head).hexdigest())]
        if hub.after_head_read:
            hub.after_head_read(hub)
        return result

    def download(**kwargs):
        assert kwargs["repo_id"] == p.BUCKET and kwargs["filename"] == c.HEAD_PATH
        assert kwargs["repo_type"] == "dataset" and kwargs["revision"] == hub.head_revision
        target = Path(kwargs["local_dir"]) / c.HEAD_PATH
        target.parent.mkdir(parents=True)
        target.write_bytes(hub.head)
        return str(target)

    hub.dataset_info, hub.get_paths_info, hub.hf_hub_download = dataset_info, get_paths_info, download
    return hub, reference, historical_fixture, historical, digest


def run(current, tmp_path, **kwargs):
    hub, reference, anchors, historical, digest = current
    return c.qualify_current_capture(c.CurrentReadOnlyHub(hub), reference, anchors, historical,
        digest, tmp_path / "qualification", kwargs.pop("ownership", lambda: None),
        kwargs.pop("deadline", time.monotonic() + 60), source=SOURCE, run_id=RUN, run_attempt="1", **kwargs)


@pytest.mark.parametrize("head_present", [False, True])
def test_current_capture_replays_real_sqlite_and_signed_history_without_writes(current, tmp_path, head_present, monkeypatch):
    hub, reference, anchors, historical, digest = current
    hub.head = b'{"private_note":"DO_NOT_PUBLISH"}' if head_present else None
    batches, remote = len(hub.batch_calls), dict(hub.files)
    result = run(current, tmp_path)
    assert result["qualification_state"] == "LOGICAL_CONTINUITY_VERIFIED", result
    assert result["state"] == "BLOCKED"
    assert result["restore_admitted"] is result["deployment_admitted"] is False
    assert result["provider_writes_performed"] is result["later_acknowledged_writes_verified"] is False
    assert result["historical_capture_report_sha256"] == digest
    assert result["private_manifest_sha256"] == reference["private_manifest"]["sha256"]
    assert len(hub.batch_calls) == batches and hub.files == remote and hub.head_reads == 2
    text = json.dumps(result)
    for private in (fixtures.PRIVATE, "DO_NOT_PUBLISH", c.HEAD_PATH, reference["capture_id"],
                    fixtures.GDW_GENERATION, fixtures.SERIES_GENERATION):
        assert private not in text
    with pytest.raises(q.RecoveryError, match="HISTORICAL_CAPTURE_BINDING_INVALID"):
        q.validate_historical_anchors(anchors, reference, hashlib.sha256(p._json_bytes(reference)).hexdigest())


@pytest.mark.parametrize("current", ["fallback"], indirect=True)
def test_explicit_byte_verified_upload_fallback_qualifies_without_new_writes(current, tmp_path):
    hub, reference, *_ = current
    assert reference["copy_mode"] == "LOCAL_UPLOAD_FALLBACK"
    assert all("/uploaded-originals/" in row["private_copy_path"]
               for row in reference["files"] if row["present"])
    batches, before = len(hub.batch_calls), dict(hub.files)
    result = run(current, tmp_path)
    assert result["qualification_state"] == "LOGICAL_CONTINUITY_VERIFIED", result
    assert len(hub.batch_calls) == batches and hub.files == before


@pytest.mark.parametrize("defect", ["stale", "future", "run", "attempt", "source", "running",
    "revision", "observation_revision", "observed_time", "original", "hash", "xet", "manifest",
    "history_digest", "history_generation", "signature", "fallback_path", "fallback_mode"])
def test_incomplete_changed_or_replayed_capture_stays_blocked(current, tmp_path, defect):
    hub, reference, anchors, historical, digest = current
    if defect == "stale":
        reference["generated_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    elif defect == "future":
        reference["completed_at"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    elif defect == "run":
        reference["capture_id"] = "42" + reference["capture_id"]
    elif defect == "attempt":
        reference["capture_id"] = reference["capture_id"].replace("-1-", "-2-", 1)
    elif defect == "source":
        reference["source_revision"] = "8" * 40
    elif defect == "running":
        hub.stage = "RUNNING"
    elif defect == "revision":
        hub.revision = "8" * 40
    elif defect == "observation_revision":
        reference["observations"][0]["hf_revision"] = "8" * 40
    elif defect == "observed_time":
        reference["observations"][0]["observed_at"] = "PRIVATE_PROVIDER_TEXT"
    elif defect == "original":
        hub.files[p.DATABASES["gdw"]] += b"changed"
    elif defect == "hash":
        reference["files"][0]["sha256"] = "8" * 64
    elif defect == "xet":
        reference["files"][0]["xet_hash"] = "8" * 64
    elif defect == "manifest":
        reference["private_manifest"]["sha256"] = "8" * 64
    elif defect == "history_digest":
        anchors["capture_report_sha256"] = "8" * 64
    elif defect == "history_generation":
        anchors["gdw"]["database_generation_id"] = "8" * 32
    elif defect == "signature":
        anchors["gdw"]["receipt_sha256"] = "8" * 64
    elif defect == "fallback_path":
        reference["files"][0]["private_copy_path"] = reference["files"][0]["private_copy_path"].replace("/originals/", "/uploaded-originals/")
    elif defect == "fallback_mode":
        reference["copy_mode"] = "LOCAL_UPLOAD_FALLBACK"
    result = run(current, tmp_path)
    assert result["qualification_state"] == "NOT_VERIFIED", result
    assert "PRIVATE_PROVIDER_TEXT" not in json.dumps(result)
    assert result["restore_admitted"] is result["deployment_admitted"] is False


@pytest.mark.parametrize("defect", ["head_revision", "head_appears", "resume", "source", "deadline"])
def test_final_fences_cannot_leave_qualification_after_drift(current, tmp_path, defect):
    hub = current[0]
    calls = 0

    def ownership():
        nonlocal calls
        calls += 1
        if defect == "source" and calls >= 3:
            raise p.PreservationError("SOURCE_NO_LONGER_CURRENT_MAIN")

    def change(hub):
        if hub.head_reads == 1:
            if defect == "head_revision":
                hub.head_revision = "7" * 40
            elif defect == "head_appears":
                hub.head = b"{}"
            elif defect == "resume":
                hub.stage = "RUNNING"

    hub.after_head_read = change
    result = run(current, tmp_path, ownership=ownership,
                 deadline=time.monotonic() - 1 if defect == "deadline" else time.monotonic() + 60)
    assert result["qualification_state"] == "NOT_VERIFIED", result


def test_read_adapter_exposes_only_provider_reads(current):
    adapter = c.CurrentReadOnlyHub(current[0])
    for name in ("batch_bucket_files", "create_commit", "restart_space", "pause_space", "add_space_variable",
                 "delete_repo", "upload_file", "request_space_storage"):
        assert not hasattr(adapter, name)


@pytest.mark.parametrize("bad", [None, [], {"private_error": fixtures.PRIVATE}])
def test_malformed_report_never_exports_private_diagnostics(current, tmp_path, bad):
    changed = (current[0], bad, *current[2:])
    result = run(changed, tmp_path)
    assert result["qualification_state"] == "NOT_VERIFIED"
    assert fixtures.PRIVATE not in json.dumps(result)


def test_cli_rejects_local_invocation_before_provider_import(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    output = tmp_path / "public.json"
    monkeypatch.setattr("sys.argv", ["qualify", "--capture-report", "missing-private.json", "--output", str(output)])
    assert c.main() == 2
    assert json.loads(output.read_text())["qualification_state"] == "NOT_VERIFIED"
    assert "missing-private" not in capsys.readouterr().out
